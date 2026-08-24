"""
SocialPublisher Protocol — the adapter contract all publishing targets must implement.

Business logic (scheduler, review workflow) depends ONLY on this interface.
Swapping 'discord' → 'mock_instagram' for a given platform_key is a config change,
never a code change. This is proven by a test in Phase 4.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from app.models.variant import Variant


@dataclass
class PublishResult:
    """Outcome of a single publish attempt."""

    success: bool
    adapter_name: str  # "discord" | "mock_instagram" | "mock_linkedin"
    response_ref: str | None  # message ID, mock preview ref, or None
    error_detail: str | None  # populated on failure, None on success


class SocialPublisher(Protocol):
    """
    Adapter contract for all social publishing targets.

    Every implementation must be idempotency-safe: if called twice with the
    same idempotency_key it MUST NOT publish a second time. The DB unique
    constraint on schedule_slots.idempotency_key is the backstop, but
    adapters should also short-circuit on duplicate keys where possible.

    Implementations must NEVER raise. All exceptions must be caught and
    returned as PublishResult(success=False, error_detail=<message>).
    """

    @property
    def platform_key(self) -> str:
        """The platform_key string this adapter handles (e.g. 'discord')."""
        ...

    async def publish(
        self,
        variant: "Variant",
        idempotency_key: str,
    ) -> PublishResult:
        """
        Publish variant content to the target platform exactly once.

        Args:
            variant:         The approved Variant ORM record to publish.
            idempotency_key: Globally unique key for this publish attempt
                             (= schedule_slots.idempotency_key).

        Returns:
            PublishResult with success=True and a response_ref on success,
            or success=False and an error_detail on failure.
        """
        ...
