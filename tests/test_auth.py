"""Integration tests for POST /auth/login."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User

pytestmark = pytest.mark.asyncio


async def _create_user(db_session: AsyncSession) -> None:
    user = User(email="test@example.com", hashed_password=hash_password("testpassword"))
    db_session.add(user)
    await db_session.commit()


async def test_login_valid_credentials(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session)
    resp = await client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "testpassword"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient, db_session: AsyncSession) -> None:
    await _create_user(db_session)
    resp = await client.post(
        "/auth/login",
        json={"email": "test@example.com", "password": "wrongpassword"},
    )
    assert resp.status_code == 401


async def test_login_unknown_email(client: AsyncClient) -> None:
    resp = await client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "x"},
    )
    assert resp.status_code == 401


async def test_protected_endpoint_requires_token(client: AsyncClient) -> None:
    """POST /posts without a token is rejected."""
    resp = await client.post(
        "/posts",
        json={"source_type": "markdown", "raw_content": "hello", "title": "Test"},
    )
    assert resp.status_code in (401, 403)
