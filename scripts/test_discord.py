import asyncio
from datetime import UTC, datetime

from app.core.database import AsyncSessionLocal
from app.models.post import Post, SourceType
from app.models.schedule_slot import ScheduleSlot, SlotStatus
from app.models.variant import Variant, VariantStatus
from app.services.publisher import claim_and_publish_slot


async def main():
    async with AsyncSessionLocal() as db:
        post = Post(
            source_type=SourceType.MARKDOWN,
            raw_content="Testing Discord!",
            title="Test Post"
        )
        db.add(post)
        await db.commit()
        await db.refresh(post)

        variant = Variant(
            post_id=post.id,
            platform_key="discord",
            content="Hello from Social Studio! 🚀\nReal message during Phase 4 gate.",
            hashtags=[],
            status=VariantStatus.APPROVED,
            ai_generated=False,
        )
        db.add(variant)
        await db.commit()
        await db.refresh(variant)

        slot = ScheduleSlot(
            variant_id=variant.id,
            scheduled_for=datetime.now(UTC),
            idempotency_key=f"test_discord:{variant.id}",
            status=SlotStatus.PENDING,
        )
        db.add(slot)
        await db.commit()
        await db.refresh(slot)

        print(f"Created slot {slot.id}, publishing to Discord...")

        attempt = await claim_and_publish_slot(str(slot.id), db)

        if attempt and attempt.result == "success":
            print(f"SUCCESS! Message landed in Discord. Ref ID: {attempt.response_ref}")
        else:
            print(f"FAILED. Error: {attempt.error_detail if attempt else 'None'}")

if __name__ == "__main__":
    asyncio.run(main())
