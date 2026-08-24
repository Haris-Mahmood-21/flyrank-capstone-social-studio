# Social Media Studio — Design Document

**Phase 1 artifact** | FlyRank Internship Capstone · Backend Track

---

## 1. Constraint Profiles

Each platform has a constraint profile stored in the `constraint_profiles` table and enforced
by the variant generator **before** a variant is written to the database.
A variant that violates its profile is rejected with a `422` and never saved.

| Platform | `platform_key` | `max_length` (chars) | `max_hashtags` | Tone rules |
|---|---|---|---|---|
| Discord | `discord` | 2 000 | 0 | casual, emojis allowed, CTA encouraged |
| Instagram | `instagram` | 2 200 | 30 | visual/lifestyle, emojis allowed, strong CTA |
| LinkedIn | `linkedin` | 3 000 | 5 | professional, no emojis, thought-leadership tone |

### Tone rule JSON schema (stored in `constraint_profiles.tone_rules`)

```json
{
  "style":  "casual | visual | professional",
  "emojis": true | false,
  "cta":    true | false
}
```

The Gemini prompt for each platform injects these rules as system instructions so the
generated text already targets the right tone. The constraint validator then checks character
length and hashtag count mechanically — no LLM needed for enforcement.

---

## 2. SocialPublisher Interface (finalized)

```python
from typing import Protocol
from dataclasses import dataclass


@dataclass
class PublishResult:
    success: bool
    adapter_name: str  # "discord" | "mock_instagram" | "mock_linkedin"
    response_ref: str | None  # message ID, mock preview ref, etc.
    error_detail: str | None  # populated on failure


class SocialPublisher(Protocol):
    """
    Adapter contract for all social publishing targets.

    Every implementation must be idempotency-safe: if called twice with the
    same idempotency_key it MUST NOT publish a second time. The DB unique
    constraint on schedule_slots.idempotency_key is the backstop, but
    adapters should also short-circuit on duplicate keys where possible.
    """

    @property
    def platform_key(self) -> str:
        """The platform_key string this adapter handles (e.g. 'discord')."""
        ...

    async def publish(
        self,
        variant: "Variant",  # app.models.Variant ORM object
        idempotency_key: str,
    ) -> PublishResult:
        """
        Publish variant content to the target platform exactly once.

        Args:
            variant:         The approved Variant ORM record to publish.
            idempotency_key: Globally unique key for this publish attempt
                             (= schedule_slots.idempotency_key).

        Returns:
            PublishResult with success=True and a response_ref on success,
            or success=False and an error_detail on failure.

        Raises:
            Nothing. All exceptions must be caught and returned as
            PublishResult(success=False, error_detail=...).
        """
        ...
```

### Adapter implementations planned

| Class | Module | Target | Notes |
|---|---|---|---|
| `DiscordPublisher` | `app/adapters/discord.py` | Real Discord webhook | Phase 4 |
| `MockInstagramPublisher` | `app/adapters/mock_instagram.py` | Writes fake preview to DB | Phase 4 |
| `MockLinkedInPublisher` | `app/adapters/mock_linkedin.py` | Writes fake preview to DB | Phase 4 |

**Adapter registry** (in `app/adapters/__init__.py`): a dict mapping `platform_key → SocialPublisher`.
Swapping `discord` → `mock_instagram` for a given platform_key is a config change, never a code change.

---

## 3. Data Model (finalized)

