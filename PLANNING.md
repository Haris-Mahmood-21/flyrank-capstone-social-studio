# Social Media Studio — Capstone Planning

FlyRank Internship · Backend Track · Capstone
**Owner:** Haris | **Repo name:** `flyrank-capstone-social-studio`

---

## 1. Project Summary

Turn one blog post into a scheduled, multi-platform social campaign. The system generates
platform-specific variants, enforces per-platform constraint profiles, routes each variant
through a human review workflow, and publishes approved variants exactly once — even under
retries, crashes, and concurrent workers.

**The grade lives in reliability, not features.** Idempotency, durable scheduling, and clean
adapter architecture matter more than platform count or UI polish.

---

## 2. Instructions for the coding agent (read this first)

This file is the spec. Follow it exactly — do not silently swap a library, pattern, or
architectural decision listed here for "a better one." If something in this file seems
wrong or you think a different approach is better, **stop and state the assumption/
suggestion explicitly and wait for confirmation** before proceeding. Never change an
architectural decision without flagging it.

**Working rules:**
- All code, comments, variable names, docstrings, commit messages → **English only**.
  Conversation with me can be Roman Urdu, but nothing in the codebase.
- macOS + `uv` only. Do not suggest pip/venv/poetry/conda commands.
- **One phase at a time.** Finish Phase N, hit its Gate, commit, then stop and report
  what was done before starting Phase N+1. Do not jump ahead or work on two phases at once.
- After finishing each module/file, do a short self-review pass (does it match the spec
  in this file? are there obvious edge cases missed?) before moving on.
- Before writing any code for a step, state your plan/assumptions for that step in 2-4
  bullet points, then proceed.
- Idempotency must be enforced at the **database level** (unique constraint), not only
  in application logic — this is non-negotiable, it is the core of the grade.
- Keep scope exactly as defined in this file. Do not add features, endpoints, or
  abstractions beyond what's listed, even if they seem like natural extensions. If you
  think something should be added, ask first.
- Every phase Gate (see Section 6) must be demonstrably met — a passing test, a working
  curl call, or a log line — before moving to the next phase.

---

## 3. Environment Variables

These go in `.env` (git-ignored) with placeholders mirrored in `.env.example`:

```
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/social_studio
JWT_SECRET=changeme-generate-a-real-secret
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=60
GEMINI_API_KEY=your-gemini-free-tier-key
DISCORD_WEBHOOK_URL=your-discord-webhook-url
LOG_LEVEL=INFO
ENVIRONMENT=development
```

---

## 4. Confirmed Tech Stack

| Layer | Choice | Why |
|---|---|---|
| Language / framework | Python 3.12+ / FastAPI (async) | Async I/O for DB, webhooks, external calls |
| ORM | SQLAlchemy 2.0 (async) + asyncpg | Modern async standard |
| Database | PostgreSQL via Docker | Production-like, not SQLite |
| Migrations | Alembic | Proper schema versioning, no raw `CREATE TABLE` |
| Scheduler | APScheduler + SQLAlchemy persistent job store | Durable, survives restarts, no extra broker needed |
| Real publish target | Discord Webhook | Simplest real integration, no OAuth friction |
| Mock adapters | Instagram, LinkedIn (self-written) | Prove adapter pattern without real API access |
| AI (variant text) | Gemini free tier | Free, no card |
| Auth | JWT | Matches your SecureRAG/NL2SQL pattern |
| Logging | Structured JSON logs + correlation ID | Debuggable publish history, production habit |
| Testing | pytest + pytest-asyncio | Async-compatible test suite |
| Lint / format / types | Ruff + mypy + pre-commit | Standard 2026 Python hygiene |
| CI | GitHub Actions | Tests green on every push |
| Package manager | uv | Per your established rule |
| Secrets | `.env` + `.env.example` | Never committed |
| Deployment | Local only (`docker compose up`) | No hosting required |

**Stretch goals included:** Cost tracking per campaign (Gemini call cost logged), Grounding
check (flag variants containing claims not present in the source post).

**Explicitly out of scope:** Image generation, analytics/engagement tracking, multi-tenant,
A/B variant testing, real Instagram/X/LinkedIn accounts, deployment to a hosting provider.

---

## 5. Data Model

```
users
 ├─ id (PK)
 ├─ email (unique)
 ├─ hashed_password
 └─ created_at

posts
 ├─ id (PK)
 ├─ source_type (url | markdown)
 ├─ source_ref (the URL, or null)
 ├─ raw_content (the stored markdown — single source of truth)
 ├─ title
 └─ created_at

constraint_profiles
 ├─ id (PK)
 ├─ platform_key (discord | instagram | linkedin)
 ├─ max_length
 ├─ tone_rules (json)
 └─ max_hashtags

variants
 ├─ id (PK)
 ├─ post_id (FK -> posts)
 ├─ platform_key
 ├─ content (generated text)
 ├─ hashtags (json array)
 ├─ status (draft | approved | rejected | published)
 ├─ ai_generated (bool)
 ├─ ai_cost_usd (nullable — stretch goal)
 ├─ grounding_flags (json, nullable — stretch goal)
 ├─ created_at
 └─ updated_at

schedule_slots
 ├─ id (PK)
 ├─ variant_id (FK -> variants, unique)
 ├─ scheduled_for (timestamp)
 ├─ idempotency_key (unique — variant_id + slot, the core of the grade)
 └─ status (pending | claimed | done | failed)

publish_attempts
 ├─ id (PK)
 ├─ schedule_slot_id (FK -> schedule_slots)
 ├─ adapter_name (discord | mock_instagram | mock_linkedin)
 ├─ attempt_number
 ├─ result (success | failure)
 ├─ response_ref (message ID / mock preview ref)
 ├─ error_detail (nullable)
 └─ attempted_at
```

