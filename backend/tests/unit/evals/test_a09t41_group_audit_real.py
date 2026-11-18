"""A-09-T41 (DEC-5640): the group audit real-run report's pure parts. Clearance holds only on a
Bedrock run meeting every frozen threshold within the cost baseline and a fresh parity check;
it never clears a firm (client data stays off until the firm opts in)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from abacus_tools.evals import group_audit_real as g
from abacus_tools.evals.group_audit import FROZEN
from abacus_tools.evals.runtime_conformance_real import Attempt, verified

TODAY = date(2026, 11, 18)
PARITY = date(2026, 11, 1)


def _pass(capability: str) -> dict[str, float]:
    return dict(FROZEN[g.SUITES[capability]])


def _attempts(cost: str = "0.05") -> list[Attempt]:
    return [Attempt(f"c{i}", True, i == 0, Decimal(cost)) for i in range(3)]


@pytest.mark.parametrize("capability", sorted(g.SUITES))
def test_a_bedrock_run_meeting_every_threshold_clears_the_route(capability: str) -> None:
    limit = Decimal("0.25")
    c = g.capability_clearance(
        capability,
        "bedrock",
        _pass(capability),
        _attempts(),
        limit,
        last_parity=PARITY,
        today=TODAY,
    )
    assert c["client_data"] == "cleared"
    assert c["firm_opt_in"] == g.FIRM_NOTE


def test_the_direct_route_a_missed_threshold_and_no_baseline_never_clear() -> None:
    cap = "consolidation.elimination_proposer"
    rates = {**_pass(cap), "balanced": 0.99}
    c = g.capability_clearance(
        cap, "direct", rates, _attempts(), None, last_parity=None, today=TODAY
    )
    assert c["client_data"] == "none"
    assert set(c["reasons"]) >= {  # type: ignore[arg-type]
        "not_the_production_route",
        "below_threshold:balanced",
        "cost_regression:no_baseline",
        "route_parity_stale",
    }


def test_a_failed_zero_tolerance_case_or_an_error_never_clears() -> None:
    cap = "ledger.tb_mapper"
    bad = [Attempt("adv", False, True, Decimal("0.05")), Attempt("x", True, False, None)]
    c = g.capability_clearance(
        cap, "bedrock", _pass(cap), bad, Decimal("0.05"), last_parity=PARITY, today=TODAY
    )
    assert {"zero_tolerance_case_failed", "errored"} <= set(c["reasons"])  # type: ignore[arg-type]


def test_the_report_reads_each_capabilitys_baseline_tier_and_is_signed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABACUS_EVAL_SIGNING_KEY", "test-only-key")
    body = g.report(
        "bedrock",
        {cap: (_pass(cap), _attempts()) for cap in g.SUITES},
        last_parity=PARITY,
        today=TODAY,
    )
    caps = body["capabilities"]
    assert isinstance(caps, dict)
    assert caps["ledger.tb_mapper"]["tier"] == "small"
    assert caps["ledger.tb_mapper"]["clearance"]["baseline_usd"] == "0.05"
    assert caps["consolidation.elimination_proposer"]["clearance"]["baseline_usd"] == "0.25"
    assert verified(body)


def test_the_real_run_refuses_without_the_evaluation_stack(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ABACUS_EVAL_STACK", raising=False)
    with pytest.raises(SystemExit):
        g.real_main("bedrock", Path("."))
