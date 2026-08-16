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

# Frontend is a buildless static client; assert it exists and references the API.
echo "── frontend presence ─────────────────────────────────"
test -s web/index.html && grep -q "/v1/" web/index.html \
  && echo "web/index.html present and wired to /v1 API" \
  || { echo "frontend check failed"; exit 1; }

echo
echo "ALL GATES PASSED"
