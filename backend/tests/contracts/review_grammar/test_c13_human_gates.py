# ac-test-author: ayushkbhatia
"""C13 consumer contract (P-04-T17, TASK-1279): what I-01 and every gate owner build against.

From `docs/contracts/review-grammar.md` ("Human gates (C13 read)", §2's "What waits on me" row),
P-04 §4.2 (`human_gates`), DF-25 and DEC-320 (the slot, the fixed event set, one row per subject):
- the kind taxonomy is DF-25's seven kinds, the same on the wire, in the table's CHECK and in the
  slot, and the slot refuses any other kind;
- a source may name only the fixed C13 events, because the worker's subscriptions are fixed before
  owners register; the worker hands every one of them to the projector;
- the read is a firm read: no agent, system or client principal holds `human_gate.read`;
- the row carries identifiers only: labels come from the owner at read time.

Boundary: `review.api` (the slot), the OpenAPI document, the permission matrix, the worker's
publisher, and the migrations as the database's own statement of the CHECKs.
"""

from __future__ import annotations

import uuid
from typing import Final, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity.authz.matrix import RULES
from abacus.modules.review import api as review_api
from abacus.modules.review.api import C13_EVENTS, GateSource, OpenGate, register_gate_source
from abacus.worker import __main__ as worker_main

from ._c3 import PATHS, SCHEMAS, Json, migration

# DF-25 (P-04 §4.2; contract "Human gates (C13 read)").
DF25: Final = [
    "decision",
    "sign_off_request",
    "proposal",
    "send",
    "final_approval",
    "export",
    "release",
]
# DEC-320's fixed set, plus `fulfilment.voided` (R-01 Story 2.2: a voided rule link's version
# leaves nothing waiting, as a withdrawal does).
EVENTS: Final = {
    "proposal.recorded",
    "guidance_draft.decided",
    "review_decision.recorded",
    "inbox_file.sorted",
    "evidence_version.withdrawn",
    "fulfilment.voided",
}
# Contract §2: firm admin, practice leader (in scope), quality partner, engagement partner,
# manager, senior, staff, reviewer, EQR reviewer.
READERS: Final = {
    "firm_admin",
    "practice_leader",
    "quality_partner",
    "engagement_partner",
    "manager",
    "senior",
    "staff",
    "reviewer",
    "eqr_reviewer",
}


async def _nothing(tenant: TenantContext, engagement_id: uuid.UUID | None) -> list[OpenGate]:
    return []


def _source(
    subject_type: str, kind: str = "decision", events: frozenset[str] | None = None
) -> GateSource:
    return GateSource(
        subject_type,
        kind,
        "decision.read",
        events if events is not None else frozenset({"proposal.recorded"}),
        _nothing,
    )


def test_c13_the_wire_kinds_are_the_df25_taxonomy() -> None:
    gate = SCHEMAS["HumanGateOut"]
    props = cast(dict[str, Json], gate["properties"])
    assert props["kind"]["enum"] == DF25
    assert props["state"]["enum"] == ["open", "done", "voided"]


def test_c13_the_table_checks_the_same_kinds_and_states() -> None:
    m93 = migration("0093_review_core.py")
    table = m93[m93.index("CREATE TABLE human_gates") :]
    table = table[: table.index('"""')]
    for kind in DF25:
        assert f"'{kind}'" in table, kind
    assert "state IN ('open', 'done', 'voided')" in table


def test_c13_one_row_per_subject_is_a_database_rule() -> None:
    """DEC-320: two events about one subject, delivered at once, insert one row."""
    m152 = migration("0152_projection_keys.py")
    assert "human_gates_one_per_subject ON human_gates" in m152
    assert "(tenant_id, kind, subject_ref)" in m152


def test_c13_the_row_carries_identifiers_not_labels() -> None:
    """Labels come from the subject's owner at read time; the projection stores none."""
    props = cast(dict[str, Json], SCHEMAS["HumanGateOut"]["properties"])
    assert set(props) == {
        "id",
        "kind",
        "subject",
        "engagement_id",
        "work_item_id",
        "client_id",
        "assignee_user_id",
        "role",
        "due_on",
        "state",
        "created_at",
    }


def test_c13_the_read_is_the_list_envelope_with_counts_per_kind() -> None:
    op = PATHS["/v1/human-gates"]["get"]
    assert op["x-abacus-action"] == "human_gate.read"
    names = {cast(str, p["name"]) for p in cast(list[Json], op["parameters"])}
    assert {"assignee", "kind", "engagement_id", "cursor", "limit"} <= names
    page = SCHEMAS["ListPage_HumanGateOut_"]
    assert {"items", "total", "counts", "next_cursor"} <= set(cast(Json, page["properties"]))


def test_c13_only_firm_people_read_what_waits_on_them() -> None:
    decisions = RULES["human_gate.read"].decisions
    granted = {role for role, d in decisions.items() if d != "deny"}
    assert granted == READERS
    for principal in ("agent", "system", "client_admin", "client_contributor"):
        assert decisions.get(principal, "deny") == "deny", principal


# P-04-T19 (DEC-402): review's other consumer, the stale sign-off detector, on the owners'
# change events. No event is in both sets, so every C13 event still reaches the projector.
STALE_EVENTS: Final = {"trial_balance.version_created", "workpaper.content_changed"}


def test_c13_the_event_set_is_fixed() -> None:
    assert set(C13_EVENTS) == EVENTS
    assert set(review_api.SUBSCRIPTIONS) == EVENTS | STALE_EVENTS
    assert not EVENTS & STALE_EVENTS


def test_c13_the_worker_hands_every_c13_event_to_the_projector() -> None:
    built = worker_main.publisher()
    for event in sorted(EVENTS):
        assert review_api.SUBSCRIPTIONS[event] in built.handlers[event], event


@pytest.mark.parametrize("kind", ["approval", "task", "Decision", "", "sign_off"])
def test_c13_the_slot_refuses_a_kind_outside_df25(kind: str) -> None:
    with pytest.raises(ValueError):
        register_gate_source(_source(f"consumer_bad_kind_{len(kind)}", kind=kind))


@pytest.mark.parametrize(
    "events",
    [
        frozenset({"engagement.status_changed"}),
        frozenset({"proposal.recorded", "sign_off.recorded"}),
        frozenset[str](),
    ],
)
def test_c13_the_slot_refuses_an_event_outside_the_fixed_set(events: frozenset[str]) -> None:
    with pytest.raises(ValueError):
        register_gate_source(_source(f"consumer_bad_events_{len(events)}", events=events))


@pytest.mark.parametrize("subject_type", ["Decision", "consumer-gate", "1gate", ""])
def test_c13_the_slot_refuses_a_subject_type_that_is_not_snake_case(subject_type: str) -> None:
    with pytest.raises(ValueError):
        register_gate_source(_source(subject_type))


def test_c13_an_owner_registers_its_subject_type_once() -> None:
    """Two owners claiming one subject type would project one subject twice."""
    register_gate_source(_source("consumer_registered_once"))
    with pytest.raises(ValueError):
        register_gate_source(_source("consumer_registered_once", kind="export"))
