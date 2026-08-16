# Relay — Implementation Ledger

Running record of what was built, decided, executed, and verified. Never claims
functionality that has not been run.

---

## Phase 0 — Repository & Execution Foundation ✅ (green)

**Date:** 2026-08-16

### Files added
- `pyproject.toml` — uv/hatchling project; pinned deps; ruff/mypy/pytest/import-linter config.
- `src/relay/__init__.py`, subpackage `__init__` for `core`, `ai`, `notifications`, `api`, `worker`.
- `src/relay/config.py` — typed `Settings` (pydantic-settings), dev/test/prod enum, fail-fast production secret validation, psycopg sync-URL derivation.
- `src/relay/logging.py` — structlog config (JSON/console), contextvar request-id binding.
- `src/relay/db/base.py` — declarative `Base`, deterministic naming convention, `TimestampMixin`, `uuid_pk`.
- `src/relay/db/session.py` — sync engine, `SessionLocal`, `session_scope`, `sessionmaker_for`.
- `src/relay/core/clock.py` — `Clock` protocol, `SystemClock`, `FrozenClock` (test-only).
- `src/relay/worker/models.py` — `WorkerHeartbeat` table.
- `src/relay/worker/heartbeat.py` — upsert heartbeat, liveness/staleness query.
- `src/relay/worker/runner.py` — `Worker` with injectable clock, single-`tick()` + `run()` loop, graceful stop, restart-safe (heartbeat upsert).
- `src/relay/worker/main.py` — worker entrypoint with SIGINT/SIGTERM handling.
- `src/relay/models.py` — model registry importing all table modules for Alembic.
- `src/relay/api/main.py` — thin FastAPI app factory.
- `src/relay/api/health.py` — `/health/live`, `/health/ready` (real DB check → 503 when down).
- `src/relay/api/middleware.py` — `X-Request-ID` correlation middleware.
- `alembic.ini`, `migrations/env.py`, `migrations/script.py.mako`, `migrations/versions/33fc46f9deae_phase0_worker_heartbeat.py`.
- `tests/conftest.py` + unit (`test_config`, `test_clock`) + integration (`test_health`, `test_worker_heartbeat`, `test_migrations`).
- `scripts/`: `bootstrap.sh`, `migrate.sh`, `run_api.sh`, `run_worker.sh`, `verify.sh`.
- `docker-compose.yml` (postgres, mailpit, migrate, api, worker, web), `Dockerfile`, `web/index.html` placeholder.
- `.github/workflows/ci.yml` (Postgres service, install, migrate-from-zero, verify).
- `.env.example`, `.gitignore`, `README.md`, `docs/` placeholders.

### Architectural decisions
- **Single package + import-linter over separate wheels.** The manifesto suggests an apps/packages split; I use one `relay` package (src layout) whose subpackages match the module names, with import-linter contracts enforcing the boundary rules (`relay.core` forbidden from importing fastapi/starlette/uvicorn/relay.ai/relay.api/relay.notifications/relay.worker; `relay.ai` forbidden from web + worker). Same guarantee, far less packaging boilerplate. Contracts run in CI.
- **Sync SQLAlchemy + psycopg3.** Route handlers are `def` (threadpool). Avoids async footguns and makes `FOR UPDATE SKIP LOCKED` claiming (Phase 7) direct. Documented, deliberate.
- **Worker readiness from persisted state** (`worker_heartbeat`), not a guess. `tick()` is separated from `run()` so tests drive iterations with `FrozenClock` and no sleeping.
- **Alembic URL injection:** `env.py` uses a caller-provided `sqlalchemy.url` if set (tests), else `relay.config`. Enables the migration test to run against a throwaway DB.

### Commands executed & results
- `uv venv --python 3.11 .venv && uv pip install -e ".[dev]"` → success.
- `alembic revision --autogenerate -m "phase0 worker heartbeat"` → created migration.
- `alembic upgrade head` (relay_dev) → `worker_heartbeat` created, `alembic_version=33fc46f9deae`; verified via `psql \d`.
- `pytest` → **15 passed** (against real Postgres `relay_test`).
- `ruff check src tests` → All checks passed. `ruff format --check` → clean.
- `mypy` → Success: no issues in 20 source files.
- `lint-imports` → 2 contracts kept, 0 broken.
- API runtime: `uvicorn relay.api.main:app` → `GET /health/live` = 200 `{"status":"ok"}`; `GET /health/ready` = 200 `{"database":"ok"}`.
- Worker runtime: `python -m relay.worker.main` → 3 heartbeats persisted (`beats=3`, `last_beat_at > started_at`), graceful stop on SIGTERM (`worker.stop ticks=3`).

