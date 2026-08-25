import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.variant import VariantStatus

# --- Generation ---


class GenerateRequest(BaseModel):
    platform_keys: list[Literal["discord", "instagram", "linkedin"]] = Field(
        ..., description="List of platform keys to generate variants for."
    )


class VariantResponse(BaseModel):
    id: uuid.UUID
    post_id: uuid.UUID
    platform_key: str
    content: str
    hashtags: list[str]
    status: VariantStatus
    ai_generated: bool
    ai_cost_usd: float | None = None
    grounding_flags: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class GenerateResponse(BaseModel):
    variants: list[VariantResponse]


# --- Editing ---


class VariantUpdate(BaseModel):
    content: str | None = None
    hashtags: list[str] | None = None
