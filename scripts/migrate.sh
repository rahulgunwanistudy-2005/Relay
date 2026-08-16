#!/usr/bin/env bash
# Apply database migrations to the configured Postgres.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/alembic"
[ -x "$PY" ] || PY="alembic"

exec "$PY" upgrade "${1:-head}"
