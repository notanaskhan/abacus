"""T-05-T64 (TASK-7941; T-05 §6; DEC-4936): Bedrock clearance for the four entity capabilities.

Row acceptance: "All four capabilities show client_data cleared with committed Bedrock reports by
Fri Jun 23, 2028."

The pure parts of the clearance run, without the evaluation account: the frozen thresholds come
from the fake suites (never lowered), each capability's baseline row is its spec's budget, only a
Bedrock run with fresh parity clears, every shortfall is named, reports are signed, and the run
refuses without the account's stack.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest

from abacus_tools.evals import tax_entity, tax_entity_part2
from abacus_tools.evals import tax_entity_real as real
from abacus_tools.evals.runtime_conformance_real import Attempt
from abacus_tools.evals.tax_return_real import baseline

TODAY = date(2028, 6, 20)
FRESH = date(2028, 6, 1)


def _ok(suite: str) -> dict[str, float]:
    return dict(real.FROZEN[suite])


def _attempts(cost: str) -> list[Attempt]:
    return [Attempt(f"c{i}", True, i % 3 == 0, Decimal(cost)) for i in range(30)]


@pytest.mark.parametrize(
    ("suite", "cost"),
    [("tax_account_mapper", "0.04"), ("tax_agreement_reader", "0.18"),
     ("tax_memo_drafter", "0.27"), ("tax_recommender_modes", "0.02")],
)  # fmt: skip
def test_each_capability_clears_on_bedrock_within_its_budget(suite: str, cost: str) -> None:
    found = real.clearance(suite, "bedrock", _ok(suite), _attempts(cost), last_parity=FRESH,
                           today=TODAY)  # fmt: skip
    assert found["client_data"] == "cleared", found["reasons"]


def test_the_thresholds_are_the_frozen_suites_own() -> None:
    assert real.FROZEN["tax_account_mapper"] == tax_entity.FROZEN["tax_account_mapper"]
    assert real.FROZEN["tax_memo_drafter"] == tax_entity_part2.FROZEN["tax_memo_drafter"]


def test_the_baseline_rows_are_each_specs_budget() -> None:
    assert baseline("tax.account_mapper", "small") == Decimal("0.05")
    assert baseline("tax.agreement_reader", "medium") == Decimal("0.20")
    assert baseline("tax.memo_drafter", "medium") == Decimal("0.30")
    assert baseline("decisions.recommender", "medium") == Decimal("0.03")


@pytest.mark.parametrize(
    ("route", "parity", "cost", "reason"),
    [
        ("direct", FRESH, "0.04", "not_the_production_route"),
        ("bedrock", date(2028, 1, 2), "0.04", "route_parity_stale"),
        ("bedrock", None, "0.04", "route_parity_stale"),
        ("bedrock", FRESH, "0.06", "cost_regression"),
    ],
)
def test_each_shortfall_is_named(route: str, parity: date | None, cost: str, reason: str) -> None:
    found = real.clearance("tax_account_mapper", route, _ok("tax_account_mapper"),
                           _attempts(cost), last_parity=parity, today=TODAY)  # fmt: skip
    assert found["client_data"] == "none" and reason in found["reasons"]  # type: ignore[operator] -- stand-in


def test_a_threshold_short_by_a_hair_does_not_clear() -> None:
    rates = _ok("tax_agreement_reader") | {"citation_verified": 0.999}
    found = real.clearance("tax_agreement_reader", "bedrock", rates, _attempts("0.1"),
                           last_parity=FRESH, today=TODAY)  # fmt: skip
    assert "below_threshold:citation_verified" in found["reasons"]  # type: ignore[operator] -- stand-in


def test_the_report_is_signed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_EVAL_SIGNING_KEY", "k")
    body = real.report("tax_memo_drafter", "bedrock", _ok("tax_memo_drafter"), _attempts("0.2"),
                       last_parity=FRESH, today=TODAY)  # fmt: skip
    assert real.verified(body) and not real.verified(body | {"route": "direct"})


def test_without_the_accounts_stack_the_run_refuses(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ABACUS_EVAL_STACK", raising=False)
    with pytest.raises(SystemExit):
        real.real_main("tax_memo_drafter", "bedrock", Path("."))
