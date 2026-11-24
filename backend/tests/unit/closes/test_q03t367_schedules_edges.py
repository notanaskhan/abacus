"""Q-03-T367 (TASK-8959): the close schedules' edges (C-01-T21; CLS-06; ADR-050).

The quarterly mutation sweep left the schedule engine's refusals, its rounding, the first
period's inflow, `through`, `balance_at`'s first period and every tie result's fields unguarded.
Each is held here by its exact value.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal as D

import pytest

from abacus.modules.closes.compute import schedules as sch

PREPAID = sch.Arrangement("prepaid", D("1000"), date(2026, 1, 1), date(2026, 3, 31))


@pytest.mark.parametrize(
    ("arrangement", "message"),
    [
        (replace(PREPAID, finish_on=date(2025, 12, 31)), "finish before start"),
        (
            replace(PREPAID, frequency="quarterly", finish_on=date(2026, 4, 30)),
            "the term is not a whole number of periods",
        ),
        (replace(PREPAID, scheduled_total=D("0")), "the scheduled total is positive"),
    ],
)
def test_each_refusal_names_what_is_wrong(arrangement: sch.Arrangement, message: str) -> None:
    with pytest.raises(sch.ScheduleInvalid) as refused:
        sch.schedule(arrangement)
    assert str(refused.value) == message


def test_a_one_day_term_is_one_period() -> None:
    one = replace(PREPAID, finish_on=date(2026, 1, 1))
    assert sch.periods_of(one) == ("2026-01",)
    assert sch.schedule(one) == (sch.Line("2026-01", D("1000.00"), D("1000.00"), D("0.00")),)


def test_a_prepaid_rounds_down_and_the_last_period_takes_the_remainder() -> None:
    assert sch.schedule(PREPAID) == (
        sch.Line("2026-01", D("1000.00"), D("333.33"), D("666.67")),
        sch.Line("2026-02", D("0.00"), D("333.33"), D("333.34")),
        sch.Line("2026-03", D("0.00"), D("333.34"), D("0.00")),
    )
    # A total that rounds up to the cent at half would differ: 0.02 over three periods.
    tiny = replace(PREPAID, scheduled_total=D("0.05"))
    assert [ln.aje for ln in sch.schedule(tiny)] == [D("0.01"), D("0.01"), D("0.03")]


def test_a_balance_carried_in_reduces_the_first_inflow() -> None:
    midway = replace(PREPAID, starting_balance=D("400"))
    first = sch.schedule(midway)[0]
    assert (first.inflows, first.aje, first.ending_balance) == (
        D("600.00"),
        D("333.33"),
        D("666.67"),  # 400 + 600 - 333.33
    )


def test_an_accrual_builds_and_has_no_inflow() -> None:
    accrual = replace(PREPAID, kind="accrual")
    assert [(ln.inflows, ln.ending_balance) for ln in sch.schedule(accrual)] == [
        (D("0.00"), D("333.33")),
        (D("0.00"), D("666.66")),
        (D("0.00"), D("1000.00")),
    ]
    assert sch.balance_at(accrual, "2026-12") == D("1000.00")  # held once built


def test_through_stops_at_its_period_and_balance_at_reads_the_first_period() -> None:
    assert [ln.period for ln in sch.schedule(PREPAID, through="2026-02")] == ["2026-01", "2026-02"]
    assert [ln.period for ln in sch.schedule(PREPAID, through="2025-11")] == ["2026-01"]
    assert sch.balance_at(PREPAID, "2025-12") == D("0")
    assert sch.balance_at(PREPAID, "2026-01") == D("666.67")  # the first period itself
    assert sch.balance_at(PREPAID, "2026-02") == D("333.34")


def test_quarterly_and_multi_year_periods() -> None:
    quarters = replace(PREPAID, frequency="quarterly", finish_on=date(2026, 12, 31))
    assert sch.periods_of(quarters) == ("2026-03", "2026-06", "2026-09", "2026-12")
    years = replace(
        PREPAID, frequency="annual", start_on=date(2025, 7, 1), finish_on=date(2027, 6, 30)
    )
    assert sch.periods_of(years) == ("2026-06", "2027-06")
    long = replace(PREPAID, start_on=date(2025, 11, 1), finish_on=date(2026, 2, 28))
    assert sch.periods_of(long) == ("2025-11", "2025-12", "2026-01", "2026-02")


def test_every_tie_result_whole() -> None:
    assert sch.tie(D("100"), D("100")) == sch.TieResult(
        "tie", D("100.00"), D("100.00"), None, None
    )
    assert sch.tie(D("100"), D("100"), recorded=True) == sch.TieResult(
        "recorded", D("100.00"), D("100.00"), None, None
    )
    pending = (sch.PendingEntry("AJE-1", D("5")), sch.PendingEntry("AJE-2", D("-20")))
    assert sch.tie(D("120"), D("100"), pending) == sch.TieResult(
        "ties_once_posted", D("120.00"), D("100.00"), D("20.00"), "AJE-2"
    )
    assert sch.tie(D("130"), D("100"), pending) == sch.TieResult(
        "off", D("130.00"), D("100.00"), D("30.00"), None
    )
