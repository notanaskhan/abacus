"""A-04-T33 (TASK-3266; DEC-2246): the soc1 case set in the one section-drafter suite.

Row acceptance: frozen thresholds and adversarial cases for mode `soc1` before its prompt merges
(A-04-T35). The suite loads and validates; soc1 has a key case, three layouts, adversarial cases,
and its exception recall and fact agreement are gated.
"""

from __future__ import annotations

from abacus_tools.evals import section_drafting as sd


def test_soc1_has_a_key_case_three_layouts_and_adversarial_cases() -> None:
    suite = sd.load()
    soc1 = [c for c in suite.cases if c.mode == "soc1"]
    assert any(c.key for c in soc1)
    assert len([c for c in soc1 if not c.categories]) >= 3
    assert {"prompt_injection", "exfiltration_link"} <= {k for c in soc1 for k in c.categories}


def test_soc1_exception_recall_and_fact_agreement_are_gated() -> None:
    suite = sd.load()
    gated = {t.metric: t for t in suite.thresholds}
    assert "soc1" in (gated["seeded_exception_recall"].modes or [])
    assert "soc1" in (gated["line_agreement"].modes or [])
    assert gated["seeded_exception_recall"].minimum >= 0.97
    assert "soc1" in sd.APPLIES["seeded_exception_recall"]


def test_every_soc1_fake_answer_passes_the_graders() -> None:
    suite = sd.load()
    for case in (c for c in suite.cases if c.mode == "soc1"):
        result = sd.grade(case, case.fake_answer)
        assert result.reserved_actions_absent is not False, case.id
        assert result.adversarial_containment is not False, case.id
        assert result.seeded_exception_recall in (None, 1.0), case.id
