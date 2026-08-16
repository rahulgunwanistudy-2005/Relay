"""Pure ownership state machine.

Deterministic, side-effect-free reducer over an immutable ``OwnershipState``.
The application/service layer (Phase 5) maps persisted rows to this state,
applies a command, and persists the result inside one transaction. Keeping the
rules pure here lets property tests exhaust the transition space with no DB.

Invariants (must hold after every legal command):
  1. Exactly one current owner (a single optional field — never a set).
  2. A live responsibility (active/blocked/transfer_pending/completed) has an owner.
  3. A draft has no owner.
  4. ``ownership_version`` is >= 1, never decreases, and increments *only* on an
     accepted transfer.
  5. A transfer that is accepted routes ownership to the proposed target; the
     previous owner is not retained (the seed of No Boomerang).
"""

from __future__ import annotations

import dataclasses
import uuid

from relay.core.enums import ResponsibilityStatus as S

MembershipId = uuid.UUID


class IllegalTransition(Exception):
    """Raised when a status transition is not permitted."""


class OwnershipInvariantError(Exception):
    """Raised when a state would violate an ownership invariant."""


# Legal status transitions. Everything not listed is illegal.
ALLOWED: dict[S, frozenset[S]] = {
    S.draft: frozenset({S.proposed, S.active, S.archived}),
    S.proposed: frozenset({S.active, S.draft, S.archived}),
    S.active: frozenset({S.transfer_pending, S.blocked, S.completed, S.archived}),
    S.blocked: frozenset({S.active, S.archived}),
    S.transfer_pending: frozenset({S.active, S.archived}),
    S.completed: frozenset({S.active, S.archived}),
    S.archived: frozenset(),
}


def can_transition(src: S, dst: S) -> bool:
    return dst in ALLOWED.get(src, frozenset())


def ensure_transition(src: S, dst: S) -> None:
    if not can_transition(src, dst):
        raise IllegalTransition(f"{src.value} -> {dst.value} is not allowed")


@dataclasses.dataclass(frozen=True)
class OwnershipState:
    status: S
    current_owner: MembershipId | None
    ownership_version: int
    pending_source: MembershipId | None = None
    pending_target: MembershipId | None = None

    @staticmethod
    def new_draft() -> OwnershipState:
        return OwnershipState(status=S.draft, current_owner=None, ownership_version=1)


_LIVE = frozenset({S.active, S.blocked, S.transfer_pending, S.completed})


def check_invariants(state: OwnershipState) -> None:
    if state.ownership_version < 1:
        raise OwnershipInvariantError("ownership_version must be >= 1")
    if state.status is S.draft and state.current_owner is not None:
        raise OwnershipInvariantError("draft must not have an owner")
    if state.status in _LIVE and state.current_owner is None:
        raise OwnershipInvariantError(f"{state.status.value} must have an owner")
    if state.status is S.transfer_pending:
        if state.pending_target is None:
            raise OwnershipInvariantError("transfer_pending requires a pending target")
        if state.pending_source != state.current_owner:
            raise OwnershipInvariantError("pending source must be the current owner")
    else:
        if state.pending_target is not None or state.pending_source is not None:
            raise OwnershipInvariantError("pending fields set outside transfer_pending")


def _transition(state: OwnershipState, dst: S, **changes) -> OwnershipState:
    ensure_transition(state.status, dst)
    new = dataclasses.replace(state, status=dst, **changes)
    check_invariants(new)
    return new


# --- Commands (each returns a new state; never mutates the input) ---


def activate(state: OwnershipState, owner: MembershipId) -> OwnershipState:
    """Assign the first owner to a draft. Ownership version stays at 1."""
    return _transition(state, S.active, current_owner=owner)


def propose_transfer(
    state: OwnershipState, source: MembershipId, target: MembershipId
) -> OwnershipState:
    if state.current_owner != source:
        raise OwnershipInvariantError("only the current owner can be the transfer source")
    if source == target:
        raise OwnershipInvariantError("cannot transfer a responsibility to its current owner")
    return _transition(state, S.transfer_pending, pending_source=source, pending_target=target)


def accept_transfer(state: OwnershipState) -> OwnershipState:
    if state.status is not S.transfer_pending or state.pending_target is None:
        raise IllegalTransition("no pending transfer to accept")
    return _transition(
        state,
        S.active,
        current_owner=state.pending_target,
        ownership_version=state.ownership_version + 1,
        pending_source=None,
        pending_target=None,
    )


def decline_transfer(state: OwnershipState) -> OwnershipState:
    if state.status is not S.transfer_pending:
        raise IllegalTransition("no pending transfer to decline")
    return _transition(state, S.active, pending_source=None, pending_target=None)


def cancel_transfer(state: OwnershipState) -> OwnershipState:
    if state.status is not S.transfer_pending:
        raise IllegalTransition("no pending transfer to cancel")
    return _transition(state, S.active, pending_source=None, pending_target=None)


def block(state: OwnershipState) -> OwnershipState:
    return _transition(state, S.blocked)


def unblock(state: OwnershipState) -> OwnershipState:
    return _transition(state, S.active)


def complete(state: OwnershipState) -> OwnershipState:
    return _transition(state, S.completed)


def reopen(state: OwnershipState) -> OwnershipState:
    return _transition(state, S.active)


def start_next_cycle(state: OwnershipState) -> OwnershipState:
    """Recurrence: a completed cycle's responsibility becomes active for the next
    cycle, carrying the same owner (No Boomerang across cycles)."""
    return _transition(state, S.active)


def archive(state: OwnershipState) -> OwnershipState:
    return _transition(state, S.archived, pending_source=None, pending_target=None)
