"""Tests for Phase 3 review workflow endpoints."""

from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.post import Post, SourceType
from app.models.variant import Variant, VariantStatus

pytestmark = pytest.mark.asyncio


async def _create_test_data(db_session: AsyncSession) -> tuple[Post, Variant]:
    post = Post(
        source_type=SourceType.MARKDOWN,
        raw_content="hello",
        title="Test",
    )
    db_session.add(post)
    await db_session.commit()
    await db_session.refresh(post)

    variant = Variant(
        post_id=post.id,
        platform_key="discord",
        content="This is a draft.",
        hashtags=["test"],
        status=VariantStatus.DRAFT,
        ai_generated=False,
    )
    db_session.add(variant)
    await db_session.commit()
    await db_session.refresh(variant)

    return post, variant


async def test_approve_and_reject_variant(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
) -> None:
    _, variant = await _create_test_data(db_session)

    # Approve
    resp = await client.post(
        f"/variants/{variant.id}/approve",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    # Reject
    resp = await client.post(
        f"/variants/{variant.id}/reject",
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


async def test_edit_variant_content(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
    seeded_profiles,
) -> None:
    _, variant = await _create_test_data(db_session)

    # Valid edit
    resp = await client.patch(
        f"/variants/{variant.id}",
        json={"content": "New content for discord", "hashtags": []},
        headers=auth_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["content"] == "New content for discord"

    # Invalid edit (too long for discord, max 2000)
    resp = await client.patch(
        f"/variants/{variant.id}",
        json={"content": "x" * 2001},
        headers=auth_headers,
    )
    assert resp.status_code == 422
    assert "max_length" in resp.json()["detail"]


async def test_schedule_unapproved_variant_fails(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
) -> None:
    """GATE: Unapproved variant blocked."""
    _, variant = await _create_test_data(db_session)
    # Status is currently DRAFT

    future_time = datetime.now(UTC) + timedelta(hours=1)
    resp = await client.post(
        f"/variants/{variant.id}/schedule",
        json={"scheduled_for": future_time.isoformat()},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Cannot schedule" in resp.json()["detail"]


async def test_schedule_approved_variant_succeeds(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
) -> None:
    """GATE: Approved one proceeds."""
    _, variant = await _create_test_data(db_session)

    # Approve first
    await client.post(f"/variants/{variant.id}/approve", headers=auth_headers)

    future_time = datetime.now(UTC) + timedelta(hours=1)
    resp = await client.post(
        f"/variants/{variant.id}/schedule",
        json={"scheduled_for": future_time.isoformat()},
        headers=auth_headers,
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["variant_id"] == str(variant.id)
    assert data["status"] == "pending"


async def test_schedule_slot_unique_constraint(
    client: AsyncClient,
    db_session: AsyncSession,
    auth_headers: dict,
) -> None:
    _, variant = await _create_test_data(db_session)

    await client.post(f"/variants/{variant.id}/approve", headers=auth_headers)

    future_time = datetime.now(UTC) + timedelta(hours=1)

    # First schedule succeeds
    resp1 = await client.post(
        f"/variants/{variant.id}/schedule",
        json={"scheduled_for": future_time.isoformat()},
        headers=auth_headers,
    )
    assert resp1.status_code == 201

    # Second schedule for same variant fails (unique constraint on variant_id or idempotency_key)
    future_time_2 = datetime.now(UTC) + timedelta(hours=2)
    resp2 = await client.post(
        f"/variants/{variant.id}/schedule",
        json={"scheduled_for": future_time_2.isoformat()},
        headers=auth_headers,
    )
    assert resp2.status_code == 409
