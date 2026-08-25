"""
Unit tests for the constraint validator.

No database or Gemini API required — pure logic tests.
These prove the Gate requirement: a rule-breaking variant is blocked.

We use a simple stub instead of instantiating the ORM model so we don't
need SQLAlchemy's mapper registry (and thus no DB connection) in these tests.
"""

from dataclasses import dataclass, field

import pytest

from app.services.generation import ConstraintViolationError, validate_against_profile


@dataclass
class _ProfileStub:
    """Minimal stand-in for ConstraintProfile — no SQLAlchemy involved."""

    platform_key: str
    max_length: int
    max_hashtags: int
    tone_rules: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_valid_discord_variant_passes() -> None:
    """Content within Discord limits passes without error."""
    profile = _ProfileStub("discord", max_length=2000, max_hashtags=0)
    validate_against_profile("Short post.", [], profile)  # must not raise


def test_valid_instagram_variant_passes() -> None:
    profile = _ProfileStub("instagram", max_length=2200, max_hashtags=30)
    hashtags = [f"tag{i}" for i in range(10)]
    validate_against_profile("Great photo!", hashtags, profile)


def test_valid_linkedin_variant_passes() -> None:
    profile = _ProfileStub("linkedin", max_length=3000, max_hashtags=5)
    validate_against_profile("Exciting news in our industry.", ["innovation"], profile)


# ---------------------------------------------------------------------------
# Violation: content too long
# ---------------------------------------------------------------------------


def test_content_too_long_raises() -> None:
    profile = _ProfileStub("discord", max_length=100, max_hashtags=0)
    long_content = "x" * 101
    with pytest.raises(ConstraintViolationError, match="max_length=100"):
        validate_against_profile(long_content, [], profile)


def test_content_exactly_at_limit_passes() -> None:
    profile = _ProfileStub("discord", max_length=100, max_hashtags=0)
    validate_against_profile("x" * 100, [], profile)  # must not raise


# ---------------------------------------------------------------------------
# Violation: too many hashtags
# ---------------------------------------------------------------------------


def test_too_many_hashtags_raises() -> None:
    profile = _ProfileStub("linkedin", max_length=3000, max_hashtags=5)
    hashtags = [f"tag{i}" for i in range(6)]
    with pytest.raises(ConstraintViolationError, match="max_hashtags=5"):
        validate_against_profile("Some content.", hashtags, profile)


def test_exactly_max_hashtags_passes() -> None:
    profile = _ProfileStub("linkedin", max_length=3000, max_hashtags=5)
    hashtags = [f"tag{i}" for i in range(5)]
    validate_against_profile("Some content.", hashtags, profile)


# ---------------------------------------------------------------------------
# Violation: hashtags on a no-hashtag platform (Discord)
# ---------------------------------------------------------------------------


def test_hashtags_on_discord_raises() -> None:
    profile = _ProfileStub("discord", max_length=2000, max_hashtags=0)
    with pytest.raises(ConstraintViolationError, match="not allowed"):
        validate_against_profile("Nice post!", ["foo"], profile)
