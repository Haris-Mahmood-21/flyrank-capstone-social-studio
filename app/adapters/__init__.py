from collections.abc import Mapping

from .base import SocialPublisher
from .discord import DiscordPublisher
from .mock_instagram import MockInstagramPublisher
from .mock_linkedin import MockLinkedInPublisher

_DISCORD = DiscordPublisher()
_INSTAGRAM = MockInstagramPublisher()
_LINKEDIN = MockLinkedInPublisher()

ADAPTERS: Mapping[str, SocialPublisher] = {
    _DISCORD.platform_key: _DISCORD,
    _INSTAGRAM.platform_key: _INSTAGRAM,
    _LINKEDIN.platform_key: _LINKEDIN,
}


def get_adapter(platform_key: str) -> SocialPublisher:
    """Get the publisher adapter for a given platform key."""
    if platform_key not in ADAPTERS:
        raise ValueError(f"No adapter registered for platform_key: {platform_key}")
    return ADAPTERS[platform_key]
