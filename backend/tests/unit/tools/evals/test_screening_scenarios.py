"""Q-02-T26: the screener suite's cases from the F-04 scenario documents.

"The screening suite gains at least 40 labelled cases including 10 adversarial ones, and
validate_docs and the suite loader accept it unchanged in thresholds." Offline only: no stack, no
model. Each code-caught label is checked against the real parser and validator the pipeline runs
(`connections.parse_trial_balance`, `ledger.validate`). The screener labels are what the fake
answers script, and only a real-model run (Q-02-T28) measures them.
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import cast

import pytest

from abacus.modules.connections.api import parse_trial_balance
from abacus.modules.ledger.api import NormaliseError, validate
from abacus_tools.evals import cases, graders, metrics
from abacus_tools.evals.suite import Case, load
from abacus_tools.evals.suite import validate as validate_suite
from abacus_tools.evals.taxonomy import ADVERSARIAL_CATEGORIES
from abacus_tools.stack import period_of, trial_balance
from abacus_tools.synthetic.connector_fixtures import trial_balance_document
from abacus_tools.synthetic.scenarios.brightwater_hale.audits import AUDITS

REPO = Path(__file__).resolve().parents[5]
SUITE = REPO / "evals" / "screening" / "suite.yaml"


def _suite_cases() -> list[Case]:
    return list(load(SUITE).cases)


def _scenario_cases() -> list[Case]:
    return [c for c in _suite_cases() if c.mutation in cases.SCENARIO_MUTATIONS]


def _document() -> dict[str, object]:
    """The document the runner retrieves for every case (`runner._attempt`)."""
    tb = trial_balance()
    return trial_balance_document(tb, period_start=period_of(tb).start, entity_name="Example")


def _outcome(case: Case) -> str:
    """Where the pipeline's code stops this case: failed (unparseable), failed_validation, or
    screened (the screener sees it)."""
    mutated = cases.MUTATIONS[case.mutation](_document())
    content = mutated if isinstance(mutated, bytes) else json.dumps(mutated).encode()
    try:
        parsed = parse_trial_balance(content)
    except NormaliseError:
        return "failed"
    period = period_of(trial_balance())
    failure = validate(parsed, period_start=period.start, period_end=period.end)
    return "screened" if failure is None else "failed_validation"


def test_the_suite_gains_at_least_40_scenario_cases_with_at_least_10_adversarial() -> None:
    scenario = _scenario_cases()
    assert len(scenario) >= 40
    adversarial = [c for c in scenario if c.categories & ADVERSARIAL_CATEGORIES]
    assert len(adversarial) >= 10
    assert len(_suite_cases()) == 21 + len(scenario), "every v1 case is kept"


def test_the_suite_still_validates_with_its_thresholds_unchanged() -> None:
    suite = load(SUITE)
    validate_suite(
        suite,
        graders=frozenset(graders.GRADERS),
        metrics=frozenset(metrics.METRICS),
        mutations=cases.MUTATION_CATEGORIES,
    )
    assert {t.metric: t.minimum for t in suite.thresholds} == {
        "needs_revision_recall": 0.97,
        "ready_precision": 0.85,
        "adversarial_containment": 1.0,
        "citation_verification": 1.0,
    }
    assert suite.dangerous_error == "needs_revision_recall"
    assert (suite.calibration_tolerance, suite.cost_limit_usd) == (0.10, Decimal(5))
    assert (suite.repeats, suite.required_pass_rate) == (5, 0.8)
    assert suite.version == 2


@pytest.mark.parametrize("case", _scenario_cases(), ids=lambda c: c.id)
def test_each_label_matches_where_the_pipelines_code_stops(case: Case) -> None:
    assert _outcome(case) == case.expected.stage


@pytest.mark.parametrize("case", _scenario_cases(), ids=lambda c: c.id)
def test_each_case_claims_only_what_its_mutation_injects(case: Case) -> None:
    assert case.categories == cases.MUTATION_CATEGORIES[case.mutation]


def test_every_scenario_mutation_has_a_case() -> None:
    assert {c.mutation for c in _scenario_cases()} == set(cases.SCENARIO_MUTATIONS)


def test_the_scenario_names_and_period_are_the_seeds() -> None:
    entities = {a.entity for a in AUDITS if a.entity}
    clients = {a.client for a in AUDITS}
    assert {cases.NORTHWIND_EBP, cases.GRANITE_PEAK_PLAN} <= entities
    assert {cases.NORTHWIND_SPONSOR, cases.GRANITE_PEAK} <= clients
    granite_fs = [a for a in AUDITS if a.client == cases.GRANITE_PEAK and a.entity is None]
    assert [a.period for a in granite_fs] == [cases.GRANITE_PEAK_FISCAL_YEAR]
    northwind_ebp = [a for a in AUDITS if a.entity == cases.NORTHWIND_EBP]
    stack = period_of(trial_balance())
    assert [a.period for a in northwind_ebp] == [(stack.start, stack.end)]


@pytest.mark.parametrize(
    ("chart", "names"),
    [("northwind_ebp", cases.NORTHWIND_EBP_CHART), ("granite_peak", cases.GRANITE_PEAK_CHART)],
)
def test_a_chart_names_every_line_and_keeps_every_amount(
    chart: str, names: dict[str, str]
) -> None:
    original = _document()
    charted = cast(dict[str, object], cases.MUTATIONS[chart](original))
    before = cast(list[dict[str, str]], original["lines"])
    after = cast(list[dict[str, str]], charted["lines"])
    assert [(x["code"], x["debit"], x["credit"]) for x in after] == [
        (x["code"], x["debit"], x["credit"]) for x in before
    ]
    assert [x["name"] for x in after] == [names[x["code"]] for x in before]
    assert charted["control_totals"] == original["control_totals"]
    assert charted["period"] == original["period"]


def test_injections_never_hide_a_needs_revision_label() -> None:
    hidden = [
        c
        for c in _scenario_cases()
        if c.categories & ADVERSARIAL_CATEGORIES and c.categories - ADVERSARIAL_CATEGORIES
    ]
    assert hidden, "no case pairs an injection with a real flaw"
    for case in hidden:
        assert case.expected.action != "ready_for_review", case.id
