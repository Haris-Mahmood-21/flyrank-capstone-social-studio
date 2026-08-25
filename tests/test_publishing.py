
"""Integration tests for Phase 4: Adapters & idempotent publish."""

import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, SourceType
from app.models.publish_attempt import PublishAttempt
from app.models.schedule_slot import ScheduleSlot, SlotStatus
from app.models.variant import Variant, VariantStatus
from app.services.publisher import ClaimError, claim_and_publish_slot

pytestmark = pytest.mark.asyncio

async def _seed_data(db_session: AsyncSession) -> ScheduleSlot:
    post = Post(source_type=SourceType.MARKDOWN, raw_content="test", title="test")
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    variant = Variant(
        post_id=post.id,
        platform_key="instagram",
        content="mock content",
        hashtags=["mock"],
        status=VariantStatus.APPROVED,
        ai_generated=False,
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)

    slot = ScheduleSlot(
        variant_id=variant.id,
        scheduled_for=datetime.now(UTC),
        idempotency_key=f"{variant.id}:123",
        status=SlotStatus.PENDING,
    )
    db_session.add(slot)
    await db_session.commit()
    await db_session.refresh(slot)

    return slot


async def test_publish_adapter_success(db_session: AsyncSession) -> None:
    slot = await _seed_data(db_session)

    attempt = await claim_and_publish_slot(slot.id, db_session)

    assert attempt is not None
    assert attempt.result == "success"
    assert attempt.adapter_name == "mock_instagram"
    assert attempt.response_ref.startswith("ig_mock_")

    await db_session.refresh(slot)
    assert slot.status == SlotStatus.DONE


async def test_concurrency_double_publish_prevented(db_session: AsyncSession) -> None:
    """
    GATE: two async workers attempt the same slot simultaneously.
    Asserts on the actual IntegrityError (ClaimError) from the second worker's insert.
    """
    slot = await _seed_data(db_session)

    from sqlalchemy.ext.asyncio import async_sessionmaker
    from sqlalchemy.pool import NullPool

    from app.core.config import settings
    from app.core.database import create_async_engine

    _base_url, _ = settings.DATABASE_URL.rsplit("/", 1)
    test_db_url = f"{_base_url}/social_studio_test"

    engine2 = create_async_engine(test_db_url, poolclass=NullPool)
    factory2 = async_sessionmaker(engine2, class_=AsyncSession, expire_on_commit=False)

    async with factory2() as db_session2:
        # Run them simultaneously
        t1 = asyncio.create_task(claim_and_publish_slot(slot.id, db_session))
        t2 = asyncio.create_task(claim_and_publish_slot(slot.id, db_session2))

        results = await asyncio.gather(t1, t2, return_exceptions=True)

    await engine2.dispose()

    # One should be a PublishAttempt, the other should be a ClaimError
    successes = [r for r in results if isinstance(r, PublishAttempt)]
    errors = [r for r in results if isinstance(r, ClaimError)]

    assert len(successes) == 1
    assert len(errors) == 1, f"Expected exactly 1 ClaimError, got {errors}"

    attempt = successes[0]
    assert attempt.result == "success"

    # Print the error for visual confirmation in test output
    print(f"\nCaught constraint violation successfully: {repr(errors[0].__cause__)}")

    # Verify in DB
    all_attempts = (await db_session.scalars(select(PublishAttempt).where(PublishAttempt.schedule_slot_id == slot.id))).all()
    assert len(all_attempts) == 1

    await db_session.refresh(slot)
    assert slot.status == SlotStatus.DONE



async def test_sequential_duplicate_publish_prevented(db_session: AsyncSession) -> None:
    """
    GATE: repeated publish call -> one message only.
    Asserts that sequentially calling publish on a slot already marked DONE
    short-circuits before inserting a new attempt or calling the adapter.
    """
    slot = await _seed_data(db_session)

    with patch(
        "app.adapters.mock_instagram.MockInstagramPublisher.publish",
        new_callable=AsyncMock
    ) as mock_publish:
        from app.adapters.base import PublishResult
        mock_publish.return_value = PublishResult(
            success=True,
            adapter_name="mock_instagram",
            response_ref="ig_mock_123",
            error_detail=None
        )

        # Call 1 (Expected to succeed)
        attempt1 = await claim_and_publish_slot(slot.id, db_session)
        assert attempt1 is not None
        assert attempt1.result == "success"

        # Call 2 (Expected to short-circuit and return None)
        attempt2 = await claim_and_publish_slot(slot.id, db_session)
        assert attempt2 is None

        # Verify adapter was only called exactly once
        assert mock_publish.call_count == 1

        # Verify DB only has 1 publish attempt row for this slot
        attempts = (await db_session.scalars(
            select(PublishAttempt).where(PublishAttempt.schedule_slot_id == slot.id)
        )).all()
        assert len(attempts) == 1
