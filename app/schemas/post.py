"""Pydantic schemas for posts."""

import uuid
from datetime import datetime

from pydantic import BaseModel, model_validator

from app.models.post import SourceType


class PostCreate(BaseModel):
    source_type: SourceType
    # Required when source_type == "url"
    source_ref: str | None = None
    # Required when source_type == "markdown"
    raw_content: str | None = None
    title: str

    @model_validator(mode="after")
    def check_source_fields(self) -> "PostCreate":
        if self.source_type == SourceType.URL and not self.source_ref:
            raise ValueError("source_ref is required when source_type is 'url'")
        if self.source_type == SourceType.MARKDOWN and not self.raw_content:
            raise ValueError("raw_content is required when source_type is 'markdown'")
        return self


class PostResponse(BaseModel):
    id: uuid.UUID
    source_type: SourceType
    source_ref: str | None
    title: str
    created_at: datetime

    model_config = {"from_attributes": True}
