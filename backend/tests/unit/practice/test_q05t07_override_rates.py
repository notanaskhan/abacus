"""Q-05-T07 (TASK-8714; DEC-96; DEC-5710): overrides are changes and rejections; the firm-wide
rate 206 of 3,410 is 6.0% and Denver's 61 of 1,128 is 5.4% (exact Decimal, half up); an agent is
rated from 25 outputs and above tolerance only when its rate exceeds it; EBP Audit Workpapers'
37 overrides are 21 + 9 + 7 by reason."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.practice.compute.override_rates import (
    OutcomeRow,
    per_agent,
    rate,
    reasons,
    totals,
)


def _rows(agent: str, adopted: int, changed: int, rejected: int = 0) -> list[OutcomeRow]:
    return (
        [OutcomeRow(agent, "adopted")] * adopted
        + [OutcomeRow(agent, "changed", "amount")] * changed
        + [OutcomeRow(agent, "rejected", "wrong_period")] * rejected
    )


def test_ac_firm_and_office_rates_read_6_0_and_5_4() -> None:
    assert rate(206, 3410) == Decimal("6.0")
    assert rate(61, 1128) == Decimal("5.4")
    assert totals(_rows("a", 3204, 150, 56)) == (3410, 206, Decimal("6.0"))


def test_ac_rated_from_25_and_above_tolerance_by_exact_comparison() -> None:
    rows = _rows("few", 20, 4) + _rows("many", 92, 8)
    by = {r.agent_key: r for r in per_agent(rows, Decimal(8))}
    assert not by["few"].rated and not by["few"].above_tolerance
    assert by["many"].rate == Decimal("8.0") and not by["many"].above_tolerance
    over = {r.agent_key: r for r in per_agent(_rows("x", 91, 9), Decimal(8))}
    assert over["x"].above_tolerance


def test_ac_reasons_count_most_frequent_first() -> None:
    rows = (
        [OutcomeRow("ebp", "changed", "classification")] * 21
        + [OutcomeRow("ebp", "changed", "amount")] * 9
        + [OutcomeRow("ebp", "rejected", "wrong_period")] * 7
        + [OutcomeRow("ebp", "adopted")] * 100
    )
    assert reasons(rows, "ebp") == [("classification", 21), ("amount", 9), ("wrong_period", 7)]
    assert sum(n for _, n in reasons(rows, "ebp")) == 37
