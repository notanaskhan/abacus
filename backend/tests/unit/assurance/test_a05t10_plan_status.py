"""A-05-T10 (TASK-2907; A-05 §3 F1; DEC-1955): the plan-status engine, by code."""

from __future__ import annotations

from datetime import date

import pytest

from abacus.modules.assurance.compute.ebp import plan_status as ps


def test_northwind_is_a_large_filer_due_oct_15_2026_with_a_5558() -> None:
    found = ps.plan_status(
        plan_year_end=date(2025, 12, 31),
        participants_boy_with_balances=286,
        prior_year_filer="large_plan",
        form_5558_filed_on=date(2026, 7, 20),
        holidays=frozenset(),
    )
    assert (found.filer_status, found.form5500_due_on, found.extended) == (
        "large_plan",
        date(2026, 10, 15),
        True,
    )


def test_without_a_5558_the_due_date_is_the_last_day_of_the_seventh_month() -> None:
    due, extended, _ = ps.due_date(
        date(2025, 12, 31), form_5558_filed_on=None, holidays=frozenset()
    )
    assert (due, extended) == (date(2026, 7, 31), False)


def test_a_due_date_on_a_weekend_rolls_to_the_next_business_day() -> None:
    # A Jun 30 plan year ends Jan 31; Jan 31, 2027 is a Sunday.
    due, _, rolled = ps.due_date(date(2026, 6, 30), form_5558_filed_on=None, holidays=frozenset())
    assert (due, rolled) == (date(2027, 2, 1), True)


@pytest.mark.parametrize(
    ("count", "prior", "status", "kept"),
    [
        (99, None, "small_plan", False),
        (100, None, "large_plan", False),
        (120, "small_plan", "small_plan", True),
        (121, "small_plan", "large_plan", False),
        (110, "large_plan", "large_plan", False),
    ],
)
def test_the_100_participant_line_and_the_80_120_rule(
    count: int, prior: ps.Filer | None, status: str, kept: bool
) -> None:
    assert ps.filer_status(count, prior) == (status, kept)


@pytest.mark.parametrize(
    ("value", "problem"),
    [
        ("001", None),
        ("58217", "recordkeeper_id"),
        ("000", "zero"),
        ("1", "format"),
        ("01a", "format"),
    ],
)
def test_plan_numbers(value: str, problem: str | None) -> None:
    assert ps.plan_number_problem(value, recordkeeper_plan_id="58217") == problem
