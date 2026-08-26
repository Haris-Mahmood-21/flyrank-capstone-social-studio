"""Variant generation service.

Calls the Gemini API to produce platform-specific content from a blog post,
validates each result against its constraint profile, and saves approved
variants to the database.

Cost tracking (stretch goal): every Gemini call logs token counts and
estimated USD cost stored in variants.ai_cost_usd.
"""

import json
import logging
from decimal import Decimal

from google import genai
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.constraint_profile import ConstraintProfile
from app.models.post import Post
from app.models.variant import Variant, VariantStatus

logger = logging.getLogger(__name__)

# Gemini 2.0 Flash pricing (free-tier users pay $0, but we track as if paid)
_INPUT_COST_PER_TOKEN = Decimal("0.10") / Decimal("1000000")  # $0.10 / 1M tokens
_OUTPUT_COST_PER_TOKEN = Decimal("0.40") / Decimal("1000000")  # $0.40 / 1M tokens
_MODEL_NAME = "gemini-3.6-flash"


def _build_prompt(post: Post, profile: ConstraintProfile) -> str:
    tone = profile.tone_rules
    hashtag_instruction = (
        f"Include exactly {profile.max_hashtags} relevant hashtags in the 'hashtags' list."
        if profile.max_hashtags > 0
        else "The 'hashtags' list must be empty — this platform does not use hashtags."
    )
    emoji_instruction = (
        "You MAY use emojis where appropriate." if tone.get("emojis") else "Do NOT use any emojis."
    )
    return f"""You are an expert social media content writer.
Convert the blog post below into a {profile.platform_key.upper()} post.

PLATFORM CONSTRAINTS (you must respect all of them):
- The 'content' field must NOT exceed {profile.max_length} characters.
- Tone/style: {tone.get("style", "neutral")}. {emoji_instruction}
- {hashtag_instruction}

RESPONSE FORMAT — return ONLY valid JSON, no markdown fences:
{{
  "content": "<the post text, without any hashtags appended>",
  "hashtags": ["<tag1>", "<tag2>"]
}}

BLOG POST TITLE: {post.title}

BLOG POST CONTENT:
{post.raw_content[:8000]}
"""


def _estimate_cost(input_tokens: int, output_tokens: int) -> Decimal:
    return (
        Decimal(input_tokens) * _INPUT_COST_PER_TOKEN
        + Decimal(output_tokens) * _OUTPUT_COST_PER_TOKEN
    )


class ConstraintViolationError(Exception):
    """Raised when generated content violates a platform constraint profile."""


def validate_against_profile(
    content: str,
    hashtags: list[str],
    profile: ConstraintProfile,
) -> None:
    """
    Raise ConstraintViolationError with a clear message if content violates
    the platform's constraint profile.

    Checks:
      - content character length <= max_length
      - number of hashtags <= max_hashtags
      - no hashtags on platforms where max_hashtags == 0
    """
    if len(content) > profile.max_length:
        raise ConstraintViolationError(
            f"[{profile.platform_key}] Content length {len(content)} exceeds "
            f"max_length={profile.max_length}"
        )
    if profile.max_hashtags == 0 and hashtags:
        raise ConstraintViolationError(
            f"[{profile.platform_key}] Hashtags are not allowed on this platform "
            f"but {len(hashtags)} were generated"
        )
    if len(hashtags) > profile.max_hashtags:
        raise ConstraintViolationError(
            f"[{profile.platform_key}] Hashtag count {len(hashtags)} exceeds "
            f"max_hashtags={profile.max_hashtags}"
        )


async def _call_gemini(prompt: str) -> tuple[str, Decimal]:
    """
    Call Gemini and return (raw_json_text, estimated_cost_usd).

    Raises ValueError if the API key is not configured.
    """
    if not settings.GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY is not set — cannot call Gemini API. Add it to your .env file."
        )
    client = genai.Client(api_key=settings.GEMINI_API_KEY)
    response = await client.aio.models.generate_content(
        model=_MODEL_NAME,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )
    usage = response.usage_metadata
    input_tokens = usage.prompt_token_count or 0
    output_tokens = usage.candidates_token_count or 0
    cost = _estimate_cost(input_tokens, output_tokens)
    logger.info(
        "Gemini call complete: input_tokens=%d output_tokens=%d cost_usd=%.8f",
        input_tokens,
        output_tokens,
        cost,
    )
    return response.text or "", cost


async def generate_variants(
    post: Post,
    platform_keys: list[str],
    db: AsyncSession,
) -> list[Variant]:
    """
    Generate and save variants for each requested platform.

    Steps per platform:
      1. Load the platform's constraint profile.
      2. Build a structured Gemini prompt.
      3. Call Gemini (async).
      4. Parse JSON response → content + hashtags.
      5. Validate against constraint profile (raises 422 on violation).
      6. Build a Variant ORM object (unsaved until all platforms succeed).

    If ANY platform fails validation, the whole request is rejected and
    nothing is written to the database.
    """
    # --- Load constraint profiles for all requested platforms ---
    result = await db.execute(
        select(ConstraintProfile).where(ConstraintProfile.platform_key.in_(platform_keys))
    )
    profiles_by_key: dict[str, ConstraintProfile] = {
        p.platform_key: p for p in result.scalars().all()
    }

    missing = set(platform_keys) - set(profiles_by_key)
    if missing:
        raise ValueError(f"No constraint profile found for platforms: {missing}")

    # --- Generate for each platform, collect results before writing ---
    variants: list[Variant] = []
    violations: list[str] = []

    for key in platform_keys:
        profile = profiles_by_key[key]
        prompt = _build_prompt(post, profile)

        try:
            raw_json, cost = await _call_gemini(prompt)
        except Exception as exc:
            raise RuntimeError(f"Gemini API call failed for platform '{key}': {exc}") from exc

        try:
            parsed = json.loads(raw_json)
            content: str = parsed["content"]
            hashtags: list[str] = parsed.get("hashtags", [])
        except (json.JSONDecodeError, KeyError) as exc:
            raise RuntimeError(
                f"Gemini returned invalid JSON for platform '{key}': {exc}\n"
                f"Raw response: {raw_json[:200]}"
            ) from exc

        try:
            validate_against_profile(content, hashtags, profile)
        except ConstraintViolationError as exc:
            violations.append(str(exc))
            continue

        variants.append(
            Variant(
                post_id=post.id,
                platform_key=key,
                content=content,
                hashtags=hashtags,
                status=VariantStatus.DRAFT,
                ai_generated=True,
                ai_cost_usd=cost,
            )
        )
        logger.info(
            "Variant generated: post=%s platform=%s status=draft cost_usd=%.8f",
            post.id,
            key,
            cost,
        )

    if violations:
        raise ConstraintViolationError(
            "One or more generated variants violated platform constraints. "
            "Nothing was saved.\n" + "\n".join(violations)
        )

    db.add_all(variants)
    await db.commit()
    for v in variants:
        await db.refresh(v)

    return variants
