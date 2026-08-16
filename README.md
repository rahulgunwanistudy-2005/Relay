# Relay

A **responsibility-transfer engine**. When responsibility for something is
consensually handed from person A to person B, Relay moves the *entire*
operational lifecycle — anticipation, decisions, preparation, execution,
verification, follow-up, and recurrence — so A stops being the hidden monitoring
system.

The highest-priority product invariant is **No Boomerang**: after an accepted
handoff A → B, all future Relay-generated reminders, monitoring, recurrence
obligations, and notifications belong to B unless A was explicitly configured as
a backup/escalation target. This is a database/domain invariant, not UI
behavior.

> The backend is the product. The frontend only demonstrates the backend.

## Architecture

Modular monolith. One installable package, `relay`, with subpackages that map to
the manifesto's modules; boundaries are enforced by [import-linter](https://import-linter.readthedocs.io/)
contracts (see `pyproject.toml`).

| Package | Responsibility | Boundary rule |
| --- | --- | --- |
| `relay.core` | domain, ownership, responsibilities, recurrence, reminders, audit, policies, application services | no web-framework or AI imports |
| `relay.ai` | free text → draft Responsibility Graph | never mutates ownership/reminders |
| `relay.notifications` | delivery channels + persisted delivery evidence | — |
| `relay.api` | thin FastAPI layer | routes stay thin |
| `relay.worker` | durable, idempotent background processing | idempotent effects |
| `relay.db` | engine/session/base | — |

**Stack:** Python 3.11, FastAPI, Pydantic v2, SQLAlchemy 2 (sync + psycopg3),
Alembic, PostgreSQL, structlog, pytest/Hypothesis. Sync SQLAlchemy is a
deliberate choice: route handlers are `def` (threadpool), which keeps
`FOR UPDATE SKIP LOCKED` worker claiming straightforward and eliminates async
footguns.

## Quickstart

```bash
# 1. Dependencies
./scripts/bootstrap.sh
cp .env.example .env          # edit RELAY_DATABASE_URL if needed

# 2. Database (Docker) — or point .env at a local Postgres
docker compose up -d postgres
./scripts/migrate.sh

# 3. Run
./scripts/run_api.sh          # http://localhost:8000/docs
./scripts/run_worker.sh       # durable background worker

# 4. Verify everything
./scripts/verify.sh
```

Health probes: `GET /health/live` (process up) and `GET /health/ready`
(dependencies reachable; 503 when the DB is down).

## Status

Phase 0 (repository & execution foundation) is complete and green. See
[`IMPLEMENTATION_LEDGER.md`](IMPLEMENTATION_LEDGER.md) for the running record of
what has been built, executed, and verified, and `tasks/todo.md` for the phase
plan.
