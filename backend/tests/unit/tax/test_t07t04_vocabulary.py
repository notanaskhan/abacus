"""T-07-T04 (TASK-8018; T-07 §T04, DF-31; SPEC-656 AC-15.2; DEC-5008): the trusts-and-estates
status rows, read from the generated registry."""

from __future__ import annotations

from abacus.kernel import _statuses as s


def test_ac15_2_the_interpretation_states_follow_the_epic() -> None:
    assert [m.value for m in s.InstrumentInterpretationStatus] == [
        "unread",
        "reading",
        "proposed",
        "adopted",
        "approved",
        "reopened",
    ]


def test_the_other_new_objects_are_generated() -> None:
    assert {m.value for m in s.InstrumentSegmentationStatus} == {"segmented", "needs_review"}
    assert {m.value for m in s.SixtyFiveDayElectionStatus} == {"not_made", "elected"}
    assert {m.value for m in s.EstateInventoryItemStatus} == {"gathering_support", "valued"}
    assert {m.value for m in s.EstateDeductionElectionStatus} == {
        "none",
        "s642g_pending",
        "s642g_706",
        "s642g_1041",
    }
    assert {m.value for m in s.EstateComputationLabelStatus} == {
        "accrued_tie_out_shadow",
        "engine_import",
    }
