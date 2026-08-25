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
