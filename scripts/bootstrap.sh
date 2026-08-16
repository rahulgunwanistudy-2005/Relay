#!/usr/bin/env bash
# Create the virtualenv and install Relay with dev dependencies.
set -euo pipefail
cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

uv venv --python 3.11 .venv
uv pip install --python .venv -e ".[dev]"

echo "Bootstrap complete. Activate with: source .venv/bin/activate"
echo "Next: cp .env.example .env  &&  ./scripts/migrate.sh"
