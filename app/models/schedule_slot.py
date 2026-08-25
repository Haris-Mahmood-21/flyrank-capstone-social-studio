"""ScheduleSlot ORM model.

The idempotency_key column carries a UNIQUE constraint at the DB level.
This is the core correctness guarantee: two workers racing on the same
slot will produce a UniqueViolation on INSERT — exactly one wins.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SlotStatus(enum.StrEnum):
    PENDING = "pending"
    CLAIMED = "claimed"
    DONE = "done"
    FAILED = "failed"


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Only one slot per variant (one variant can only be scheduled once)
    variant_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("variants.id"), unique=True, nullable=False
    )
    scheduled_for: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # DB-level uniqueness — not just application-level check
    # Format: "{variant_id}:{scheduled_for.isoformat()}"
    idempotency_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    status: Mapped[SlotStatus] = mapped_column(
        Enum(SlotStatus, name="slotstatus"),
        nullable=False,
        default=SlotStatus.PENDING,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
