# Evidence Log

Gate proof for each phase of the Social Media Studio capstone.

---

## Phase 0 — Scaffolding ✅

**Gate:** `docker compose up` boots an empty FastAPI app; CI runs green on an empty test.

**Evidence:**
```
$ uv run pytest -v
tests/test_health.py::test_health_returns_ok PASSED  [100%]
1 passed in 0.15s

$ uv run ruff check .
All checks passed!
```

Commit: `cbb6f06` — Phase 0: project scaffolding

---

## Phase 1 — Design ✅

**Gate:** One-page design doc committed.

**Evidence:**
- `DESIGN.md` committed — covers constraint profiles, `SocialPublisher` Protocol,
  finalized data model, request/response flow, key architecture decisions.
- `README.md` committed — includes explicit Non-Goals section.
- `app/adapters/base.py` committed — `SocialPublisher` Protocol + `PublishResult`
  dataclass, fully docstringed, ready for Phase 4 implementations.

---

## Phase 2 — Ingestion & Generation 🔜

---

## Phase 3 — Review Workflow 🔜

---

## Phase 4 — Adapters & Idempotent Publish 🔜

---

## Phase 5 — Scheduling, Hardening, Docs 🔜
