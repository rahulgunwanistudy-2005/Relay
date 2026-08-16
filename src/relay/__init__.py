"""Relay — a responsibility-transfer engine.

Modular monolith. Subpackages map to the manifesto's modules:

- ``relay.core``          domain, ownership, responsibilities, recurrence, reminders,
                          audit, policies, application services. No web/AI imports.
- ``relay.ai``            bounded free-text -> draft Responsibility Graph. Never mutates state.
- ``relay.notifications`` delivery channels and persisted delivery evidence.
- ``relay.api``           thin FastAPI layer.
- ``relay.worker``        durable, idempotent background processing.
- ``relay.db``            engine/session/base shared infrastructure.

Boundaries are enforced by import-linter contracts (see pyproject.toml).
"""

__version__ = "0.0.0"
