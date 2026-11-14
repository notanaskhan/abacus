"""I-02-T20 (TASK-7940; I-02 §6.3; DEC-4935): eval runs for `briefing.today`.

Row acceptance: "Committed Bedrock and direct reports meet every frozen threshold (DE-3 to DE-6
cases at 1.0, judge at least 4) at no more than $0.10 per briefing."

The pure parts of the real run, without the evaluation account: clearance's every reason, the cost
cap and baseline, the judge floor, the p95, the signed report, the cadence (fast on PRs, full
nightly) and the refusal without the account's stack.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, cast

import pytest

from abacus_tools.evals import briefing_today_real as real
from abacus_tools.evals.briefing_today import FROZEN

ROOT = Path(__file__).resolve().parents[4]
TODAY = date(2028, 6, 20)
ALL = {g: 1.0 for g in FROZEN}


def _attempts(cost: str = "0.06", judge: float = 4.4, n: int = 40) -> list[real.BriefingAttempt]:
    return [real.BriefingAttempt(f"c{i}", True, i % 2 == 0, Decimal(cost), 8000 + i * 50, judge)
            for i in range(n)]  # fmt: skip


def _clear(route: str = "bedrock", **kw: object) -> dict[str, object]:
    attempts = kw.pop("attempts", _attempts())
    return real.clearance(route, kw.pop("rates", ALL), attempts, Decimal("0.10"),  # type: ignore[arg-type] -- stand-in
                          last_parity=date(2028, 6, 1), today=TODAY)  # fmt: skip


def test_a_bedrock_run_meeting_everything_clears() -> None:
    found = _clear()
    assert found["client_data"] == "cleared" and found["reasons"] == []
    assert found["p95_within_budget"] is True


def test_the_direct_route_never_clears_on_its_own() -> None:
    assert "not_the_production_route" in _clear("direct")["reasons"]  # type: ignore[operator] -- stand-in


@pytest.mark.parametrize(
    ("kwargs", "reason"),
    [
        ({"rates": ALL | {"number_provenance": 0.99}}, "below_threshold:number_provenance"),
        ({"attempts": _attempts(judge=3.9)}, "judge_below_floor"),
        ({"attempts": _attempts(cost="0.12")}, "over_cost_cap"),
        (
            {"attempts": [real.BriefingAttempt("x", False, True, Decimal("0.05"), 9000, 4.5)]},
            "zero_tolerance_case_failed",
        ),
        ({"attempts": [real.BriefingAttempt("x", True, False, None, None, 4.5)]}, "errored"),
    ],
)
def test_each_shortfall_is_named(kwargs: dict[str, object], reason: str) -> None:
    found = _clear(**cast(dict[str, Any], kwargs))  # Any: a test stand-in
    assert found["client_data"] == "none" and reason in found["reasons"]  # type: ignore[operator] -- stand-in


def test_p95_is_nearest_rank() -> None:
    assert real.p95([100] * 19 + [5000]) == 100
    assert real.p95([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]) == 19
    assert real.p95([]) is None


def test_the_baseline_row_is_the_specs_budget() -> None:
    from abacus_tools.evals.tax_return_real import baseline

    assert baseline("briefing.today", "medium") == Decimal("0.10")


def test_the_report_is_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_EVAL_SIGNING_KEY", "k")
    body = real.report("bedrock", ALL, _attempts(), last_parity=date(2028, 6, 1), today=TODAY)
    assert real.verified(body)
    tampered = body | {"cases": 1}
    assert not real.verified(tampered)


def test_without_the_accounts_stack_the_run_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABACUS_EVAL_STACK", raising=False)
    with pytest.raises(SystemExit):
        real.real_main("bedrock", Path("."))


def test_the_cadence_fast_on_prs_full_nightly() -> None:
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    nightly = (ROOT / ".github/workflows/evals.yml").read_text(encoding="utf-8")
    assert "run: make evals-briefing-fast" in ci
    assert "run: make evals-briefing-full" in nightly
