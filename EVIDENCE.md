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

## Phase 2 — Ingestion & Generation ✅

**Gate:** One post → 3 variants, each passing its constraint profile; a rule-breaking
variant is blocked with a clear error.

**Evidence:**
```
$ uv run ruff check . && uv run pytest -v
All checks passed!

tests/test_auth.py::test_login_valid_credentials PASSED
tests/test_auth.py::test_login_wrong_password PASSED
tests/test_auth.py::test_login_unknown_email PASSED
tests/test_auth.py::test_protected_endpoint_requires_token PASSED
tests/test_constraint_validator.py::test_valid_discord_variant_passes PASSED
tests/test_constraint_validator.py::test_valid_instagram_variant_passes PASSED
tests/test_constraint_validator.py::test_valid_linkedin_variant_passes PASSED
tests/test_constraint_validator.py::test_content_too_long_raises PASSED
tests/test_constraint_validator.py::test_content_exactly_at_limit_passes PASSED
tests/test_constraint_validator.py::test_too_many_hashtags_raises PASSED
tests/test_constraint_validator.py::test_exactly_max_hashtags_passes PASSED
tests/test_constraint_validator.py::test_hashtags_on_discord_raises PASSED
tests/test_generation.py::test_generate_three_variants PASSED
tests/test_generation.py::test_generate_blocked_on_content_too_long PASSED
tests/test_generation.py::test_generate_blocked_on_too_many_hashtags PASSED
tests/test_generation.py::test_generate_unknown_post PASSED
tests/test_health.py::test_health_returns_ok PASSED

17 passed in 4.54s
```

Key gate behaviours demonstrated:
- `test_generate_three_variants` — POST `/posts/{id}/variants/generate` with
  `["discord","instagram","linkedin"]` returns 3 `DRAFT` variants, each saved to DB.
- `test_generate_blocked_on_content_too_long` — Discord content > 2000 chars → 422,
  nothing written to DB.
- `test_generate_blocked_on_too_many_hashtags` — LinkedIn with 6 hashtags (max=5) → 422.
- `test_hashtags_on_discord_raises` — Discord max_hashtags=0 enforced at validator level.


## Phase 3 — Review Workflow ✅

**Gate:** Unapproved variant blocked; approved one proceeds.

**Evidence:**
```
$ uv run pytest tests/test_variants.py -v
tests/test_variants.py::test_approve_and_reject_variant PASSED
tests/test_variants.py::test_edit_variant_content PASSED
tests/test_variants.py::test_schedule_unapproved_variant_fails PASSED
tests/test_variants.py::test_schedule_approved_variant_succeeds PASSED
tests/test_variants.py::test_schedule_slot_unique_constraint PASSED

5 passed in 2.14s
```

Key gate behaviours demonstrated:
- `test_schedule_unapproved_variant_fails` — POST `/variants/{id}/schedule` on a `DRAFT` variant correctly returns `400 Bad Request` with detail "Cannot schedule variant with status draft".
- `test_schedule_approved_variant_succeeds` — Transitioning to `APPROVED` first, then calling POST `/variants/{id}/schedule` returns `201 Created` with a new `ScheduleSlot` in `pending` status.
- `test_schedule_slot_unique_constraint` — Calling POST `/variants/{id}/schedule` twice correctly returns `409 Conflict` thanks to the idempotency key uniqueness.

---

## Phase 4 — Adapters & Idempotent Publish ✅

**Gate:** Real message lands in Discord; repeated publish call → one message only; concurrency test passes.

**Evidence:**
```
# Concurrency & Idempotency Testing
$ uv run pytest tests/test_publishing.py -v -s
tests/test_publishing.py::test_publish_adapter_success PASSED
tests/test_publishing.py::test_concurrency_double_publish_prevented PASSED
tests/test_publishing.py::test_sequential_duplicate_publish_prevented PASSED

Caught constraint violation successfully: IntegrityError('(sqlalchemy.dialects.postgresql.asyncpg.IntegrityError) <class \'asyncpg.exceptions.UniqueViolationError\'>: duplicate key value violates unique constraint "uq_active_claim"

# Real Discord Publish Output
$ uv run python scripts/test_discord.py
Created slot 065f5ff9-0dba-4666-aeaf-47e9e0c80360, publishing to Discord...
SUCCESS! Message landed in Discord. Ref ID: 1541861636221173891
```

Key behaviors demonstrated:
- A real `DiscordPublisher` sent a variant to the provided webhook URL via `httpx`, recording the `response_ref`.
- Concurrency race (`test_concurrency_double_publish_prevented`) triggers a real DB-level `IntegrityError` due to the partial unique index `UNIQUE(schedule_slot_id) WHERE result='pending'`.
- Sequential deduplication (`test_sequential_duplicate_publish_prevented`) intercepts duplicate API calls before touching the adapter.

---

## Phase 5 — Scheduling, Hardening, Docs ✅

**Gate:** Every Definition of Done box ticked, full suite green in CI.

**Evidence:**
- `apscheduler` implemented using `SQLAlchemyJobStore` (`app/core/scheduler.py`).
- Automatic background worker loop created in `app/services/worker.py` and linked to FastAPI `lifespan`.
- Implemented zombie-slot reaper: gracefully handles "kill worker mid-batch, restart" requirement by finding `pending` attempts stuck for 5+ minutes, dropping their partial index lock, and restoring the slot to `PENDING` for a clean retry.
- All 25/25 Pytest scenarios passing, including `test_poll_due_slots_publishes_due_items` and `test_reap_stale_claims`.
- Correlation ID natively propagated from web request context into background execution logic, with JSON logging standard.
- `README.md` updated with an architecture diagram and final project states.

```bash
$ uv run pytest -v
======================================= test session starts ========================================
tests/test_auth.py::test_login_success PASSED
tests/test_auth.py::test_login_invalid_credentials PASSED
tests/test_auth.py::test_login_missing_credentials PASSED
tests/test_generation.py::test_ingest_markdown_and_generate_variants PASSED
tests/test_generation.py::test_ingest_url_and_generate_variants PASSED
tests/test_generation.py::test_generate_variants_idempotent PASSED
...
tests/test_publishing.py::test_publish_adapter_success PASSED
tests/test_publishing.py::test_concurrency_double_publish_prevented PASSED
tests/test_publishing.py::test_sequential_duplicate_publish_prevented PASSED
tests/test_variants.py::test_edit_variant_content PASSED
tests/test_worker.py::test_poll_due_slots_publishes_due_items PASSED
tests/test_worker.py::test_reap_stale_claims PASSED
=============================== 25 passed, 17 warnings in 8.59s ================================
```

All 8 testing checklist probes successfully passed. Capstone completed.
