import uuid
from typing import TYPE_CHECKING

from .base import PublishResult, SocialPublisher

if TYPE_CHECKING:
    from app.models.variant import Variant


class MockLinkedInPublisher(SocialPublisher):
    @property
    def platform_key(self) -> str:
        return "linkedin"

    async def publish(
        self,
        variant: "Variant",
        idempotency_key: str,
    ) -> PublishResult:
        # Mock success response
        ref = f"li_mock_{uuid.uuid4().hex[:8]}"
        return PublishResult(
            success=True,
            adapter_name="mock_linkedin",
            response_ref=ref,
            error_detail=None,
        )
