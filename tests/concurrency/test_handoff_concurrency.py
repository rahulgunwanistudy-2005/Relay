"""Concurrency: real parallel DB transactions must yield one valid outcome."""

from __future__ import annotations

import threading

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from relay.core.application import handoff
from relay.core.application.errors import ApplicationError
from relay.core.enums import ContractStatus, OwnershipEventType, ResponsibilityStatus
from relay.core.models import OwnershipContract, OwnershipEvent, Responsibility
from relay.core.ownership.state_machine import IllegalTransition, OwnershipInvariantError
from tests.factories import make_household, make_membership, make_responsibility, make_user

pytestmark = [pytest.mark.integration, pytest.mark.concurrency]


def _run_two(fn_a, fn_b) -> list:
    """Run two callables on separate threads, started as simultaneously as
    possible. Returns [(ok, value_or_exc), ...] in [a, b] order."""
    barrier = threading.Barrier(2)
    results: list = [None, None]

    def wrap(i, fn):
        def inner():
            barrier.wait()
            try:
                results[i] = ("ok", fn())
            except Exception as exc:  # capture for assertion in the main thread
                results[i] = ("err", exc)

        return inner

    ta = threading.Thread(target=wrap(0, fn_a))
    tb = threading.Thread(target=wrap(1, fn_b))
    ta.start()
    tb.start()
    ta.join(timeout=15)
    tb.join(timeout=15)
    return results


def _scenario(engine: Engine, *, propose: bool):
    with Session(engine) as s:
        hh = make_household(s)
        a = make_membership(s, make_user(s, name="A"), hh)
        b = make_membership(s, make_user(s, name="B"), hh)
        c = make_membership(s, make_user(s, name="C"), hh)
        resp = make_responsibility(s, hh, a, owner=a, status=ResponsibilityStatus.active)
        s.commit()
        data = {"a": a.id, "b": b.id, "c": c.id, "resp": resp.id}
        if propose:
            cid = handoff.propose_handoff(
                s,
                actor_membership_id=a.id,
                responsibility_id=resp.id,
                target_membership_id=b.id,
            ).id
            s.commit()
            data["contract"] = cid
        return data


def test_concurrent_accept_of_same_contract_transfers_once(engine: Engine) -> None:
    sc = _scenario(engine, propose=True)

    def accept(key):
        def _do():
            with Session(engine) as s:
                r = handoff.accept_handoff(
                    s,
                    actor_membership_id=sc["b"],
                    contract_id=sc["contract"],
                    idempotency_key=key,
                )
                s.commit()
                return r

        return _do

    results = _run_two(accept("race-a"), accept("race-b"))

    oks = [v for (status, v) in results if status == "ok"]
    errs = [v for (status, v) in results if status == "err"]
    assert len(oks) == 1, f"expected exactly one success, got {results}"
    assert len(errs) == 1
    assert isinstance(errs[0], ApplicationError)

    with Session(engine) as s:
        resp = s.get(Responsibility, sc["resp"])
        assert resp.current_owner_membership_id == sc["b"]
        assert resp.ownership_version == 2
        transferred = s.execute(
            select(func.count())
            .select_from(OwnershipEvent)
            .where(OwnershipEvent.event_type == OwnershipEventType.transferred)
        ).scalar_one()
        assert transferred == 1


def test_concurrent_proposals_produce_one_pending_contract(engine: Engine) -> None:
    sc = _scenario(engine, propose=False)

    def propose(target):
        def _do():
            with Session(engine) as s:
                c = handoff.propose_handoff(
                    s,
                    actor_membership_id=sc["a"],
                    responsibility_id=sc["resp"],
                    target_membership_id=target,
                )
                cid = c.id
                s.commit()
                return cid

        return _do

    results = _run_two(propose(sc["b"]), propose(sc["c"]))

    oks = [v for (status, v) in results if status == "ok"]
    errs = [v for (status, v) in results if status == "err"]
    assert len(oks) == 1, f"expected exactly one proposal to win, got {results}"
    assert len(errs) == 1
    assert isinstance(errs[0], (ApplicationError, OwnershipInvariantError, IllegalTransition))

    with Session(engine) as s:
        resp = s.get(Responsibility, sc["resp"])
        assert resp.status is ResponsibilityStatus.transfer_pending
        pending = s.execute(
            select(func.count())
            .select_from(OwnershipContract)
            .where(OwnershipContract.status == ContractStatus.pending)
        ).scalar_one()
        assert pending == 1
