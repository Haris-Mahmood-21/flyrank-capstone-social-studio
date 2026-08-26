from typing import TYPE_CHECKING

import httpx

from app.core.config import settings

from .base import PublishResult, SocialPublisher

if TYPE_CHECKING:
    from app.models.variant import Variant


class DiscordPublisher(SocialPublisher):
    @property
    def platform_key(self) -> str:
        return "discord"

    async def publish(
        self,
        variant: "Variant",
        idempotency_key: str,
    ) -> PublishResult:
        if not settings.DISCORD_WEBHOOK_URL:
            return PublishResult(
                success=False,
                adapter_name="discord",
                response_ref=None,
                error_detail="DISCORD_WEBHOOK_URL environment variable is missing",
            )

        # Include idempotency_key in content as Discord doesn't have an idempotency header
        # for webhooks, this helps us see it in the UI and test behavior.
        content = f"{variant.content}\n\n*Idempotency Key: {idempotency_key}*"
        if variant.hashtags:
            content += f"\n{' '.join(['#' + h for h in variant.hashtags])}"

        try:
            async with httpx.AsyncClient() as client:
                # wait=true makes Discord return the created message object
                url = f"{settings.DISCORD_WEBHOOK_URL}?wait=true"
                response = await client.post(url, json={"content": content})

                if response.status_code >= 400:
                    return PublishResult(
                        success=False,
                        adapter_name="discord",
                        response_ref=None,
                        error_detail=f"Discord API error: {response.status_code} {response.text}",
                    )

                data = response.json()
                message_id = data.get("id")
                return PublishResult(
                    success=True,
                    adapter_name="discord",
                    response_ref=message_id,
                    error_detail=None,
                )
        except Exception as e:
            return PublishResult(
                success=False,
                adapter_name="discord",
                response_ref=None,
                error_detail=f"Exception during request: {str(e)}",
            )
