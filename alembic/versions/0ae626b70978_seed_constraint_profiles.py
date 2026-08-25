"""seed_constraint_profiles

Revision ID: 0ae626b70978
Revises: 09905702f04a
Create Date: 2026-08-25

Insert the three canonical platform constraint profiles:
  - discord   (max 2000 chars, 0 hashtags, casual)
  - instagram (max 2200 chars, 30 hashtags, visual)
  - linkedin  (max 3000 chars, 5 hashtags, professional)
"""

import json
import uuid

import sqlalchemy as sa

from alembic import op

revision: str = "0ae626b70978"
down_revision: str = "09905702f04a"
branch_labels = None
depends_on = None

_PROFILES = [
    {
        "id": str(uuid.uuid4()),
        "platform_key": "discord",
        "max_length": 2000,
        "tone_rules": json.dumps({"style": "casual", "emojis": True, "cta": True}),
        "max_hashtags": 0,
    },
    {
        "id": str(uuid.uuid4()),
        "platform_key": "instagram",
        "max_length": 2200,
        "tone_rules": json.dumps({"style": "visual", "emojis": True, "cta": True}),
        "max_hashtags": 30,
    },
    {
        "id": str(uuid.uuid4()),
        "platform_key": "linkedin",
        "max_length": 3000,
        "tone_rules": json.dumps({"style": "professional", "emojis": False, "cta": True}),
        "max_hashtags": 5,
    },
]

_INSERT = sa.text(
    "INSERT INTO constraint_profiles (id, platform_key, max_length, tone_rules, max_hashtags) "
    "VALUES (:id, :platform_key, :max_length, CAST(:tone_rules AS jsonb), :max_hashtags) "
    "ON CONFLICT (platform_key) DO NOTHING"
)


def upgrade() -> None:
    conn = op.get_bind()
    for profile in _PROFILES:
        conn.execute(_INSERT, profile)


def downgrade() -> None:
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "DELETE FROM constraint_profiles "
            "WHERE platform_key IN ('discord', 'instagram', 'linkedin')"
        )
    )
