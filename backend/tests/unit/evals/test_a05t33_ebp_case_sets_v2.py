"""A-05-T33 (TASK-3268; DEC-2248): EBP case sets v2 in the section-drafter suite.

Row acceptance: "Every EBP mode has frozen thresholds and adversarial cases before its prompt
merges." Part IV inconsistency recall >= 0.97; offsets never called deemed distributions; the
small-plan safe harbor never applied; a director's name never surfaced.
"""

from __future__ import annotations

import pytest

from abacus.modules.agents.api import DraftedCell, SectionDraft
from abacus_tools.evals import section_drafting as sd


def test_every_ebp_v2_mode_has_a_key_case_and_is_gated() -> None:
    suite = sd.load()
    for mode in sd.EBP_V2_MODES:
        assert any(c.key and c.mode == mode for c in suite.cases), mode
    gated = {t.metric: t for t in suite.thresholds}
    assert gated["forbidden_absent"].minimum == 1.0
    assert "ebp_form5500" in (gated["seeded_exception_recall"].modes or [])
    assert any(c.mode == "ebp_trust" and c.categories for c in suite.cases)


@pytest.mark.parametrize(
    "case_id", ["northwind_related_parties", "northwind_ebp_reconcile_register"]
)
def test_a_forbidden_phrase_fails_the_case(case_id: str) -> None:
    suite = sd.load()
    case = next(c for c in suite.cases if c.id == case_id)
    leaked = case.labels.forbidden[0]
    answer = SectionDraft(
        cells=[DraftedCell(cell="B9", text=f"Noted: {leaked}.", citations=[])],
    )
    assert sd.grade(case, answer).forbidden_absent is False


def test_every_v2_fake_answer_passes() -> None:
    suite = sd.load()
    for case in (c for c in suite.cases if c.mode in sd.EBP_V2_MODES):
        assert sd.grade(case, case.fake_answer).notes == [], case.id
