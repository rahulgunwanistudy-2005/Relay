"""Persistence for AI extractions. Lives in relay.ai (never imported by core)."""

from __future__ import annotations

import datetime as dt
import uuid

from sqlalchemy import Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from relay.core.enums import AIValidationState
from relay.core.models._helpers import pg_enum
from relay.db.base import Base


class AIExtraction(Base):
    __tablename__ = "ai_extractions"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # Hash of the input text — avoids storing raw sensitive text unnecessarily.
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(60), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(60), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(60), nullable=False)
    structured_output: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    validation_state: Mapped[AIValidationState] = mapped_column(
        pg_enum(AIValidationState, "ai_validation_state"), nullable=False
    )
    provenance_metadata: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[dt.datetime] = mapped_column(server_default=func.now(), nullable=False)
