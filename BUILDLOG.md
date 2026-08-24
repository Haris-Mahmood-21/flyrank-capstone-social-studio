# Build Log

Chronological notes for each phase.

---

## 2026-08-25 — Phase 0

- Initialized `uv` project (Python 3.12)
- Installed 41 runtime packages + 22 dev packages
- Created folder structure: `app/{api,core,models,schemas,services,adapters}`, `tests/`, `.github/workflows/`
- Built FastAPI skeleton with `/health` endpoint and modern `lifespan` handler
- Set up structured JSON logging with correlation ID `ContextVar`
- Configured async SQLAlchemy engine + `get_db` dependency
- Initialized Alembic with async-compatible `env.py`
- Wrote `docker-compose.yml` (Postgres 16 + app, healthcheck)
- Wrote `Dockerfile` using `uv`
- Configured `ruff` + `mypy` in `pyproject.toml`
- Added `.pre-commit-config.yaml` (ruff + mypy hooks)
- Added GitHub Actions CI (lint + pytest on every push, with Postgres service)
- Gate: `pytest -v` → 1 passed, `ruff check` → all checks passed

---

## 2026-08-25 — Phase 1

- Wrote `DESIGN.md` — constraint profiles table (Discord/Instagram/LinkedIn),
  finalized `SocialPublisher` Protocol with `PublishResult` dataclass,
  full data model with types and constraints, request/response flow diagram,
  key architecture decisions table
- Wrote `README.md` — project overview, quick start, tech stack, explicit Non-Goals section
- Created `app/adapters/base.py` — `SocialPublisher` Protocol + `PublishResult` dataclass
  (the contract all Phase 4 adapters must implement)
- Created `EVIDENCE.md` and `BUILDLOG.md`
- Gate: design doc committed with all required sections
