"""Explicit escalation / backup routing.

No Boomerang law: a previous owner (or creator, or viewer) is NEVER an implicit
fallback recipient. The *only* way anyone other than the current owner receives
a Relay obligation is an explicitly configured backup policy whose triggering
condition has occurred. This module is that single sanctioned exception, and it
is deterministic and auditable.

Policy shape (stored on OwnershipContract.backup_policy / responsibility config):
    {"escalate_to": "<membership_uuid>", "on": ["overdue", "owner_unavailable"]}
An empty policy means: no fallback, ever.
"""

from __future__ import annotations

import dataclasses
import uuid


@dataclasses.dataclass(frozen=True)
class BackupPolicy:
    escalate_to: uuid.UUID | None
    on: frozenset[str]

    @staticmethod
    def from_dict(raw: dict | None) -> BackupPolicy:
        raw = raw or {}
        target = raw.get("escalate_to")
        return BackupPolicy(
            escalate_to=uuid.UUID(target) if target else None,
            on=frozenset(raw.get("on", [])),
        )


def resolve_escalation_recipient(backup_policy: dict | None, *, condition: str) -> uuid.UUID | None:
    """Return the explicitly-configured escalation recipient for ``condition``,
    or ``None``. Returning ``None`` is the norm — absence of a policy never
    resurrects a previous owner."""
    policy = BackupPolicy.from_dict(backup_policy)
    if policy.escalate_to is not None and condition in policy.on:
        return policy.escalate_to
    return None
