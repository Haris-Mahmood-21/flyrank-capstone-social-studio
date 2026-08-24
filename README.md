# Social Media Studio

**FlyRank Internship · Backend Track · Capstone**

Turn one blog post into a scheduled, multi-platform social campaign.
The system generates platform-specific content variants, enforces per-platform constraint
profiles, routes each variant through a human review workflow, and publishes approved
variants **exactly once** — even under retries, crashes, and concurrent workers.

---

## Quick Start

```bash
# 1. Copy env and fill in your keys
cp .env.example .env

# 2. Start Postgres
docker compose up db -d

# 3. Run migrations
uv run alembic upgrade head

# 4. Start the API
uv run uvicorn app.main:app --reload
```

API docs available at http://localhost:8000/docs

---

## Tech Stack

| Layer | Choice |
|---|---|
| Language / framework | Python 3.12 / FastAPI (async) |
| ORM | SQLAlchemy 2.0 (async) + asyncpg |
| Database | PostgreSQL 16 (Docker) |
| Migrations | Alembic |
| Scheduler | APScheduler + SQLAlchemy job store |
| AI (variant text) | Gemini free tier |
| Real publish target | Discord Webhook |
| Mock adapters | Instagram, LinkedIn |
| Auth | JWT (HS256) |
| Package manager | uv |

---

## Non-Goals

> This section is required by the project brief and intentionally kept narrow.

**This project does not support image generation.**
All content produced by Social Media Studio is text-only. There are no plans to add
image generation, editing, or attachment support. Any variant that requires an image
for its platform must be handled outside this system.

Additional items explicitly out of scope (not planned as stretch goals):
- Real Instagram, X, or LinkedIn API credentials / OAuth flows
- Analytics or engagement tracking after publish
- Multi-tenant user management
- A/B variant testing
- Deployment to any hosting provider (local Docker only)

---

## Project Structure

```
app/
├── api/          FastAPI routers
├── core/         Config, security, logging, database session
├── models/       SQLAlchemy ORM models
├── schemas/      Pydantic request/response schemas
├── services/     Business logic (generation, review, scheduling)
├── adapters/     SocialPublisher implementations
└── main.py

alembic/          Migration scripts
tests/            pytest suite
.github/
└── workflows/
    └── ci.yml    Lint + test on every push
```

---

## Design

See [DESIGN.md](./DESIGN.md) for:
- Platform constraint profiles (length, tone, hashtags)
- `SocialPublisher` Protocol interface (finalized)
- Full data model
- Request/response flow
- Key architecture decisions

---

## Build Phases

| Phase | Focus | Status |
|---|---|---|
| 0 | Scaffolding | ✅ Done |
| 1 | Design doc | ✅ Done |
| 2 | Ingestion & generation | 🔜 |
| 3 | Review workflow | 🔜 |
| 4 | Adapters & idempotent publish | 🔜 |
| 5 | Scheduling, hardening, docs | 🔜 |

---

## Evidence & Build Log

- [EVIDENCE.md](./EVIDENCE.md) — Gate proof for each phase
- [BUILDLOG.md](./BUILDLOG.md) — Chronological build notes
