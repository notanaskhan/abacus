"""F-04-T30 (TASK-1319; F-04.30, F-04.31): the data-layer invariant checker fails on each injected
violation and passes on a clean window. INV-1's human-only actions come from the register and from
the generated permission matrix's agent-denied cells."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.modules.identity.api import RULES
from abacus_tools.harness.invariants import (
    AuditRow,
    agent_denied_actions,
    check,
    check_inv1,
    check_inv5,
    human_only,
)

PERSON = uuid4()
USERS = frozenset({PERSON})


def _agent(action: str, seq: int = 1) -> AuditRow:
    return AuditRow(seq, "agent", "agent:run", action, on_behalf_of_user_id=PERSON)


def test_inv1_actions_derive_from_the_generated_matrix() -> None:
    denied = agent_denied_actions()
    assert denied == {a for a, r in RULES.items() if r.decisions.get("agent") == "deny"}
    assert "acceptance.decide" in denied
    assert "report.release" in denied


@pytest.mark.parametrize(
    ("matrix_action", "audit_action"),
    [
        ("acceptance.decide", "acceptance.decided"),
        ("report.release", "report.released"),
        ("report.approve", "report.approved"),
    ],
)
def test_inv1_a_matrix_verb_covers_its_audit_action(matrix_action: str, audit_action: str) -> None:
    assert human_only(audit_action, frozenset({matrix_action}), frozenset())


def test_inv1_send_covers_sent() -> None:
    assert human_only("follow_up.sent", frozenset({"follow_up.send"}), frozenset())
    assert not human_only("follow_up.drafted", frozenset({"follow_up.send"}), frozenset())


def test_inv1_an_injected_agent_decision_from_the_register_fails() -> None:
    action = sorted(HUMAN_ONLY_ACTIONS)[0]
    found = check_inv1([_agent(action)])
    assert [(v.invariant, v.action) for v in found] == [("INV-1", action)]


def test_inv1_an_injected_agent_decision_from_the_matrix_alone_fails() -> None:
    found = check_inv1([_agent("widget.approved")], denied=frozenset({"widget.approve"}))
    assert [v.invariant for v in found] == ["INV-1"]


def test_inv1_a_policy_row_of_a_human_only_action_fails_too() -> None:
    row = AuditRow(1, "policy", "policy:p", "report.released", policy_ref="P v1")
    assert [v.invariant for v in check_inv1([row])] == ["INV-1"]


def test_inv1_an_agent_proposing_passes() -> None:
    assert check_inv1([_agent("proposal.created")]) == []


def test_inv5_an_agent_row_without_its_person_fails() -> None:
    row = AuditRow(1, "agent", "agent:run", "proposal.created")
    found = check_inv5([row], USERS)
    assert [(v.invariant, v.detail) for v in found] == [
        ("INV-5", "agent row names no person it acted for")
    ]


def test_inv5_a_human_row_naming_an_unknown_user_fails() -> None:
    row = AuditRow(1, "human", str(uuid4()), "note.added")
    assert [v.detail for v in check_inv5([row], USERS)] == ["human actor is not a known user"]


def test_inv5_a_human_row_with_a_non_uuid_actor_fails() -> None:
    row = AuditRow(1, "human", "not-a-uuid", "note.added")
    assert [v.invariant for v in check_inv5([row], USERS)] == ["INV-5"]


def test_inv5_a_policy_row_without_its_ref_fails() -> None:
    row = AuditRow(1, "policy", "policy:p", "rule.applied")
    assert [v.detail for v in check_inv5([row], USERS)] == ["policy row has no policy_ref"]


def test_inv5_an_unknown_actor_kind_fails() -> None:
    row = AuditRow(1, "robot", "r", "x.y")
    assert [v.detail for v in check_inv5([row], USERS)] == ["unknown actor_kind=robot"]


def test_a_clean_window_passes() -> None:
    rows = [
        AuditRow(1, "human", str(PERSON), "evidence.accepted"),
        _agent("proposal.created", 2),
        AuditRow(3, "system", "audit_chain:seal", "audit_chain.sealed"),
        AuditRow(4, "support", "staff:x", "support_session.started"),
        AuditRow(5, "policy", "policy:p", "rule.applied", policy_ref="Autonomy v2"),
    ]
    assert check(rows, USERS) == []


def test_a_violation_names_the_invariant_seq_and_action() -> None:
    found = check([_agent("report.released", seq=42)], USERS)
    assert str(found[0]) == "INV-1 at seq 42 (report.released): actor_kind=agent"
    assert isinstance(PERSON, UUID)