### Security decisions
- Production secret validation fails fast (`RELAY_SECRET_KEY` must be ≥32 chars and not the dev default).
- No module reads `os.environ` directly except `config.py`. Secrets loaded from env; `.env` gitignored.
- Docker image runs as non-root (`uid 10001`).

### Residual limitations / flags
- **Docker daemon was down** during Phase 0, so gates were verified against a local Homebrew Postgres 14 and structurally for compose — **not** yet via `docker compose up`. The compose/Dockerfile need a real `docker compose up --build` pass on a machine with the daemon running.
- No AI, notifications, auth, or domain model yet — those are Phases 1, 3, 8, 9.
- `mypy` checks `src` only (not `tests`); test files carry a few justified `type: ignore`.

---

## Phases 1 & 2 — Canonical Domain Model + DB Integrity ✅ (green)

**Date:** 2026-08-16

### Files added
- `src/relay/core/enums.py` — 16 domain StrEnums (statuses, lifecycle kinds, provenance, delivery, outbox, etc.).
- `src/relay/core/models/` — `identity.py` (User/Household/Membership), `responsibility.py` (Responsibility/ResponsibilityCycle/LifecycleStep/StepDependency), `ownership.py` (OwnershipContract/OwnershipEvent), `reminders.py`, `recurrence.py`, `outbox.py`, `audit.py`, plus `_helpers.py` (native-enum factory) and `__init__.py` registry.
- `src/relay/ai/models.py` — `AIExtraction`; `src/relay/notifications/models.py` — `NotificationDelivery` (kept in their bounded packages).
- Updated `src/relay/models.py` registry to import all table modules.
- `migrations/versions/373de370dc2d_phase1_domain_model.py` — all 15 domain tables.
- `tests/factories.py` + `tests/integration/test_domain_constraints.py` (7 DB-enforcement tests).

### Architectural decisions
- **15 canonical entities** with `scope_version` / `ownership_version` / `optimistic_version` (the last wired as SQLAlchemy `version_id_col` for stale-write protection).
- **All datetimes are `timestamptz`** via `Base.type_annotation_map = {datetime: DateTime(timezone=True)}` — required for DST-correct recurrence (Phase 7). Verified: migration has 42 tz-aware columns, 0 bare `DateTime()`.
- **DB-enforced invariants (not just Python):** unique email; unique `(user_id, household_id)`; unique `(responsibility_id, sequence)` for cycle history; unique reminder `dedupe_key`; `CHECK status='draft' OR current_owner IS NOT NULL`; `CHECK from_step<>to_step`; confidence ∈ [0,1]; positive version checks; native PG enums for every status; FKs with deliberate `ondelete` (CASCADE for children, RESTRICT for owners, SET NULL for append-only event refs).
- Ownership/audit event tables are append-only (no `updated_at`, no mutation path).
- Models are data + invariants only; business policy lives in sibling modules (Phase 4+).

### Commands executed & results
- `alembic revision --autogenerate` (regenerated after tz fix) → `373de370dc2d`.
- `alembic upgrade head` (relay_dev) → **17 tables**, **6 CHECK constraints**, **15 native enum types** verified via `psql`.
- `pytest tests/integration/test_domain_constraints.py` → **7 passed** (email/membership uniqueness, non-draft-owner check, cycle-sequence uniqueness, self-dependency rejection, dedupe-key uniqueness, FK enforcement — all raise `IntegrityError` from the DB).
- Full `verify.sh` → **ALL GATES PASSED** (22 tests, ruff/format/mypy/import-linter clean, boundaries kept).

### Residual limitations
- Step-dependency **acyclicity** (multi-node cycles) is a domain-logic check (Phase 4), not a single DB constraint — DB only blocks self-edges and duplicate edges.
- Migration reversibility for the full schema is covered by `test_migrations.py` (upgrade head → downgrade base on a throwaway DB).

---

## Phase 4 — Pure Ownership State Machine ✅ (green)

**Date:** 2026-08-16

### Files added
- `src/relay/core/ownership/state_machine.py` — immutable `OwnershipState` + pure reducer commands (activate, propose/accept/decline/cancel transfer, block/unblock, complete/reopen, start_next_cycle, archive), legal-transition table, `check_invariants`.
- `tests/unit/test_ownership_transitions.py` (10 targeted cases), `tests/property/test_ownership_state_machine.py` (Hypothesis `RuleBasedStateMachine`).

