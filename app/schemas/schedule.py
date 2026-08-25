import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.schedule_slot import SlotStatus


class ScheduleCreate(BaseModel):
    scheduled_for: datetime = Field(
        ..., description="When the post should be published (UTC timezone aware)."
    )


class ScheduleSlotResponse(BaseModel):
    id: uuid.UUID
    variant_id: uuid.UUID
    scheduled_for: datetime
    idempotency_key: str
    status: SlotStatus

    model_config = ConfigDict(from_attributes=True)


class PublishAttemptResponse(BaseModel):
    id: uuid.UUID
    schedule_slot_id: uuid.UUID
    adapter_name: str
    attempt_number: int
    result: str
    response_ref: str | None = None
    error_detail: str | None = None
    attempted_at: datetime

    model_config = ConfigDict(from_attributes=True)
