#!/usr/bin/env bash
# Run the durable background worker.
set -euo pipefail
cd "$(dirname "$0")/.."

PY=".venv/bin/python"
[ -x "$PY" ] || PY="python"

exec "$PY" -m relay.worker.main