### Decisions & invariants
- State machine is **pure** (no DB) so property tests exhaust the space. States: draft/proposed/active/blocked/transfer_pending/completed/archived; only listed transitions allowed.
- Invariants enforced after every command: exactly one owner (single field); live status ⟹ owner present; draft ⟹ no owner; `ownership_version` ≥ 1, monotonic, **increments only on accepted transfer**; accept routes to target and drops the previous owner (No Boomerang seed).
- Illegal commands raise `IllegalTransition`/`OwnershipInvariantError` and leave state unchanged.

### Verification
- Hypothesis stateful test: **200 examples × 40 steps** — could not produce two owners, an ownerless live state, an illegal transition, or a version regression. 10 unit cases green (accept increments version + routes to B; decline keeps A; double-accept illegal; A→B→C chain; recurrence keeps owner; archived terminal).

---

## Phase 5 — Ownership Contract & Atomic Handoff ✅ (green)

**Date:** 2026-08-16

### Files added
- `src/relay/core/application/{__init__,errors,handoff}.py` — typed errors + `propose_handoff` / `accept_handoff` / `decline_handoff`.
- `src/relay/core/reminders/{__init__,keys.py}` — deterministic `make_dedupe_key`.
- `src/relay/core/models/idempotency.py` — `IdempotencyKey` (+ migration `…phase5 idempotency keys`).
- `tests/integration/test_handoff.py` (5), `tests/concurrency/test_handoff_concurrency.py` (2, real threads).

### The atomic accept (one transaction, caller commits)
idempotency check → lock contract `FOR UPDATE` → authorize proposed owner → lock responsibility `FOR UPDATE` → validate pending + `expected_scope_version` + `expected_ownership_version` → validate active membership → apply pure `accept_transfer` → write owner/version/status → mark contract accepted → **supersede old-version reminders and materialize equivalents for the new owner at the new version** → append `OwnershipEvent(transferred)` → write `OutboxEvent(handoff.accepted)` → write `AuditEvent` → persist `IdempotencyKey` with the result. **No network/LLM/email inside the transaction.**

### Verification (real Postgres)
- Happy path: ownership A→B, version 1→2, status active, one transferred event, one outbox row.
- Reminder reroute: A's scheduled reminder → superseded; a new scheduled reminder for B at version 2.
- Idempotent replay (same key): `replayed=True`, **exactly one** transferred event.
- AuthZ: only proposed owner accepts (else `NotAuthorized`).
- Stale: scope edit between propose and accept → `StaleContract`.
- **Concurrency (threads, separate connections):** two simultaneous accepts of one contract → exactly one success + one `ApplicationError`, final version 2, one transferred event. Two simultaneous proposals (A→B vs A→C) → exactly one pending contract; the loser gets `IllegalTransition`.

### Residual / next
- Phase 3 (HTTP auth + tenant isolation) not yet built — handoff is exercised at the service layer with membership ids; the API/auth wrapper and cross-tenant test matrix come next.
- Phase 6 (No Boomerang) is seeded (reminder reroute + owner drop) but its dedicated violation-hunting test suite (escalation policy, A→B→C reminder ownership, overdue/snooze) is pending.
- Full suite now: **40 passed**, all gates green.

---

## Phase 3 — Authentication & Tenant Isolation ✅ (green)

**Date:** 2026-08-16

### Files added
- `src/relay/core/security/{passwords.py,tokens.py}` — argon2 hashing (min/max length guard), random tokens stored as SHA-256 hashes, email normalization.
- `src/relay/core/models/auth.py` — `UserSession` (hashed token, expiry, revocation), `HouseholdInvite` (hashed token, optional email targeting, role, single-use).
- `src/relay/core/application/accounts.py` — register/login/authenticate/logout (dummy-hash on unknown user to blunt enumeration).
- `src/relay/core/application/households.py` — create_household, `require_membership` (fail-closed), list_members, create_invite (admin-only), accept_invite (locked, single-use, email-gated).
- `src/relay/api/{deps.py,errors.py}`, `src/relay/api/routers/{auth.py,households.py}`, `src/relay/api/schemas/{auth.py,household.py}`; wired into `main.py`.
- Migration `…phase3 auth sessions and invites` (patched to reuse the existing `membership_role` enum via `create_type=False`).
- Tests: `tests/integration/test_auth.py` (6), `tests/integration/test_households.py` (4), `tests/security/test_tenant_isolation.py` (7).

