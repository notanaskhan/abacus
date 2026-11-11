"""P-10-T46 (TASK-7315; SPEC-647 §6; DEC-4314): the real runs' report, cost gate and signature.

Row acceptance: "Committed Bedrock and direct reports meet every section 6 threshold, and cost per
case is recorded as the baseline." The runs are the evaluation account's; this proves the gate
they pass through fails closed."""

from __future__ import annotations

from decimal import Decimal

import pytest

from abacus_tools.evals import runtime_conformance_real as real


def _attempts(*costs: str | None, failed_de: bool = False) -> list[real.Attempt]:
    return [
        real.Attempt(
            f"c{i}", not (failed_de and i == 0), i == 0, None if c is None else Decimal(c)
        )
        for i, c in enumerate(costs)
    ]


def test_a_bedrock_run_within_10_percent_of_its_baseline_clears_for_production() -> None:
    result = real.clearance("bedrock", [], _attempts("0.010", "0.011", "0.012"), Decimal("0.011"))
    assert result["cleared"] is True and result["production"] is True
    assert result["median_cost_usd"] == "0.011"


def test_a_direct_run_clears_but_never_for_production() -> None:
    result = real.clearance("direct", [], _attempts("0.01"), Decimal("0.01"))
    assert result["cleared"] is True and result["production"] is False


@pytest.mark.parametrize(
    ("below", "attempts", "limit", "reason"),
    [
        ([], _attempts("0.02"), None, "cost_regression:no_baseline"),
        ([], _attempts("0.0122"), Decimal("0.011"), "cost_regression"),
        (
            ["citations_verified"],
            _attempts("0.01"),
            Decimal("0.01"),
            "below_threshold:citations_verified",
        ),
        ([], _attempts("0.01", None), Decimal("0.01"), "errored"),
        ([], _attempts("0.01", failed_de=True), Decimal("0.01"), "de_case_failed"),
        ([], [], Decimal("0.01"), "no_attempts"),
    ],
)
def test_the_gate_fails_closed_with_its_reason(
    below: list[str], attempts: list[real.Attempt], limit: Decimal | None, reason: str
) -> None:
    result = real.clearance("bedrock", below, attempts, limit)
    assert result["cleared"] is False and reason in result["reasons"]  # type: ignore[operator]


def test_a_signed_report_verifies_and_a_changed_one_does_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(real.SIGNING_KEY_ENV, "k" * 32)
    report = real.signed({"suite": "runtime_conformance", "route": "bedrock", "cases": 61})
    assert real.verified(report)
    assert not real.verified({**report, "cases": 60})


def test_the_real_run_refuses_without_the_evaluation_stack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    monkeypatch.delenv("ABACUS_EVAL_STACK", raising=False)
    with pytest.raises(SystemExit):
        real.real_main("bedrock", tmp_path)  # type: ignore[arg-type]
