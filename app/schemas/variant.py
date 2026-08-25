"""Pydantic schemas for variants."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.models.variant import VariantStatus


class GenerateRequest(BaseModel):
    """Payload for POST /posts/{id}/variants/generate."""

    # e.g. ["discord", "instagram", "linkedin"]
    platform_keys: list[str]


class VariantResponse(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    platform_key: str
    content: str
    hashtags: list[str]
    status: VariantStatus
    ai_generated: bool
    ai_cost_usd: Decimal | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GenerateResponse(BaseModel):
    variants: list[VariantResponse]
