"""Targeted unit tests for the ownership state machine."""

from __future__ import annotations

import uuid

import pytest

from relay.core.enums import ResponsibilityStatus as S
from relay.core.ownership import state_machine as sm

A = uuid.uuid4()
B = uuid.uuid4()
C = uuid.uuid4()


def _active_owned_by(owner: uuid.UUID) -> sm.OwnershipState:
    return sm.activate(sm.OwnershipState.new_draft(), owner)


def test_activate_sets_first_owner_version_one() -> None:
    st = _active_owned_by(A)
    assert st.status is S.active
    assert st.current_owner == A
    assert st.ownership_version == 1


def test_accept_transfers_ownership_and_increments_version() -> None:
    st = _active_owned_by(A)
    st = sm.propose_transfer(st, A, B)
    assert st.status is S.transfer_pending
    st = sm.accept_transfer(st)
    assert st.status is S.active
    assert st.current_owner == B  # No Boomerang: owner is now B, not A
    assert st.ownership_version == 2
    assert st.pending_target is None


def test_decline_keeps_original_owner_and_version() -> None:
    st = _active_owned_by(A)
    st = sm.propose_transfer(st, A, B)
    st = sm.decline_transfer(st)
    assert st.status is S.active
    assert st.current_owner == A
    assert st.ownership_version == 1


def test_double_accept_is_illegal() -> None:
    st = _active_owned_by(A)
    st = sm.propose_transfer(st, A, B)
    st = sm.accept_transfer(st)
    with pytest.raises(sm.IllegalTransition):
        sm.accept_transfer(st)


def test_cannot_propose_transfer_to_self() -> None:
    st = _active_owned_by(A)
    with pytest.raises(sm.OwnershipInvariantError):
        sm.propose_transfer(st, A, A)


def test_only_current_owner_can_be_source() -> None:
    st = _active_owned_by(A)
    with pytest.raises(sm.OwnershipInvariantError):
        sm.propose_transfer(st, B, C)


def test_chain_transfer_a_b_c() -> None:
    st = _active_owned_by(A)
    st = sm.accept_transfer(sm.propose_transfer(st, A, B))
    st = sm.accept_transfer(sm.propose_transfer(st, B, C))
    assert st.current_owner == C
    assert st.ownership_version == 3


def test_recurrence_next_cycle_keeps_owner() -> None:
    st = _active_owned_by(A)
    st = sm.accept_transfer(sm.propose_transfer(st, A, B))
    st = sm.complete(st)
    st = sm.start_next_cycle(st)
    assert st.status is S.active
    assert st.current_owner == B  # owner carries across cycles
    assert st.ownership_version == 2


def test_archived_is_terminal() -> None:
    st = sm.archive(_active_owned_by(A))
    for cmd in (sm.block, sm.complete, sm.reopen, sm.accept_transfer):
        with pytest.raises(sm.IllegalTransition):
            cmd(st)


def test_draft_cannot_be_completed() -> None:
    with pytest.raises(sm.IllegalTransition):
        sm.complete(sm.OwnershipState.new_draft())
