## Task: Relay — Backend-first responsibility-transfer engine

## Goal: Build the real Relay engine per the manifesto, phase by phase, with green verification gates at every step. The No Boomerang invariant is enforced in the backend/domain layer, not the UI.

This is a multi-session build. Phases are executed in order; a phase is not "done" until its gate is green and recorded in IMPLEMENTATION_LEDGER.md.

### Phase map (manifesto)
- [x] Phase 0 — Repository & execution foundation  ✅ GREEN
- [x] Phase 1 — Canonical domain model  ✅ GREEN
- [x] Phase 2 — Database integrity & migrations  ✅ GREEN
- [x] Phase 3 — Authentication & tenant isolation  ✅ GREEN (auth + IDOR matrix)
- [x] Phase 4 — Pure ownership state machine  ✅ GREEN (Hypothesis 200×40)
- [x] Phase 5 — Ownership contract & atomic handoff  ✅ GREEN (incl. concurrency)
- [x] Phase 6 — No Boomerang engine  ✅ GREEN (dedicated suite + escalation policy)
- [x] Phase 7 — Durable scheduler, worker & recurrence  ✅ GREEN
- [x] Phase 8 — Real notification delivery  ✅ GREEN (in-app + real SMTP)
- [x] Phase 9 — Responsibility intelligence (AI, bounded)  ✅ GREEN
- [x] Phase 10 — Responsibility X-Ray  ✅ GREEN
- [x] Phase 11 — Proof of Relief  ✅ GREEN
- [x] Phase 12 — Complete API surface  ✅ GREEN (24 routes)
- [x] Phase 13 — Minimal frontend  ✅ GREEN (buildless client)
- [x] Phase 14 — Security hardening  ✅ GREEN
- [x] Phase 15 — Observability  ✅ GREEN
- [x] Phase 16 — Testing standard  ✅ (unit/property/integration/concurrency/security/worker/ai/e2e)
- [x] Phase 17 — Quality gates (verify.sh)  ✅ GREEN
- [x] Phase 18 — Real end-to-end proof  ✅ GREEN (two-user API E2E)
- [x] Phase 19 — Adversarial review  ✅ (no shortcuts in critical paths)
- [x] Phase 20 — Definition of done  ✅ (see ledger; flags documented)

### Phase 0 steps (current)
- [ ] uv-managed project + pinned deps (pyproject.toml)
- [ ] Modular-monolith package layout (src/relay: core / ai / notifications / api / worker / db)
- [ ] import-linter contracts enforcing boundary rules (core has no web/AI deps)
- [ ] Typed, env-driven config (pydantic-settings) with dev/test/prod separation + fail-fast
- [ ] Structured logging (structlog) with request correlation scaffold
- [ ] SQLAlchemy engine/session + declarative Base
- [ ] Alembic wired to Base, initial migration
- [ ] FastAPI app (thin main) with /health/live and /health/ready (ready checks DB)
- [ ] Worker process with heartbeat/readiness table
- [ ] Minimal web service placeholder
- [ ] docker-compose.yml (postgres, api, worker, web, mailpit) + Dockerfile
- [ ] scripts/: bootstrap.sh, migrate.sh, run_worker.sh, verify.sh
- [ ] CI workflow (GitHub Actions)
- [ ] pytest smoke tests (config, health, worker heartbeat) against real Postgres
- [ ] .env.example, .gitignore, README, IMPLEMENTATION_LEDGER.md

### Architecture decisions
- Single installable package `relay` (src layout) with subpackages named to match manifesto modules; boundaries enforced by import-linter contracts rather than separate wheels (less boilerplate, same guarantee). Documented in ledger.
- **Sync** SQLAlchemy + psycopg3 throughout. FastAPI route handlers are `def` (threadpool) so DB access is sync. This eliminates async footguns and makes `FOR UPDATE SKIP LOCKED` worker claiming straightforward. Deliberate, documented choice.
- Local Homebrew Postgres 14 used for dev/test verification while Docker Desktop daemon is down; docker-compose.yml is the canonical portable env.

### Risks / open questions
- Docker daemon currently down — compose gate verified structurally + against local PG, not via `docker compose up` yet. Flag to user.
- AI provider (Phase 9) needs an API key; deterministic fallback must work without one.
- Real external notification (Phase 8) needs SMTP creds; Mailpit used for dev/integration.

### Done criteria (Phase 0)
- [ ] Clean checkout → install → migrate → tests → start API → start worker all succeed
- [ ] /health/live and /health/ready return correctly; ready fails when DB down
- [ ] import-linter passes; ruff + mypy clean; pytest green

### Review — Phase 0
Built the full executable skeleton and verified every gate against a **real
Postgres** (local Homebrew PG 14, since the Docker daemon was down):
- install → migrate-from-zero → 15 pytest passing → ruff/format/mypy/import-linter clean
- API serves `/health/live` (200) and `/health/ready` (200 with real DB check; 503 when DB down, tested)
- worker persists heartbeats and shuts down gracefully on SIGTERM
- `verify.sh` runs the whole gate and ends "ALL GATES PASSED"

Deferred / flagged: `docker compose up --build` not run (daemon down) — compose
+ Dockerfile written and structurally sound but need one real pass on a machine
with Docker running. No git commit made (awaiting user).
