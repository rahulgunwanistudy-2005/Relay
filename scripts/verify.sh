#!/usr/bin/env bash
# Mandatory quality gate. Fails on the first failing check.
# Grows per phase; Phase 0 covers format, lint, types, boundaries, migrations, tests.
set -euo pipefail
cd "$(dirname "$0")/.."

BIN=".venv/bin"
[ -x "$BIN/python" ] || BIN=""   # fall back to PATH
run() { echo "── $1 ─────────────────────────────────"; shift; "$@"; }

run "ruff format --check"  "${BIN:+$BIN/}ruff" format --check src tests
run "ruff lint"            "${BIN:+$BIN/}ruff" check src tests
run "mypy"                 "${BIN:+$BIN/}mypy"
run "import-linter"        "${BIN:+$BIN/}lint-imports"
run "pytest"               "${BIN:+$BIN/}pytest"

# Frontend is a Vite + React client; assert it exists and is wired to the API.
# Its own type/lint/build gates run in the separate `web` CI job.
echo "── frontend presence ─────────────────────────────────"
test -s web/package.json && test -s web/src/lib/api.ts && grep -q "/v1/" web/src/lib/api.ts \
  && echo "web client present and wired to /v1 API" \
  || { echo "frontend check failed"; exit 1; }

echo
echo "ALL GATES PASSED"
