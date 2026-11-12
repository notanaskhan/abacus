"""T-04-T43 (TASK-7415; DEC-4411): the tax suites' real-route report: per-capability clearance
(every frozen threshold, Bedrock only, route parity under 90 days, cost within ADR-070's +10 %),
the TRI note, signing, and the refusal without the evaluation account's stack."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from abacus_tools.evals import tax_return_real as real
from abacus_tools.evals.runtime_conformance_real import Attempt
from abacus_tools.evals.tax_return import FROZEN

TODAY = date(2028, 4, 10)
FRESH = TODAY - timedelta(days=30)
PASS = [Attempt("a", True, False, Decimal("0.02")), Attempt("b", True, True, Decimal("0.03"))]


def _rates(capability: str) -> dict[str, float]:
    return dict(FROZEN[capability])


def test_a_bedrock_run_meeting_everything_clears_client_data() -> None:
    found = real.capability_clearance(
        "tax.return_analyst.residency", "bedrock", _rates("tax.return_analyst.residency"), PASS,
        Decimal("0.025"), last_parity=FRESH, today=TODAY,
    )  # fmt: skip
    assert found["client_data"] == "cleared" and found["reasons"] == []
    assert found["tri"] == real.TRI_NOTE


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"route": "direct"}, "not_the_production_route"),
        ({"route": "openai"}, "unknown_route"),
        ({"limit": None}, "cost_regression:no_baseline"),
        ({"limit": Decimal("0.01")}, "cost_regression"),
        ({"last_parity": TODAY - timedelta(days=90)}, "route_parity_stale"),
        ({"last_parity": None}, "route_parity_stale"),
        ({"attempts": []}, "no_attempts"),
        ({"attempts": [Attempt("a", True, False, None)]}, "errored"),
        ({"attempts": [Attempt("a", False, True, Decimal("0.02"))]}, "zero_tolerance_case_failed"),
    ],
)
def test_each_failing_condition_keeps_client_data_none(
    change: dict[str, object], reason: str
) -> None:
    args: dict[str, object] = {
        "route": "bedrock", "attempts": PASS, "limit": Decimal("0.025"), "last_parity": FRESH,
    }  # fmt: skip
    args.update(change)
    found = real.capability_clearance(
        "issues.fix_runner",
        str(args["route"]),
        _rates("issues.fix_runner"),
        args["attempts"],  # type: ignore[arg-type]
        args["limit"],  # type: ignore[arg-type]
        last_parity=args["last_parity"],  # type: ignore[arg-type]
        today=TODAY,
    )
    assert found["client_data"] == "none"
    assert reason in found["reasons"]  # type: ignore[operator]


def test_a_threshold_below_its_frozen_floor_or_unmeasured_is_named() -> None:
    rates = _rates("tax.return_drafter")
    rates["change_accuracy"] = 0.94
    del rates["consent_refusal_7216"]
    assert real.below_thresholds("tax.return_drafter", rates) == [
        "change_accuracy",
        "consent_refusal_7216",
    ]


def test_parity_is_fresh_under_90_days_only() -> None:
    assert real.parity_fresh(TODAY - timedelta(days=89), TODAY)
    assert not real.parity_fresh(TODAY - timedelta(days=90), TODAY)
    assert not real.parity_fresh(TODAY + timedelta(days=1), TODAY)


def test_the_report_is_signed_and_verifies(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("ABACUS_EVAL_SIGNING_KEY", "test-key")
    baselines = tmp_path / "baselines.yaml"
    baselines.write_text("issues.fix_runner:\n  small: '0.025'\n", encoding="utf-8")
    original = real.baseline

    def from_file(capability: str, tier: str) -> Decimal | None:
        return original(capability, tier, baselines)

    monkeypatch.setattr(real, "baseline", from_file)
    body = real.report(
        "bedrock",
        "small",
        {"issues.fix_runner": (_rates("issues.fix_runner"), PASS)},
        last_parity=FRESH,
        today=TODAY,
    )
    assert body["suite"] == "tax_return" and "signature" in body
    assert real.verified(body)
    tampered = {**body, "route": "direct"}
    assert not real.verified(tampered)


def test_the_real_run_refuses_without_the_evaluation_account(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="evaluation account"):
        real.real_main("bedrock", tmp_path)
    with pytest.raises(SystemExit, match="unknown route"):
        real.real_main("openai", tmp_path)
