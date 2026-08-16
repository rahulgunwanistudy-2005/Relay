"""Structured logging setup.

Emits JSON in production, human-friendly console output in development. A
contextvar-backed request/correlation id is bound onto every log line so a
reminder or ownership event can be traced end to end.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar

import structlog

_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def bind_request_id(request_id: str) -> None:
    _request_id.set(request_id)


def _inject_request_id(_logger, _method, event_dict):
    rid = _request_id.get()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    return event_dict


def configure_logging(level: str = "INFO", json: bool = True) -> None:
    renderer = structlog.processors.JSONRenderer() if json else structlog.dev.ConsoleRenderer()
    processors: list = [
        structlog.contextvars.merge_contextvars,
        _inject_request_id,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]
    # JSON needs exc_info flattened to a string; ConsoleRenderer formats it itself.
    if json:
        processors.append(structlog.processors.format_exc_info)
    processors.append(renderer)
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(level.upper())),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None):
    return structlog.get_logger(name)
