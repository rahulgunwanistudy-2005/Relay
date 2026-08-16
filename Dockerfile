# Relay API + worker image. Same image runs either process (command selects).
FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies first for layer caching.
COPY pyproject.toml README.md ./
COPY src ./src
RUN uv pip install --system -e "."

COPY alembic.ini ./
COPY migrations ./migrations

# Non-root runtime user.
RUN useradd --create-home --uid 10001 relay
USER relay

EXPOSE 8000

# Default: API. Applies migrations, then binds the platform-provided $PORT
# (Render/Fly set it; defaults to 8000 locally). Exec-form sh -c keeps quoting
# correct so the start command never mis-splits. Override `command` for the worker.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn relay.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
