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


## Phase 3 — Review Workflow 🔜

---

## Phase 4 — Adapters & Idempotent Publish 🔜

---

## Phase 5 — Scheduling, Hardening, Docs 🔜
