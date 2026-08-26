"""PublishAttempt ORM model — audit log for every publish call."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class PublishAttempt(Base):
    __tablename__ = "publish_attempts"
    __table_args__ = (
        # Partial unique index: only one 'pending' attempt allowed per slot at a time.
        # This acts as our real DB constraint for claiming a slot.
        Index(
            "uq_active_claim",
            "schedule_slot_id",
            unique=True,
            postgresql_where=text("result = 'pending'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    schedule_slot_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("schedule_slots.id"), nullable=False
    )
    adapter_name: Mapped[str] = mapped_column(String(50), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    # Three possible values:
    #   "pending"  — inserted at claim time; the partial unique index on this value
    #                is what prevents two workers from claiming the same slot.
    #   "success"  — adapter confirmed the post went through.
    #   "failure"  — adapter reported an error or the worker crashed.
    result: Mapped[str] = mapped_column(String(20), nullable=False)
    response_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    error_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