### Decisions
- **Bearer tokens (opaque, DB-backed), not cookies** → no CSRF surface. Only token hashes are stored.
- **Authorization is always via `require_membership`**, which raises `NotFound` (404) for non-members so cross-tenant resource existence is never leaked.
- Typed application errors are translated to HTTP centrally (`install_error_handlers`); services never import FastAPI (import-linter still green).

### Verification (real API + Postgres)
- Auth: register→me→login→logout (post-logout token 401); duplicate email 409; wrong password 401; unknown user 401; missing/forged token 401; short password 422.
- Households: create + scoped get; invite + second user joins; members list shows both; invite single-use (replay 409); non-admin invite 403.
- **Tenant isolation matrix:** member of A cannot read/list/invite on B (all 404); random household id 404; **revoked membership** → 404; **expired session** → 401; **revoked session** → 401; email-targeted invite rejects other user 403; forged bearer 401.
- Migration chain still reverses cleanly (`test_migrations` upgrade head → downgrade base on throwaway DB).
- Full suite: **57 passed**, all gates green.

---

## Phase 6 — No Boomerang Engine ✅ (green)

**Date:** 2026-08-16

### Files added
- `src/relay/core/policies/escalation.py` — `BackupPolicy` + `resolve_escalation_recipient`: the single sanctioned way a non-current-owner receives an obligation, and only when an explicit policy names them AND its condition fires. Empty/absent policy ⟹ `None` (never resurrects a previous owner).
- `tests/unit/test_escalation_policy.py` (3), `tests/integration/test_no_boomerang.py` (5, real Postgres).

### Verified No Boomerang properties
- After A→B, scheduled-reminder recipients == {B} exactly (never A).
- A→B→C: recipients == {C}, `ownership_version == 3`.
- Declined transfer: recipients stay {A}.
- Creator + previous owner receive nothing implicitly after transfer.
- Previous owner only returns via an explicit backup policy on its matching condition.
- Full suite: **65 passed**, all gates green.

---

## Phases 7 & 8 — Durable Worker, Recurrence, Notifications ✅ (green)

**Date:** 2026-08-16

### Files
- `src/relay/core/recurrence/calc.py` — `next_occurrence` (RRULE via dateutil, computed in household tz → UTC; DST/leap/month-boundary correct).
- `src/relay/core/application/scheduling.py` — idempotent reminder materialization (dedupe-key upsert) + `complete_cycle_and_advance` (preserve completed cycle, create next, clone steps, carry owner, materialize).
- `src/relay/worker/claiming.py` — `claim_due_reminders` + `claim_outbox` via `FOR UPDATE SKIP LOCKED` with lease-expiry reclaim.
- `src/relay/worker/processing.py` — `fire_due_reminders` (privacy-minimal message + deep link) and `process_outbox` (retry w/ backoff → dead-letter); default handler notifies new owner on `handoff.accepted`.
- `src/relay/worker/runner.py` — tick now heartbeats + fires + drains.
- `src/relay/notifications/` — `channels.py` (InApp + real SMTP), `delivery.py` (per-attempt evidence), `factory.py`, `models.py` (+`InAppNotification`). Config gained SMTP + deep-link + worker batch/backoff.
- Migration `…phase7 8 in_app_notifications`.
- Tests: `tests/unit/test_recurrence.py` (4), `tests/worker/*` (firing 3, outbox 3, restart 1, recurrence rollover 3), `tests/integration/test_notifications.py` (3, incl. **real aiosmtpd SMTP send/receive**).

### Verified
- Reminders fired once, evidence + in-app inbox written; not fired before due; idempotent across ticks.
- Outbox: success→processed; failure retries with growing backoff then dead-letters at max attempts; expired lease reclaimed by another worker.
- **Restart safety:** worker crash before commit loses nothing and restart fires each obligation exactly once (no duplicate delivery).
- Recurrence: DST spring-forward keeps 09:00 wall clock; BYMONTHDAY=31 skips short months; leap-day lands on next leap year; rollover clones steps + carries owner; transfer-then-advance routes new cycle to new owner (No Boomerang across cycles).
- **Real SMTP:** message accepted (`provider_accepted`, message-id, delivered_at) and received by an in-process SMTP server; transport failure → `retryable_failure` with evidence, `delivered_at` null.
- Full suite: **82 passed**, all gates green.

