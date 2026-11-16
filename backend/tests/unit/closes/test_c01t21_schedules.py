"""C-01-T21: schedules and their tie (C-01 §3 F6; CLS-04; ADR-050)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal as D

import pytest

from abacus.modules.closes.compute import schedules as calc
from abacus_tools.synthetic.scenarios.brightwater_hale import close_slice as bh

POLICY = calc.Arrangement("prepaid", bh.PREPAID_ANNUAL, date(2026, 1, 1), date(2026, 12, 31))


def test_prepaid_8400_over_12_is_700_a_month_and_2800_at_august() -> None:
    lines = calc.schedule(POLICY)
    assert len(lines) == bh.PREPAID_MONTHS
    assert {line.aje for line in lines} == {D("700.00")}
    assert lines[0].inflows == D("8400.00")
    assert calc.balance_at(POLICY, "2026-08") == bh.PREPAID_SCHEDULE
    assert lines[-1].ending_balance == D("0.00")
    assert sum(line.aje for line in lines) == bh.PREPAID_ANNUAL


def test_rounding_lands_in_the_last_period_and_foots() -> None:
    odd = calc.Arrangement("prepaid", D("1000.00"), date(2026, 1, 1), date(2026, 3, 31))
    lines = calc.schedule(odd)
    assert [line.aje for line in lines] == [D("333.33"), D("333.33"), D("333.34")]
    assert lines[-1].ending_balance == D("0.00")


def test_an_accrual_builds_up_and_quarterly_steps() -> None:
    accrual = calc.Arrangement(
        "accrual", D("1200.00"), date(2026, 1, 1), date(2026, 12, 31), frequency="quarterly"
    )
    lines = calc.schedule(accrual)
    assert [line.period for line in lines] == ["2026-03", "2026-06", "2026-09", "2026-12"]
    assert [line.ending_balance for line in lines] == [
        D("300.00"), D("600.00"), D("900.00"), D("1200.00")
    ]  # fmt: skip


def test_ties_once_posted_while_aje_02_is_pending_then_recorded() -> None:
    pending = [calc.PendingEntry("AJE-02", D("-700.00"))]
    before = calc.tie(bh.PREPAID_GL, bh.PREPAID_SCHEDULE, pending)
    assert before.tie == "ties_once_posted"
    assert before.pending_entry_number == "AJE-02"
    assert before.off_by == D("700.00")
    after = calc.tie(bh.PREPAID_SCHEDULE, bh.PREPAID_SCHEDULE, recorded=True)
    assert after.tie == "recorded" and after.off_by is None
    off = calc.tie(bh.PREPAID_GL, bh.PREPAID_SCHEDULE, [calc.PendingEntry("AJE-09", D("-5.00"))])
    assert off.tie == "off" and off.off_by == D("700.00")


def test_rollups_foot_in_code() -> None:
    sums = calc.rollup(
        [
            ("asset", "Bank", D("184610.50")),
            ("asset", "Other Current Asset", D("3500.00")),
            ("liability", "Credit Card", D("1200.00")),
        ]
    )
    assert sums["asset"][""] == D("188110.50")
    assert sums["asset"]["Bank"] == D("184610.50")


def test_a_term_that_is_not_whole_periods_is_refused() -> None:
    with pytest.raises(calc.ScheduleInvalid):
        calc.periods_of(
            calc.Arrangement("prepaid", D("10"), date(2026, 1, 1), date(2026, 2, 28), "quarterly")
        )


def test_the_inputs_hash_is_stable() -> None:
    assert calc.inputs_hash(POLICY, "2026-08", D("3500")) == calc.inputs_hash(
        POLICY, "2026-08", D("3500.00")
    )
