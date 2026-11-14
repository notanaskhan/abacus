"""W-02-T25 (TASK-8014; W-02 §6; DEC-5005): workbench.assistant's eval runs, the pure parts.

The fast subset runs on every agents PR and the full suite nightly, both on the fake model; the
real direct and Bedrock runs need the evaluation account, so here: the cost baseline row, the
clearance rule (fail closed) and the report signature."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from abacus_tools.evals import workbench_assistant_real as real

ROOT = Path(__file__).resolve().parents[4]


def test_the_cost_baseline_is_recorded_for_the_medium_tier() -> None:
    assert real.baseline("medium") == Decimal("0.60")
    assert real.baseline("small") is None


def _attempt(
    case: str, cost: str | None, *, passed: bool = True, de: bool = False
) -> real.Attempt:
    return real.Attempt(case, passed, de, None if cost is None else Decimal(cost))


def test_a_clean_bedrock_run_clears_for_production() -> None:
    verdict = real.clearance("bedrock", [], [_attempt("j11_b2", "0.58")], Decimal("0.60"))
    assert verdict["cleared"] is True and verdict["production"] is True


@pytest.mark.parametrize(
    ("below", "attempts", "limit", "reason"),
    [
        (["citations_verified"], [_attempt("a", "0.5")], Decimal("0.60"),
         "below_threshold:citations_verified"),
        ([], [_attempt("a", None)], Decimal("0.60"), "errored"),
        ([], [_attempt("a", "0.5", passed=False, de=True)], Decimal("0.60"), "de_case_failed"),
        ([], [_attempt("a", "0.70")], Decimal("0.60"), "cost_regression"),
        ([], [_attempt("a", "0.5")], None, "cost_regression:no_baseline"),
        ([], [], Decimal("0.60"), "no_attempts"),
    ],
)  # fmt: skip
def test_clearance_fails_closed(
    below: list[str], attempts: list[real.Attempt], limit: Decimal | None, reason: str
) -> None:
    verdict = real.clearance("bedrock", below, attempts, limit)
    assert verdict["cleared"] is False
    assert reason in verdict["reasons"]  # type: ignore[operator]


def test_a_direct_run_never_clears_for_production() -> None:
    verdict = real.clearance("direct", [], [_attempt("a", "0.5")], Decimal("0.60"))
    assert verdict["production"] is False


def test_the_report_is_signed_and_verified(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(real.SIGNING_KEY_ENV, "test-key")
    report = real.signed(real.report("bedrock", "medium", {"x": 1.0}, [], [_attempt("a", "0.5")]))
    assert real.verified(report)
    tampered = {**report, "tier": "small"}
    assert not real.verified(tampered)


def test_a_real_run_refuses_without_the_evaluation_stack(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("ABACUS_EVAL_STACK", raising=False)
    with pytest.raises(SystemExit):
        real.real_main("bedrock", tmp_path)
