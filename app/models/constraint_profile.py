"""ConstraintProfile ORM model — one row per platform."""

import uuid

from sqlalchemy import Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class ConstraintProfile(Base):
    __tablename__ = "constraint_profiles"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    platform_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    max_length: Mapped[int] = mapped_column(Integer, nullable=False)
    # {"style": "casual|visual|professional", "emojis": bool, "cta": bool}
    tone_rules: Mapped[dict] = mapped_column(JSONB, nullable=False)
    max_hashtags: Mapped[int] = mapped_column(Integer, nullable=False)
