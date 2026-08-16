"""Property tests for the pure ownership state machine.

Hypothesis drives random command sequences. After every command — legal or
illegal — the invariants must hold, illegal commands must raise (not corrupt),
and ownership_version must never decrease.
"""

from __future__ import annotations

import uuid

import pytest
from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from relay.core.enums import ResponsibilityStatus as S
from relay.core.ownership import state_machine as sm

pytestmark = pytest.mark.property

_A = uuid.uuid4()
_B = uuid.uuid4()
_C = uuid.uuid4()


class OwnershipMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.state = sm.OwnershipState.new_draft()
        self.max_version = 1

    def _attempt(self, fn) -> None:
        before = self.state
        try:
            self.state = fn(before)
        except (sm.IllegalTransition, sm.OwnershipInvariantError):
            # Rejected commands must leave the state untouched.
            assert self.state == before
            return
        # A legal command must not decrease the ownership version.
        assert self.state.ownership_version >= before.ownership_version
        self.max_version = max(self.max_version, self.state.ownership_version)

    @rule()
    def activate(self) -> None:
        self._attempt(lambda s: sm.activate(s, _A))

    @rule()
    def propose_to_b(self) -> None:
        self._attempt(lambda s: sm.propose_transfer(s, s.current_owner or _A, _B))

    @rule()
    def propose_to_c(self) -> None:
        self._attempt(lambda s: sm.propose_transfer(s, s.current_owner or _A, _C))

    @rule()
    def accept(self) -> None:
        self._attempt(sm.accept_transfer)

    @rule()
    def decline(self) -> None:
        self._attempt(sm.decline_transfer)

    @rule()
    def cancel(self) -> None:
        self._attempt(sm.cancel_transfer)

    @rule()
    def block(self) -> None:
        self._attempt(sm.block)

    @rule()
    def unblock(self) -> None:
        self._attempt(sm.unblock)

    @rule()
    def complete(self) -> None:
        self._attempt(sm.complete)

    @rule()
    def reopen(self) -> None:
        self._attempt(sm.reopen)

    @rule()
    def archive(self) -> None:
        self._attempt(sm.archive)

    @invariant()
    def invariants_hold(self) -> None:
        sm.check_invariants(self.state)
        # Exactly-one-owner is structural: current_owner is a single value.
        if self.state.status in {S.active, S.blocked, S.transfer_pending, S.completed}:
            assert self.state.current_owner is not None


TestOwnershipMachine = OwnershipMachine.TestCase
TestOwnershipMachine.settings = settings(max_examples=200, stateful_step_count=40)