```
users
 ├─ id            UUID PK
 ├─ email         VARCHAR UNIQUE NOT NULL
 ├─ hashed_password VARCHAR NOT NULL
 └─ created_at    TIMESTAMPTZ DEFAULT now()

posts
 ├─ id            UUID PK
 ├─ source_type   VARCHAR  CHECK IN ('url', 'markdown')
 ├─ source_ref    VARCHAR  NULLABLE  (the URL, or null for pasted markdown)
 ├─ raw_content   TEXT NOT NULL      (stored markdown — single source of truth)
 ├─ title         VARCHAR NOT NULL
 └─ created_at    TIMESTAMPTZ DEFAULT now()

constraint_profiles
 ├─ id            UUID PK
 ├─ platform_key  VARCHAR UNIQUE NOT NULL  CHECK IN ('discord','instagram','linkedin')
 ├─ max_length    INTEGER NOT NULL
 ├─ tone_rules    JSONB NOT NULL
 └─ max_hashtags  INTEGER NOT NULL

variants
 ├─ id            UUID PK
 ├─ post_id       UUID FK → posts(id)
 ├─ platform_key  VARCHAR NOT NULL
 ├─ content       TEXT NOT NULL
 ├─ hashtags      JSONB NOT NULL          (array of strings, no '#' prefix)
 ├─ status        VARCHAR DEFAULT 'draft' CHECK IN ('draft','approved','rejected','published')
 ├─ ai_generated  BOOLEAN DEFAULT TRUE
 ├─ ai_cost_usd   NUMERIC(12,8) NULLABLE  (stretch: Gemini token cost)
 ├─ grounding_flags JSONB NULLABLE        (stretch: flagged claims)
 ├─ created_at    TIMESTAMPTZ DEFAULT now()
 └─ updated_at    TIMESTAMPTZ DEFAULT now()

schedule_slots
 ├─ id            UUID PK
 ├─ variant_id    UUID FK → variants(id) UNIQUE   (one slot per variant)
 ├─ scheduled_for TIMESTAMPTZ NOT NULL
 ├─ idempotency_key VARCHAR UNIQUE NOT NULL        ← DB-level uniqueness enforced here
 └─ status        VARCHAR DEFAULT 'pending' CHECK IN ('pending','claimed','done','failed')

publish_attempts
 ├─ id            UUID PK
 ├─ schedule_slot_id UUID FK → schedule_slots(id)
 ├─ adapter_name  VARCHAR NOT NULL
 ├─ attempt_number INTEGER NOT NULL
 ├─ result        VARCHAR NOT NULL  CHECK IN ('success','failure')
 ├─ response_ref  VARCHAR NULLABLE
 ├─ error_detail  TEXT NULLABLE
 └─ attempted_at  TIMESTAMPTZ DEFAULT now()
```

### Idempotency key construction

```
idempotency_key = f"{variant_id}:{scheduled_for.isoformat()}"
```

This key is built at schedule time and stored with a `UNIQUE` constraint in Postgres.
Any second `INSERT` with the same key raises `UniqueViolationError` at the DB level —
not caught silently in application code — proving exactly-once publish under concurrency.

---

## 4. Request / Response Flow

```
POST /posts  →  ingest (URL fetch or markdown)
                      │
POST /posts/{id}/variants/generate
                      │
               Gemini API call (per platform)
               ↓
               constraint_validator (length, hashtags)
               ↓
               variants saved (status=draft)
                      │
POST /variants/{id}/approve   (status: draft → approved)
POST /variants/{id}/reject    (status: draft → rejected)
                      │
POST /variants/{id}/schedule  (requires status=approved)
               ↓
               schedule_slots row inserted
               idempotency_key set + UNIQUE constraint enforced
                      │
APScheduler worker polls schedule_slots WHERE status='pending' AND scheduled_for <= now()
               ↓
               claims slot (UPDATE status='claimed')
               ↓
               SocialPublisher.publish(variant, idempotency_key)
               ↓
               publish_attempts row inserted
               ↓
               UPDATE schedule_slots.status = 'done' | 'failed'
               UPDATE variants.status = 'published'
```

---

## 5. Key Architecture Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Idempotency enforcement | DB-level UNIQUE constraint | Cannot be bypassed by concurrency or bugs in application logic |
| Adapter coupling | `SocialPublisher` Protocol | Business logic never imports a concrete adapter; swap = config change |
| Scheduling | APScheduler + SQLAlchemy job store | Durable across restarts; no extra broker (Redis/RabbitMQ) needed |
| Auth scope | Single-user JWT (login only) | Capstone scope; multi-tenant explicitly out of scope |
| Variant constraint check | Pre-save validation, 422 on violation | Rule-breaking variant never reaches the DB |
| Grounding check | Post-approval, flags only | Does not block publish; surfaces information to reviewer |

---

## 6. Explicit Non-Goals

See `README.md` § Non-Goals for the single mandated non-goal statement.
Full out-of-scope list: image generation, analytics/engagement tracking, multi-tenant,
A/B variant testing, real Instagram/X/LinkedIn API accounts, deployment to a hosting provider.
