"""A-09-T04 (TASK-8053; A-09 §4.2, DF-31; SPEC-658 AC-0.2): the group-audit status rows, read from
the generated registry."""

from __future__ import annotations

from abacus.kernel import _statuses as s


def test_ac0_2_consolidation_and_its_attachments() -> None:
    assert [m.value for m in s.ConsolidationStatus] == ["draft", "finalized", "discarded"]
    assert {m.value for m in s.ConsolidationLockStatus} == {"open", "locked"}
    assert {m.value for m in s.ConsolidationTbStatus} == {
        "missing",
        "attached",
        "not_needed",
        "needs_reauth",
    }


def test_ac0_2_eliminations_decisions_and_deliverables() -> None:
    assert [m.value for m in s.EliminationEntryStatus] == [
        "proposed",
        "approved",
        "posted",
        "rejected",
    ]
    assert {m.value for m in s.GroupMaterialityDecisionStatus} == {"pending", "decided"}
    assert [m.value for m in s.ComponentDeliverableStatus] == [
        "expected",
        "received",
        "reviewed",
        "late",
        "returned",
    ]
