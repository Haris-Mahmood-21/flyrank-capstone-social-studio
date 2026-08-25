"""Post ORM model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class SourceType(enum.StrEnum):
    URL = "url"
    MARKDOWN = "markdown"


class Post(Base):
    __tablename__ = "posts"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_type: Mapped[SourceType] = mapped_column(
        Enum(SourceType, name="sourcetype"), nullable=False
    )
    source_ref: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
