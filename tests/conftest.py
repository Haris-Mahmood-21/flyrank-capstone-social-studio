"""
Shared pytest fixtures.

Design principles:
- Each test gets its own event loop (pytest-asyncio default in asyncio_mode=auto).
- NullPool is used so asyncpg never holds open connections across event loop boundaries.
- Tables are TRUNCATED via a subprocess psql call at the END of each test,
  completely bypassing the asyncpg event loop (avoids "different loop" bugs).
- The HTTP client is wired to the test DB via FastAPI dependency override.
"""

import asyncio
import subprocess
from collections.abc import AsyncGenerator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models import ConstraintProfile, User  # noqa: F401 — registers all ORM models

_base_url, _ = settings.DATABASE_URL.rsplit("/", 1)
TEST_DB_URL = f"{_base_url}/social_studio_test"

_TRUNCATE_SQL = (
    "TRUNCATE TABLE publish_attempts, schedule_slots, variants, "
    "posts, constraint_profiles, users RESTART IDENTITY CASCADE;"
)

# Docker container name (deterministic from project directory name)
_DB_CONTAINER = "flyrank-capstone-social-studio-db-1"


def _psql(sql: str) -> None:
    """Run SQL against the test DB via docker exec (synchronous, no asyncpg)."""
    subprocess.run(
        [
            "docker",
            "exec",
            _DB_CONTAINER,
            "psql",
            "-U",
            "social_studio",
            "-d",
            "social_studio_test",
            "-c",
            sql,
        ],
        check=True,
        capture_output=True,
    )


# ---------------------------------------------------------------------------
# Schema lifecycle — synchronous, before/after the entire test session
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Drop and recreate all tables before any test runs."""

    async def _setup():
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(_setup())


def pytest_unconfigure(config):
    """Drop all tables after all tests finish."""

    async def _teardown():
        engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    asyncio.run(_teardown())


# ---------------------------------------------------------------------------
# Autouse truncation — runs BEFORE each test via synchronous psql
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def truncate_tables():
    """Truncate all data tables before every test so each starts clean."""
    _psql(_TRUNCATE_SQL)
    yield
    # (no teardown needed — next test's setup does the truncate)


# ---------------------------------------------------------------------------
# Per-test DB session (NullPool — fresh connection per fixture call)
# ---------------------------------------------------------------------------


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Direct DB session for seeding data. NOT shared with the app.

    The session is opened fresh with NullPool. Teardown errors from asyncpg
    (event-loop mismatch on close) are suppressed — data isolation is handled
    by the autouse truncate_tables fixture.
    """
    engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        try:
            await session.close()
        except Exception:
            pass  # Suppress asyncpg teardown loop errors; psql truncate handles isolation
        try:
            await engine.dispose()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# HTTP test client — app wired to test DB
# ---------------------------------------------------------------------------


@pytest.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """HTTP client. The app uses test DB connections via dependency override."""
    test_engine = create_async_engine(TEST_DB_URL, poolclass=NullPool)
    test_factory = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)

    async def _get_test_db() -> AsyncGenerator[AsyncSession, None]:
        async with test_factory() as session:
            yield session

    app.dependency_overrides[get_db] = _get_test_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
    await test_engine.dispose()


# ---------------------------------------------------------------------------
# Auth fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def auth_headers(db_session: AsyncSession) -> dict[str, str]:
    """Seed a test user and return Bearer JWT headers."""
    user = User(email="testuser@example.com", hashed_password=hash_password("testpassword"))
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(subject="testuser@example.com")
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Constraint profile seed
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_profiles(db_session: AsyncSession) -> list[ConstraintProfile]:
    """Insert the 3 platform constraint profiles into the test DB."""
    profiles = [
        ConstraintProfile(
            platform_key="discord",
            max_length=2000,
            tone_rules={"style": "casual", "emojis": True, "cta": True},
            max_hashtags=0,
        ),
        ConstraintProfile(
            platform_key="instagram",
            max_length=2200,
            tone_rules={"style": "visual", "emojis": True, "cta": True},
            max_hashtags=30,
        ),
        ConstraintProfile(
            platform_key="linkedin",
            max_length=3000,
            tone_rules={"style": "professional", "emojis": False, "cta": True},
            max_hashtags=5,
        ),
    ]
    db_session.add_all(profiles)
    await db_session.commit()
    return profiles
