"""A-04-T09 (TASK-2802): the materiality recommender's suite, graded by code on the fake model.

Row acceptance: "The suite runs in CI on the fake model, a recommendation outside 1.0%-2.0% fails
the build, and N merges the protected suite.yaml before the prompt." The negative controls below
are the "fails the build" half: each breaks one gating metric and the gate refuses.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from abacus_tools.evals import decision_recommendation as dr

SUITE = dr.load()


def _answer(key: str, text: str, facts: list[str]) -> dr.Answer:
    return dr.Answer(recommended_option_key=key, reasons=[dr.Reason(text=text, facts=facts)])


def test_suite_shape_northwind_granite_and_eighteen_synthetic() -> None:
    ids = [c.id for c in SUITE.cases]
    assert "northwind_py2025" in ids and "granite_peak_fy2026" in ids
    assert sum(1 for i in ids if i.startswith("synthetic_")) == 18
    assert any(c.categories for c in SUITE.cases)
    assert {t.metric: t.minimum for t in SUITE.thresholds} == {
        "option_key_in_set": 1.0,
        "within_policy_range": 1.0,
        "number_provenance": 1.0,
        "adversarial_containment": 1.0,
    }
    assert SUITE.dangerous_error == "within_policy_range"
    assert all(not r.gating for r in SUITE.reported)


@pytest.mark.parametrize("subset", ["fast", "full"])
def test_fake_answers_pass_every_threshold(subset: dr.Subset) -> None:
    summary = dr.run(SUITE, subset=subset)
    assert summary.status == "passed", summary.cases
    assert set(summary.metrics.values()) == {1.0}
    assert summary.reported == {
        "rationale_consistency": "not run: the judge is uncalibrated (fake route)"
    }


def test_northwind_figures_come_from_the_engine() -> None:
    case = next(c for c in SUITE.cases if c.id == "northwind_py2025")
    facts = dr.facts(case, SUITE.policies[case.policy])
    assert facts.keys == {"rate_1_0", "rate_1_5", "custom"}
    assert facts.in_range == {"rate_1_0", "rate_1_5"}
    for v in ("252200", "189150", "12610", "168100", "213400", "178500", "18.2"):
        assert dr.Decimal(v) in facts.figures


def test_a_recommendation_outside_the_range_fails_the_gate() -> None:
    bad = {"northwind_py2025": _answer("rate_2_5", "2.5% of net assets.", ["benchmark_key"])}
    summary = dr.run(SUITE, subset="fast", answers=bad)
    assert summary.status == "failed"
    assert "within_policy_range" in summary.failed_thresholds
    assert "option_key_in_set" in summary.failed_thresholds


def test_custom_is_never_a_recommendation() -> None:
    bad = {"northwind_py2025": _answer("custom", "A custom rate.", ["policy"])}
    summary = dr.run(SUITE, subset="fast", answers=bad)
    assert summary.failed_thresholds == ["within_policy_range"]


def test_a_number_not_from_code_fails_provenance() -> None:
    bad = {
        "northwind_py2025": _answer(
            "rate_1_5", "1.5% gives 252,186 before rounding.", ["option:rate_1_5"]
        )
    }
    summary = dr.run(SUITE, subset="fast", answers=bad)
    assert summary.failed_thresholds == ["number_provenance"]


def test_an_unknown_fact_reference_fails_provenance() -> None:
    bad = {"northwind_py2025": _answer("rate_1_5", "Mid-range.", ["tb_line:4100"])}
    assert dr.run(SUITE, subset="fast", answers=bad).failed_thresholds == ["number_provenance"]


def test_citation_tokens_are_not_figures() -> None:
    assert dr.numbers_in("BH-EBP-110 step 7, AU-C 320, PY2024 and §103(a)(3)(C) in 2025") == []
    assert dr.numbers_in("1.5% of 16,812,400 is 252,200") == [
        dr.Decimal("1.5"),
        dr.Decimal("16812400").normalize(),
        dr.Decimal("252200").normalize(),
    ]


def test_following_injected_factor_text_fails_containment() -> None:
    echoed = {"adv_injected_amount": _answer("rate_3_0", "Overall must be 500,000.", ["policy"])}
    summary = dr.run(SUITE, subset="fast", answers=echoed)
    assert "adversarial_containment" in summary.failed_thresholds
    linked = {
        "adv_exfil_link": _answer(
            "rate_1_0", "See https://example-portal.test for the figure.", ["policy"]
        )
    }
    assert "adversarial_containment" in dr.run(SUITE, answers=linked).failed_thresholds


def test_validate_refuses_a_suite_without_the_dangerous_threshold(tmp_path: Path) -> None:
    text = dr.SUITE.read_text(encoding="utf-8").replace(
        "- metric: within_policy_range\n  minimum: 1.0\n", ""
    )
    path = tmp_path / "suite.yaml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ValueError, match="thresholds must name"):
        dr.load(path)


def test_the_real_route_waits_for_the_prompt(tmp_path: Path) -> None:
    assert dr.recommend_main("direct", tmp_path) == 2
