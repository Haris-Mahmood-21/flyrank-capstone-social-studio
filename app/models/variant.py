"""Variant ORM model — generated post content for a specific platform."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class VariantStatus(enum.StrEnum):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


class Variant(Base):
    __tablename__ = "variants"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    post_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("posts.id"), nullable=False)
    platform_key: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # List of hashtag strings without the '#' prefix
    hashtags: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    status: Mapped[VariantStatus] = mapped_column(
        Enum(VariantStatus, name="variantstatus"),
        nullable=False,
        default=VariantStatus.DRAFT,
    )
    ai_generated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Stretch goal: cost of the Gemini call that produced this variant
    ai_cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(12, 8), nullable=True)
    # Stretch goal: claims not traceable to the source post
    grounding_flags: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
