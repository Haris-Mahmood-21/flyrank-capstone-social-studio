"""
Integration tests for POST /posts/{id}/variants/generate.

Gemini API calls are mocked so these tests run without a real API key.
"""

import json
import uuid
from unittest.mock import MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, SourceType

pytestmark = pytest.mark.asyncio


def _mock_response(content: str, hashtags: list[str]) -> MagicMock:
    """Build a mock Gemini response object matching google-genai's API."""
    mock_resp = MagicMock()
    mock_resp.text = json.dumps({"content": content, "hashtags": hashtags})
    mock_resp.usage_metadata.prompt_token_count = 100
    mock_resp.usage_metadata.candidates_token_count = 50
    return mock_resp


async def _create_post(db_session: AsyncSession) -> Post:
    post = Post(
        source_type=SourceType.MARKDOWN,
        raw_content="# How AI Changes Marketing\n\nAI is transforming how brands connect.",
        title="How AI Changes Marketing",
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)
    return post


def _patch_gemini(platform_responses: dict[str, tuple[str, list[str]]]):
    """
    Patch app.services.generation.genai.Client so generate_content returns
    a response matching the platform found in the prompt.
    """

    async def _generate(model, contents, config):
        for platform, (content, hashtags) in platform_responses.items():
            if platform.upper() in contents:
                return _mock_response(content, hashtags)
        first = next(iter(platform_responses.values()))
        return _mock_response(*first)

    mock_client = MagicMock()
    mock_client.aio.models.generate_content = _generate

    return patch(
        "app.services.generation.genai.Client",
        return_value=mock_client,
    )


# ---------------------------------------------------------------------------
# Happy path: 3 variants generated, all within constraints
# ---------------------------------------------------------------------------


async def test_generate_three_variants(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    seeded_profiles,
) -> None:
    """POST /posts/{id}/variants/generate returns 3 variants, all status=draft."""
    post = await _create_post(db_session)

    platform_responses = {
        "discord": ("Great AI post! Short and casual.", []),
        "instagram": ("AI is changing marketing! 🚀", ["ai", "marketing", "tech"]),
        "linkedin": (
            "Artificial intelligence is fundamentally transforming how brands "
            "engage with their target audiences.",
            ["AI", "Marketing"],
        ),
    }

    with _patch_gemini(platform_responses):
        resp = await client.post(
            f"/posts/{post.id}/variants/generate",
            json={"platform_keys": ["discord", "instagram", "linkedin"]},
            headers=auth_headers,
        )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert len(data["variants"]) == 3

    platform_keys = {v["platform_key"] for v in data["variants"]}
    assert platform_keys == {"discord", "instagram", "linkedin"}

    for variant in data["variants"]:
        assert variant["status"] == "draft"
        assert variant["ai_generated"] is True
        assert variant["post_id"] == str(post.id)


# ---------------------------------------------------------------------------
# Constraint violation: content too long → 422
# ---------------------------------------------------------------------------


async def test_generate_blocked_on_content_too_long(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    seeded_profiles,
) -> None:
    """If Gemini returns content exceeding max_length, the request is rejected 422."""
    post = await _create_post(db_session)

    # Discord max_length = 2000; return 2001 chars
    oversized = {"discord": ("x" * 2001, [])}
    with _patch_gemini(oversized):
        resp = await client.post(
            f"/posts/{post.id}/variants/generate",
            json={"platform_keys": ["discord"]},
            headers=auth_headers,
        )

    assert resp.status_code == 422, resp.text
    assert "max_length" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Constraint violation: too many hashtags on LinkedIn → 422
# ---------------------------------------------------------------------------


async def test_generate_blocked_on_too_many_hashtags(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    seeded_profiles,
) -> None:
    """LinkedIn max_hashtags = 5; returning 6 is blocked with 422."""
    post = await _create_post(db_session)

    too_many = {"linkedin": ("Professional post.", [f"tag{i}" for i in range(6)])}
    with _patch_gemini(too_many):
        resp = await client.post(
            f"/posts/{post.id}/variants/generate",
            json={"platform_keys": ["linkedin"]},
            headers=auth_headers,
        )

    assert resp.status_code == 422, resp.text
    assert "max_hashtags" in resp.json()["detail"]


# ---------------------------------------------------------------------------
# Post not found → 404
# ---------------------------------------------------------------------------


async def test_generate_unknown_post(
    client: AsyncClient,
    auth_headers: dict,
) -> None:
    resp = await client.post(
        f"/posts/{uuid.uuid4()}/variants/generate",
        json={"platform_keys": ["discord"]},
        headers=auth_headers,
    )
    assert resp.status_code == 404
