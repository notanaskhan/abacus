"""TASK-020 (SPEC-005): the evaluation runner's own logic, without containers: suite validation
(AC-2, AC-4, AC-7), graders (AC-5, AC-6), metrics, calibration (AC-8, AC-9), the gate (AC-12),
mutations, the environment guard (AC-16) and the screener's suite file."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from pathlib import Path

import pytest

from abacus_tools.evals import cases, graders, metrics
from abacus_tools.evals.calibration import calibrate, expected_calibration_error
from abacus_tools.evals.gate import reasons
from abacus_tools.evals.observation import Observation
from abacus_tools.evals.suite import (
    Case,
    Expected,
    FakeAnswer,
    InvalidSuite,
    Suite,
    Threshold,
    load,
    validate,
)
from abacus_tools.evals.taxonomy import ADVERSARIAL_CATEGORIES, FAILURE_CATEGORIES
from abacus_tools.synthetic import generate
from abacus_tools.synthetic.connector_fixtures import trial_balance_document

REPO = Path(__file__).resolve().parents[5]
REGISTRIES = {
    "graders": frozenset(graders.GRADERS),
    "metrics": frozenset(metrics.METRICS),
    "mutations": frozenset(cases.MUTATIONS),
}


def _case(
    id: str = "a",
    *,
    stage: str = "screened",
    action: str | None = "ready_for_review",
    categories: frozenset[str] = frozenset(),
    fast: bool = True,
) -> Case:
    return Case(
        id=id,
        mutation="none",
        categories=categories,
        expected=Expected.model_validate({"stage": stage, "action": action}),
        fake_answer=FakeAnswer(action="ready_for_review", confidence=0.9),
        fast=fast,
    )


def _suite(**changes: object) -> Suite:
    base: dict[str, object] = {
        "agent": "evidence.screener",
        "version": 1,
        "covers": frozenset(),
        "cases": (_case(),),
        "graders": ("structured_output",),
        "thresholds": (Threshold(metric="needs_revision_recall", minimum=0.97),),
        "dangerous_error": "needs_revision_recall",
        "repeats": 1,
        "required_pass_rate": 1.0,
        "calibration_tolerance": 0.1,
        "cost_limit_usd": Decimal(5),
    }
    base.update(changes)
    return Suite.model_validate(base)


# --- suites --------------------------------------------------------------------------------------


def test_ac2_the_screeners_suite_file_loads_and_validates() -> None:
    suite = load(REPO / "evals" / "screening" / "suite.yaml")
    validate(suite, **REGISTRIES)
    assert suite.agent == "evidence.screener"
    assert suite.dangerous_error == "needs_revision_recall"


def test_ac4_the_screeners_suite_covers_every_taxonomy_and_adversarial_category() -> None:
    suite = load(REPO / "evals" / "screening" / "suite.yaml")
    assert suite.covers == FAILURE_CATEGORIES | ADVERSARIAL_CATEGORIES


@pytest.mark.parametrize(
    ("changes", "problem"),
    [
        ({"graders": ("nope",)}, "unknown grader"),
        ({"thresholds": (Threshold(metric="nope", minimum=0.5),)}, "unknown metric"),
        (
            {"thresholds": (Threshold(metric="ready_precision", minimum=0.5),)},
            "has no threshold",
        ),
        (
            {
                "thresholds": (Threshold(metric="accuracy", minimum=0.9),),
                "dangerous_error": "accuracy",
            },
            "accuracy alone",
        ),
        ({"covers": frozenset({"unbalanced"})}, "no case covers 'unbalanced'"),
        ({"covers": frozenset({"made_up"})}, "unknown category"),
        ({"cases": (_case(fast=False),)}, "fast subset is empty"),
        ({"cases": (_case("a"), _case("a"))}, "appears twice"),
    ],
)
def test_ac2_ac4_ac7_an_incomplete_suite_is_refused_before_any_model_call(
    changes: dict[str, object], problem: str
) -> None:
    with pytest.raises(InvalidSuite, match=re.escape(problem)):
        validate(_suite(**changes), **REGISTRIES)


def test_ac2_a_screened_case_states_its_action_and_others_none() -> None:
    with pytest.raises(ValueError):
        Expected.model_validate({"stage": "screened"})
    with pytest.raises(ValueError):
        Expected.model_validate({"stage": "failed", "action": "needs_revision"})


def _codes(part: str) -> set[str]:
    return set(re.findall(r"\| `([a-z_]+)` \|", part))


def test_ac4_the_taxonomy_registry_matches_the_protected_document() -> None:
    text = (REPO / "docs" / "product" / "failure-taxonomy.md").read_text()
    failures, adversarial = text.split("## Adversarial content")
    assert _codes(failures) == FAILURE_CATEGORIES
    assert _codes(adversarial.split("## Changing")[0]) == ADVERSARIAL_CATEGORIES


# --- mutations -----------------------------------------------------------------------------------


def _document() -> dict[str, object]:
    tb = generate(7).client_entities[0].trial_balances[-1]
    return trial_balance_document(
        tb, period_start=tb.as_of.replace(month=1, day=1), entity_name="E"
    )


def test_mutations_cover_every_category_and_never_change_their_input() -> None:
    assert set(cases.MUTATIONS) >= FAILURE_CATEGORIES | ADVERSARIAL_CATEGORIES
    original = _document()
    snapshot = json.dumps(original, sort_keys=True)
    for name, mutate in cases.MUTATIONS.items():
        result = mutate(original)
        assert json.dumps(original, sort_keys=True) == snapshot, name
        if name == "unreadable":
            assert isinstance(result, bytes)
            with pytest.raises(json.JSONDecodeError):
                json.loads(result)
        elif name != "none":
            assert result != original, name


def test_the_unbalanced_mutation_declares_totals_that_disagree_between_sides() -> None:
    mutated = cases.MUTATIONS["unbalanced"](_document())
    assert isinstance(mutated, dict)
    totals = mutated["control_totals"]
    assert isinstance(totals, dict)
    assert totals["debit"] != totals["credit"]


# --- graders -------------------------------------------------------------------------------------


def _seen(**kw: object) -> Observation:
    base: dict[str, object] = {
        "case_id": "a",
        "attempt": 1,
        "stage": "screened",
        "action": "ready_for_review",
        "model_action": "ready_for_review",
        "confidence": 0.9,
        "citations_verified": True,
        "contained": True,
        "cost_usd": Decimal("0.001"),
        "budget_usd": Decimal("0.03"),
    }
    base.update(kw)
    return Observation(**base)  # type: ignore[arg-type] -- built from a loose dict for brevity


def test_ac5_deterministic_graders_judge_stage_action_citations_containment_and_budget() -> None:
    case = _case()
    names = ("structured_output", "citations_verified", "untrusted_contained", "within_budget")
    assert all(g.passed for g in graders.grade(names, case, _seen()))
    failing = {
        "structured_output": _seen(action="needs_revision"),
        "citations_verified": _seen(citations_verified=False),
        "untrusted_contained": _seen(contained=False),
        "within_budget": _seen(cost_usd=Decimal("1")),
    }
    for name, seen in failing.items():
        [result] = graders.grade((name,), case, seen)
        assert not result.passed, name


def test_ac6_a_model_judge_without_a_calibration_record_fails_the_case() -> None:
    [result] = graders.grade(("model_judge",), _case(), _seen())
    assert not result.passed
    assert result.reason is not None and result.reason.startswith("grader_error")


def test_an_errored_attempt_never_passes() -> None:
    grades = graders.grade(("within_budget",), _case(), _seen(stage="errored", error="Boom"))
    assert not all(g.passed for g in grades)


# --- metrics and calibration ---------------------------------------------------------------------


def test_metrics_count_what_code_catches_as_caught_and_fail_closed_when_undefined() -> None:
    needs = _case("n", stage="failed_validation", action=None)
    ready = _case("r")
    attempts = [(needs, _seen(stage="failed_validation", action=None)), (ready, _seen())]
    assert metrics.needs_revision_recall(attempts) == 1.0
    assert metrics.ready_precision(attempts) == 1.0
    assert metrics.ready_precision([(needs, _seen(stage="failed", action=None))]) == 0.0
    missed = [(_case("n", action="needs_revision"), _seen(action="ready_for_review"))]
    assert metrics.needs_revision_recall(missed) == 0.0


def test_ac8_ece_weights_each_bands_gap_by_its_share() -> None:
    ece, bands = expected_calibration_error([(0.9, True), (0.9, True), (0.3, True), (0.3, False)])
    assert ece == pytest.approx(0.5 * 0.1 + 0.5 * 0.2)
    assert [b["band"] for b in bands] == [0.3, 0.9]


def test_ac8_ac9_the_recommended_threshold_is_the_lowest_meeting_the_dangerous_metric() -> None:
    unsure = _case("u", action="needs_revision")
    attempts = [
        (unsure, _seen(action="needs_revision", model_action="ready_for_review", confidence=0.45))
    ]
    result = calibrate(attempts, current_below=0.5, dangerous_minimum=0.97)
    assert result.recommended_below == 0.5
    assert result.current_meets_threshold
    assert not calibrate(
        attempts, current_below=0.4, dangerous_minimum=0.97
    ).current_meets_threshold


# --- the gate ------------------------------------------------------------------------------------


def test_ac9_ac12_the_gate_names_every_reason() -> None:
    suite = _suite()
    good = calibrate([], current_below=0.5, dangerous_minimum=0.0)
    bad_calibration = calibrate(
        [(_case(), _seen(confidence=0.1))], current_below=0.5, dangerous_minimum=0.0
    )
    assert reasons(suite, {"needs_revision_recall": 1.0}, good, [], None, 0) == []
    found = reasons(
        suite,
        {"needs_revision_recall": 0.5},
        bad_calibration,
        [Decimal("0.2")],
        Decimal("0.1"),
        1,
    )
    assert found == [
        "threshold:needs_revision_recall",
        "calibration",
        "cost_regression",
        "case_errors",
    ]
    within = reasons(
        suite, {"needs_revision_recall": 1.0}, good, [Decimal("0.11")], Decimal("0.1"), 0
    )
    assert within == []  # 10% over the baseline is allowed (Q5)


# --- the environment guard -----------------------------------------------------------------------


def test_ac16_evaluations_refuse_to_run_outside_synthetic_environments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from abacus.kernel.config import settings
    from abacus_tools.evals import runner

    class Production:
        environment = "production"

    monkeypatch.setattr(runner, "settings", lambda: Production())
    monkeypatch.delenv("CI", raising=False)
    with pytest.raises(runner.RefusedEnvironment):
        runner.guard()
    monkeypatch.setenv("CI", "true")
    runner.guard()
    settings.cache_clear()
