"""P-04-T16: the projector's reconcile is a pure plan, and the C13 slot refuses what the worker
could never deliver."""

from __future__ import annotations

import importlib
import uuid
from collections.abc import Sequence
from datetime import date

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.review.gates import (
    C13_EVENTS,
    Existing,
    GateSource,
    OpenGate,
    RowValues,
    gate_sources,
    plan,
    register_gate_source,
    source_event_id,
)

E = uuid.uuid4()


def _row(subject: uuid.UUID, state: str = "open") -> Existing:
    return Existing(uuid.uuid4(), subject, state, None, None)


def test_a_new_subject_is_inserted_and_a_gone_one_closes() -> None:
    kept, gone, new = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    rows = [_row(kept), _row(gone)]
    todo = plan(rows, [OpenGate(kept, E), OpenGate(new, E)])
    assert [g.subject_id for g in todo.inserts] == [new]
    # I-01-T04: an update carries the row's values (state, assignment, Home facts).
    assert todo.updates == ((rows[1].id, RowValues("done", None, None)),)


def test_the_same_answer_twice_plans_nothing() -> None:
    a, b = uuid.uuid4(), uuid.uuid4()
    rows = [_row(a), _row(b, "done")]
    assert plan(rows, [OpenGate(a, E)]).empty


def test_a_subject_waiting_again_reopens_with_its_assignee_and_due_date() -> None:
    a, who = uuid.uuid4(), uuid.uuid4()
    row = _row(a, "done")
    todo = plan([row], [OpenGate(a, E, assignee_user_id=who, due_on=date(2027, 1, 4))])
    assert todo.updates == ((row.id, RowValues("open", who, date(2027, 1, 4))),)


def test_a_voided_gate_stays_voided() -> None:
    a = uuid.uuid4()
    assert plan([_row(a, "voided")], [OpenGate(a, E)]).empty
    assert plan([_row(a, "voided")], []).empty


def test_source_event_ids_are_stable_per_event_and_subject() -> None:
    event, a, b = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert source_event_id(event, "x", a) == source_event_id(event, "x", a)
    assert source_event_id(event, "x", a) != source_event_id(event, "x", b)
    assert source_event_id(event, "x", a) != source_event_id(uuid.uuid4(), "x", a)


async def _none(_t: TenantContext, _e: uuid.UUID | None) -> Sequence[OpenGate]:
    return []


@pytest.mark.parametrize(
    ("subject", "kind", "events"),
    [
        ("Bad Name", "proposal", frozenset({"proposal.recorded"})),
        ("thing", "approval", frozenset({"proposal.recorded"})),  # not a DF-25 kind
        ("thing", "proposal", frozenset({"thing.happened"})),  # not subscribed (C13)
        ("thing", "proposal", frozenset[str]()),
    ],
)
def test_the_slot_refuses_what_it_cannot_project(
    subject: str, kind: str, events: frozenset[str]
) -> None:
    with pytest.raises(ValueError):
        register_gate_source(GateSource(subject, kind, "review.read", events, _none))


def test_the_agents_four_proposals_are_registered() -> None:
    importlib.import_module("abacus.modules.agents.api")  # registers at import

    found = {s.subject_type: s for s in gate_sources()}
    assert {"screening_result", "upload_review", "inbox_match", "guidance_draft"} <= set(found)
    assert all(found[k].kind == "proposal" for k in ("screening_result", "inbox_match"))
    assert all(s.events <= C13_EVENTS for s in found.values())
