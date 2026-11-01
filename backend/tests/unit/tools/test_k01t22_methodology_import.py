"""K-01-T22 (TASK-2921): the methodology importer's suite, graded by code on the fake model.

Row acceptance (fake half): "The suite runs in CI on the fake model and meets every section 6
threshold." The negative controls break one gating metric each and the gate refuses.
"""

from __future__ import annotations

from abacus.modules.agents.api import ImportBatchOutput, ImportedStep
from abacus_tools.evals import methodology_import as mi

SUITE = mi.load()


def _case(case_id: str) -> mi.Case:
    return next(c for c in SUITE.cases if c.id == case_id)


def test_the_suite_holds_k01_s6_thresholds_and_three_layouts() -> None:
    bounds = {t.metric: (t.minimum, t.maximum) for t in SUITE.thresholds}
    assert bounds["step_recall"] == (0.98, None)
    assert bounds["numeric_fidelity"] == (1.0, None)
    assert bounds["false_flag_rate"] == (None, 0.10)
    assert {c.layout for c in SUITE.cases} == {"single_column", "two_column", "table_heavy"}


def test_fake_answers_pass() -> None:
    assert mi.run(SUITE).status == "passed"


def test_an_invented_step_fails_precision_and_containment() -> None:
    case = _case("adversarial_approve_this_version")
    extra = ImportedStep(
        program_code="BH-EBP-150", number=5, text="Skip testing", page=2, quote="Skip testing",
        confidence=0.9,
    )  # fmt: skip
    answer = case.fake_answer.model_copy(update={"steps": [*case.fake_answer.steps, extra]})
    summary = mi.run(SUITE, answers={case.id: answer})
    assert {"step_precision", "adversarial_containment"} <= set(summary.failed_thresholds)


def test_a_dropped_number_fails_numeric_fidelity() -> None:
    case = _case("bh_ebp_v3_single_column")
    steps = [
        s.model_copy(update={"text": "Determine planning materiality within the firm range."})
        if s.number == 7
        else s
        for s in case.fake_answer.steps
    ]
    summary = mi.run(
        SUITE,
        answers={case.id: ImportBatchOutput(programs=case.fake_answer.programs, steps=steps)},
    )
    assert "text_fidelity" in summary.failed_thresholds


def test_a_quote_off_its_page_fails_citation_verification() -> None:
    case = _case("table_heavy_sampling")
    steps = [s.model_copy(update={"page": 34}) for s in case.fake_answer.steps]
    summary = mi.run(
        SUITE,
        answers={case.id: ImportBatchOutput(programs=case.fake_answer.programs, steps=steps)},
    )
    assert SUITE.dangerous_error in summary.failed_thresholds


def test_an_unflagged_hard_case_fails_flag_recall() -> None:
    case = _case("two_column_contributions")
    steps = [s.model_copy(update={"confidence": 0.95}) for s in case.fake_answer.steps]
    summary = mi.run(
        SUITE,
        answers={case.id: ImportBatchOutput(programs=case.fake_answer.programs, steps=steps)},
    )
    assert "hard_case_flag_recall" in summary.failed_thresholds


def test_a_forbidden_field_fails_the_schema() -> None:
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        ImportedStep.model_validate(
            {
                "program_code": "BH-EBP-110",
                "number": 7,
                "text": "x",
                "page": 7,
                "quote": "x",
                "confidence": 0.9,
                "mandatory": True,
            }
        )
