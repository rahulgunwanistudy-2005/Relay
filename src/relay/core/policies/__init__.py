"""Domain policies (escalation/backup routing)."""

from relay.core.policies.escalation import BackupPolicy, resolve_escalation_recipient

__all__ = ["BackupPolicy", "resolve_escalation_recipient"]
