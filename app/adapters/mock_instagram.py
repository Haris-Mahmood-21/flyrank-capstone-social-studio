import uuid
from typing import TYPE_CHECKING

from .base import PublishResult, SocialPublisher

if TYPE_CHECKING:
    from app.models.variant import Variant

class MockInstagramPublisher(SocialPublisher):
    @property
    def platform_key(self) -> str:
        return "instagram"

    async def publish(
        self,
        variant: "Variant",
        idempotency_key: str,
    ) -> PublishResult:
        # Mock success response
        ref = f"ig_mock_{uuid.uuid4().hex[:8]}"
        return PublishResult(
            success=True,
            adapter_name="mock_instagram",
            response_ref=ref,
            error_detail=None,
        )
