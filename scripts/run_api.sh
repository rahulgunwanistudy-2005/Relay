#!/usr/bin/env bash
# Run the API (development server with reload).
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/uvicorn"
[ -x "$PY" ] || PY="uvicorn"

exec "$PY" relay.api.main:app --host 0.0.0.0 --port "${PORT:-8000}" "$@"
