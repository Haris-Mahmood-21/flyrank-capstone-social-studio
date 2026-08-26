import logging

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters import get_adapter
from app.models.publish_attempt import PublishAttempt
from app.models.schedule_slot import ScheduleSlot, SlotStatus
from app.models.variant import Variant, VariantStatus

logger = logging.getLogger(__name__)


class ClaimError(Exception):
    """Raised when a DB constraint prevents claiming the slot."""

    pass


async def claim_and_publish_slot(
    slot_id: str,
    db: AsyncSession,
) -> PublishAttempt | None:
    """
    Safely claims a schedule slot using a claim-then-call pattern.
    The INSERT into publish_attempts with result='pending' triggers an IntegrityError
    if another worker has already claimed it.
    """
    # 1. Fetch the slot and variant
    slot = await db.scalar(select(ScheduleSlot).where(ScheduleSlot.id == slot_id))
    if not slot or slot.status != SlotStatus.PENDING:
        logger.info("Slot %s is not available for publishing", slot_id)
        return None

    variant = await db.scalar(select(Variant).where(Variant.id == slot.variant_id))
    if not variant:
        logger.error("Variant %s not found for slot %s", slot.variant_id, slot_id)
        return None

    # Determine next attempt number
    max_attempt = await db.scalar(
        select(PublishAttempt.attempt_number)
        .where(PublishAttempt.schedule_slot_id == slot_id)
        .order_by(PublishAttempt.attempt_number.desc())
        .limit(1)
    )
    next_attempt_num = (max_attempt or 0) + 1

    # 2. CLAIM: Insert a 'pending' attempt
    attempt = PublishAttempt(
        schedule_slot_id=slot.id,
        adapter_name=variant.platform_key,
        attempt_number=next_attempt_num,
        result="pending",
    )
    db.add(attempt)

    try:
        # We flush/commit to force the DB constraint to be evaluated IMMEDIATELY
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        logger.warning("DB unique constraint prevented claim on slot %s", slot_id)
        # Raise custom error so the concurrency test can assert on it!
        raise ClaimError("Slot already claimed by another worker") from exc

    # If we got here, we own the slot. We can update it to CLAIMED
    # TODO(phase5): reap stale CLAIMED slots (worker-crash recovery)
    slot.status = SlotStatus.CLAIMED
    await db.commit()

    # 3. Look up adapter
    try:
        adapter = get_adapter(variant.platform_key)
        attempt.adapter_name = adapter.platform_key
    except ValueError as e:
        logger.error("Adapter not found: %s", str(e))
        attempt.result = "failure"
        attempt.error_detail = str(e)
        slot.status = SlotStatus.FAILED
        await db.commit()
        return attempt

    # 4. Perform network call to social platform
    pub_result = await adapter.publish(variant, slot.idempotency_key)

    # 5. Record the result
    attempt.adapter_name = pub_result.adapter_name
    attempt.result = "success" if pub_result.success else "failure"
    attempt.response_ref = pub_result.response_ref
    attempt.error_detail = pub_result.error_detail

    # 6. Update statuses
    if pub_result.success:
        slot.status = SlotStatus.DONE
        variant.status = VariantStatus.PUBLISHED
    else:
        slot.status = SlotStatus.FAILED
        # Keep variant as APPROVED so it can be rescheduled if needed

    await db.commit()
    await db.refresh(attempt)
    return attempt
