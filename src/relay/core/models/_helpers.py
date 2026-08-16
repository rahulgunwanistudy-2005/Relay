"""Shared column helpers for ORM models."""

from __future__ import annotations

import datetime as dt
import uuid
from enum import StrEnum

from sqlalchemy import Enum as SAEnum
from sqlalchemy import types


def pg_enum(enum_cls: type[StrEnum], name: str) -> SAEnum:
    """A native Postgres ENUM that persists the string *value* of each member."""
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=True,
        values_callable=lambda e: [m.value for m in e],
    )


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.UTC)


# Reusable column types.
UUID = types.Uuid
JSONB_DEFAULT: dict = {}


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()