Key correctness rule baked into the schema: `schedule_slots.idempotency_key` is **unique at
the DB level** — not just checked in application code. This is what makes the concurrency
test (two workers, same slot) provably correct instead of "probably correct."

---

## 6. API Surface (draft)

```
POST   /auth/login                      → JWT
POST   /posts                           → ingest (url or markdown)
GET    /posts/{id}

POST   /posts/{id}/variants/generate    → generate variants for given platforms
GET    /variants/{id}
PATCH  /variants/{id}                   → edit content
POST   /variants/{id}/approve
POST   /variants/{id}/reject

POST   /variants/{id}/schedule          → create schedule_slot (requires approved)
GET    /schedule                        → upcoming slots

GET    /publish-history                 → all attempts, filterable by variant/platform
```

All endpoints except `/auth/login` require a valid JWT. All mutating endpoints validate
input and return honest 4xx codes on bad input — never a 500 for a client error.

---

## 7. Adapter Interface (sketch)

```python
class SocialPublisher(Protocol):
    async def publish(self, variant: Variant, idempotency_key: str) -> PublishResult:
        ...

class DiscordPublisher:      # real
class MockInstagramPublisher: # records to DB, returns fake preview
class MockLinkedInPublisher:  # records to DB, returns fake preview
```

Business logic (scheduler, review workflow) depends only on `SocialPublisher`. Swapping
`discord` → `mock_instagram` for a given platform_key is a config change, never a code change.
This is proven by a test, not just claimed in the README.

---

## 8. Build Phases

### Phase 0 — Project scaffolding (~half day)
- `uv` project init, FastAPI skeleton, Docker Compose (Postgres), Alembic init
- Ruff + mypy + pre-commit configured
- GitHub Actions workflow stub (lint + test on push)
- **Gate:** `docker compose up` boots an empty FastAPI app; CI runs green on an empty test.

### Phase 1 — Design (as required by brief)
- Constraint profiles per platform (length, tone, hashtags) written down
- `SocialPublisher` interface signature finalized
- Data model finalized (above)
- One explicit non-goal written in README
- **Gate:** One-page design doc committed. *(Optional: send to mentor for review per their offer.)*

### Phase 2 — Ingestion & generation
- JWT auth (login only, single user is fine)
- `POST /posts` — URL fetch or pasted markdown, stored
- Variant generator for 3 platforms (Gemini-backed), constraint validation enforced
- Cost tracking hook on every Gemini call (stretch goal, cheap to add now)
- **Gate:** One post → 3 variants, each passing its constraint profile; a rule-breaking
  variant is blocked with a clear error.

### Phase 3 — Review workflow
- Status transitions: draft → approved/rejected
- Grounding check on approval (stretch goal): flag content not traceable to source post
- Unapproved variant cannot be scheduled — clean 4xx
- **Gate:** Unapproved variant blocked; approved one proceeds.

### Phase 4 — Adapters & idempotent publish (heart of the grade)
- `SocialPublisher` interface + Discord real adapter + 2 mock adapters
- Idempotency key enforced at DB level (unique constraint), not just app-level check
- **Concurrency test:** two async workers attempt the same slot simultaneously →
  exactly one publish_attempt succeeds, proven with a real DB constraint, not a lock in memory
- **Gate:** Real message lands in Discord; repeated publish call → one message only;
  concurrency test passes.

### Phase 5 — Scheduling, hardening, docs
- APScheduler with SQLAlchemy job store; worker picks up due slots
- Kill worker mid-batch, restart, prove zero duplicates
- Structured JSON logging with correlation ID across ingest → generate → publish
- Full pytest suite: blocked variant, refused schedule, duplicate publish, concurrent
  publish, adapter swap, forged/invalid input
- README + architecture diagram + EVIDENCE.md + BUILDLOG.md
- **Gate:** Every Definition of Done box ticked, full suite green in CI.

---

## 9. Testing Checklist (maps to grading probes)

- [ ] Ingest post → variants generated → each passes constraint profile
- [ ] Rule-breaking variant blocked before reaching review
- [ ] Unapproved variant → schedule request refused (4xx)
- [ ] Approved variant → scheduled → published to real Discord target
- [ ] Publish retry after simulated timeout → exactly one message (idempotency)
- [ ] **Two concurrent publish attempts on the same slot → exactly one succeeds (DB-level)**
- [ ] Worker killed mid-batch, restarted → zero duplicates
- [ ] Adapter swapped via config (discord → mock_instagram) → zero code changes needed
- [ ] (Stretch) Planted fake claim in a variant → grounding check flags it
- [ ] (Stretch) Every Gemini call → cost entry logged, visible per campaign

---

## 10. Folder Structure (proposed)

```
flyrank-capstone-social-studio/
├── app/
│   ├── api/                # FastAPI routers
│   ├── core/                # config, security, logging setup
│   ├── models/              # SQLAlchemy models
│   ├── schemas/              # Pydantic schemas
│   ├── services/              # business logic (generation, review, scheduling)
│   ├── adapters/              # SocialPublisher implementations
│   └── main.py
├── alembic/
├── tests/
├── .github/workflows/ci.yml
├── docker-compose.yml
├── .env.example
├── README.md
├── EVIDENCE.md
├── BUILDLOG.md
└── pyproject.toml
```

---

## 11. Open Items for Later

- Decide exact Gemini prompt/template split per platform in Phase 2
- Confirm Discord server + webhook URL before Phase 4