---

## Phases 9–20 — Intelligence, API, Frontend, Hardening, E2E ✅ (green)

**Date:** 2026-08-16

### Phase 9 — Responsibility Intelligence (bounded AI)
- `relay/ai/schemas.py` (strict draft; ownership is structurally inexpressible, `extra="forbid"`), `providers/base.py` (Provider protocol + ProviderError), `fallback.py` (deterministic; extracts recurrence/dates from arbitrary text, never invents, always one editable EXECUTE step, surfaces unknowns), `validation.py` (dependency acyclicity + assumption discipline), `extraction.py` (pipeline: provider→schema→policy→provenance→persist AIExtraction; falls back on invalid output or outage), `providers/groq.py` (real Groq OpenAI-compatible Chat Completions via httpx, JSON mode; injection-resistant prompt), `factory.py`.
- Eval corpus `fixtures/ai_gold/corpus.json` + `tests/ai_evals/*` (30 tests): schema-valid 100%, fallback completion 100%, ownership boundary 100%, injection resistance, provider-outage safety, persistence.

### Phases 10–12 — X-Ray, Proof of Relief, full REST surface
- `relay/core/application/responsibilities.py` (create/get-scoped/list/scope-edit→version-bump/step complete+reopen/complete-with-recurrence-rollover), `proof.py` (Proof of Relief + ownership history, computed from real state — no invented metrics).
- Routers: `responsibilities.py`, `handoffs.py`, `queue.py` + schemas. **24 `/v1` routes** total. Every mutation authenticates, is tenant-scoped, and validates versions/idempotency where relevant.

### Phase 13 — Minimal frontend
- `web/index.html`: buildless single-page vanilla client covering all required screens (auth, household/member, capture→X-Ray, handoff propose/accept, ghost queue, notifications, history, proof). Makes real API requests; holds no authoritative ownership state (re-fetches after every action).

### Phase 14 — Security hardening
- `relay/api/security_mw.py` (security headers, body-size cap 413, per-process rate limiter 429), central generic-500 handler (logs server-side with request id, never leaks a stack trace), strict CORS from settings, bearer-token auth (no CSRF surface). `tests/security/test_hardening.py` (4).

### Phase 15 — Observability
- structlog JSON + contextvar request-id middleware; worker heartbeat table; `/health/live` + `/health/ready` (real DB probe); unhandled errors logged with correlation id. "Why did this reminder go to this person?" is answerable from `ownership_events` + `reminders.ownership_version` + `audit_events`.

### Phase 18 — Real end-to-end proof
- `tests/e2e/test_full_handoff_flow.py`: two users register → household → invite/join → AI draft → create → X-Ray → propose → **B accepts** → A no longer owner / B is (persisted) → reminder rerouted to B → **worker fires → B notified, A gets nothing** → Proof of Relief + ownership history correct → idempotent replay → Postgres verified. All through the real API, no manual DB edits.

### Phase 19 — Adversarial review
- `grep` of `src/` for `TODO|FIXME|HACK|mock|fake|sqlite|time.sleep|NotImplemented|print(`: no shortcuts in critical paths (only a documented "demo" comment on the rate limiter, empty-body exception classes, and the intentional deterministic fallback).

### Phase 20 — Definition of Done (status)
Green: real auth; households; multi-user membership; persisted responsibilities + lifecycle + scope versioning; ownership contracts; atomic + idempotent + concurrency-safe transfer; No Boomerang; durable reminders; durable restart-safe worker; recurrence; in-app + real SMTP delivery with persisted attempts; bounded AI + safe fallback + evals; audit-reconstructable ownership; Proof of Relief from real state; tenant isolation + security tests; migrations from zero; minimal frontend driving real APIs; two-user E2E; **full verify suite green (117 tests)**.
Outstanding (flagged, not blocking correctness): `docker compose up --build` unrun (daemon down — verified on local PG instead); Playwright browser E2E not added (Python TestClient E2E covers the critical path); real Groq call exercised only via the adapter code path (no API key set here), deterministic fallback fully tested; no git commit yet (public repo — awaiting go-ahead).

### Final verification
- `./scripts/verify.sh` → format, lint, mypy, import-linter (2 contracts kept), **117 pytest passed** (unit/property/integration/concurrency/security/worker/ai_evals/e2e), frontend presence — **ALL GATES PASSED**.
