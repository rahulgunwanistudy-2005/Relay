from __future__ import annotations

import uuid

from relay.core.policies import resolve_escalation_recipient


def test_empty_policy_never_escalates() -> None:
    assert resolve_escalation_recipient({}, condition="overdue") is None
    assert resolve_escalation_recipient(None, condition="overdue") is None


def test_policy_escalates_only_on_matching_condition() -> None:
    target = uuid.uuid4()
    policy = {"escalate_to": str(target), "on": ["overdue"]}
    assert resolve_escalation_recipient(policy, condition="overdue") == target
    assert resolve_escalation_recipient(policy, condition="owner_unavailable") is None


def test_policy_without_target_never_escalates() -> None:
    assert resolve_escalation_recipient({"on": ["overdue"]}, condition="overdue") is None
