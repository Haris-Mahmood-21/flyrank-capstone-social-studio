import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, SourceType
from app.models.variant import Variant, VariantStatus
from app.models.schedule_slot import ScheduleSlot, SlotStatus
from app.models.publish_attempt import PublishAttempt
from app.services.worker import poll_due_slots, reap_stale_claims

pytestmark = pytest.mark.asyncio

async def _seed_data(db_session: AsyncSession, scheduled_for_delta_sec: int) -> ScheduleSlot:
    post = Post(source_type=SourceType.MARKDOWN, raw_content="test", title="test")
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    variant = Variant(
        post_id=post.id,
        platform_key="linkedin", 
        content="worker test",
        hashtags=[],
        status=VariantStatus.APPROVED,
        ai_generated=False,
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)

    slot = ScheduleSlot(
        variant_id=variant.id,
        scheduled_for=datetime.now(timezone.utc) + timedelta(seconds=scheduled_for_delta_sec),
        idempotency_key=f"worker_test:{variant.id}",
        status=SlotStatus.PENDING,
    )
    db_session.add(slot)
    await db_session.commit()
    await db_session.refresh(slot)
    
    return slot


async def test_poll_due_slots_publishes_due_items(db_session: AsyncSession) -> None:
    # Seed a slot in the past (-10 seconds)
    slot_due = await _seed_data(db_session, -10)
    # Seed a slot in the future (+1 hour)
    slot_future = await _seed_data(db_session, 3600)

    # Run the worker cycle once
    await poll_due_slots(db_session)

    # The due slot should be DONE
    await db_session.refresh(slot_due)
    assert slot_due.status == SlotStatus.DONE

    # The future slot should still be PENDING
    await db_session.refresh(slot_future)
    assert slot_future.status == SlotStatus.PENDING

    # Verify publish attempt was created for the due slot
    attempts = (await db_session.scalars(
        select(PublishAttempt).where(PublishAttempt.schedule_slot_id == slot_due.id)
    )).all()
    assert len(attempts) == 1
    assert attempts[0].result == "success"


async def test_reap_stale_claims(db_session: AsyncSession) -> None:
    """GATE: Kill worker mid-batch, restart, prove zero duplicates (reaper restores state)."""
    slot = await _seed_data(db_session, -10)
    
    # Simulate a crashed worker: slot is CLAIMED, attempt is PENDING, timestamp is old
    slot.status = SlotStatus.CLAIMED
    
    old_time = datetime.now(timezone.utc) - timedelta(minutes=10)
    stuck_attempt = PublishAttempt(
        schedule_slot_id=slot.id,
        adapter_name="discord",
        attempt_number=1,
        result="pending",
    )
    db_session.add(stuck_attempt)
    await db_session.commit()
    await db_session.refresh(stuck_attempt)
    
    # Manually backdate the attempted_at (SQLAlchemy doesn't let us easily set server_default locally without this)
    # Wait, we can just execute an update
    from sqlalchemy import update
    await db_session.execute(
        update(PublishAttempt)
        .where(PublishAttempt.id == stuck_attempt.id)
        .values(attempted_at=old_time)
    )
    await db_session.commit()

    # Verify pre-reap state
    await db_session.refresh(stuck_attempt)
    assert stuck_attempt.result == "pending"

    # Run the reaper
    reaped = await reap_stale_claims(db_session)
    assert reaped == 1
    
    # Verify post-reap state
    await db_session.refresh(stuck_attempt)
    assert stuck_attempt.result == "failure"
    assert "crashed" in stuck_attempt.error_detail

    await db_session.refresh(slot)
    assert slot.status == SlotStatus.PENDING

    # Now if we poll due slots, it should seamlessly retry and succeed
    await poll_due_slots(db_session)
    
    await db_session.refresh(slot)
    assert slot.status == SlotStatus.DONE
    
    # We should now have TWO attempts (one failed from crash, one success from retry)
    attempts = (await db_session.scalars(
        select(PublishAttempt).where(PublishAttempt.schedule_slot_id == slot.id).order_by(PublishAttempt.attempt_number)
    )).all()
    assert len(attempts) == 2
    assert attempts[0].result == "failure"
    assert attempts[1].result == "success"
