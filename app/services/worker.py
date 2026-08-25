import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.logging import correlation_id_var, new_correlation_id
from app.models.publish_attempt import PublishAttempt
from app.models.schedule_slot import ScheduleSlot, SlotStatus
from app.services.publisher import claim_and_publish_slot

logger = logging.getLogger(__name__)

async def reap_stale_claims(db: AsyncSession) -> int:
    """
    Finds slots that were claimed by a worker that crashed (stuck in 'pending' attempt
    for > 5 minutes) and resets them so they can be retried.
    """
    cutoff = datetime.now(UTC) - timedelta(minutes=5)

    stale_attempts = (await db.scalars(
        select(PublishAttempt)
        .where(PublishAttempt.result == "pending", PublishAttempt.attempted_at <= cutoff)
    )).all()

    reaped_count = 0
    for attempt in stale_attempts:
        attempt.result = "failure"
        attempt.error_detail = "Worker crashed or timed out during publish."

        slot = await db.scalar(
            select(ScheduleSlot).where(ScheduleSlot.id == attempt.schedule_slot_id)
        )
        if slot:
            slot.status = SlotStatus.PENDING

        reaped_count += 1

    await db.commit()
    if reaped_count > 0:
        logger.warning("Reaped %d stale claims due to worker crashes", reaped_count)

    return reaped_count

async def poll_due_slots(db: AsyncSession | None = None) -> None:
    """
    Runs periodically via APScheduler.
    Finds all PENDING slots where scheduled_for <= now, and publishes them.
    """
    cid = new_correlation_id()
    token = correlation_id_var.set(cid)

    # If no db session is provided (e.g. running from APScheduler), create one
    own_session = AsyncSessionLocal() if db is None else None
    session = db if db is not None else own_session

    try:
        await reap_stale_claims(session)

        now = datetime.now(UTC)
        due_slots = (await session.scalars(
            select(ScheduleSlot.id)
            .where(ScheduleSlot.status == SlotStatus.PENDING, ScheduleSlot.scheduled_for <= now)
            .order_by(ScheduleSlot.scheduled_for.asc())
        )).all()

        if due_slots:
            logger.info("Found %d due slots to publish", len(due_slots))

        for slot_id in due_slots:
            try:
                await claim_and_publish_slot(str(slot_id), session)
            except Exception as e:
                logger.error("Unexpected error publishing slot %s: %s", slot_id, e)
    finally:
        if own_session:
            await own_session.close()
        correlation_id_var.reset(token)
