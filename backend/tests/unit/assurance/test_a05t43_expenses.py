"""A-05-T43 (TASK-3308; DEC-2307): the expenses engine, from the row.

"Expenses foot to 38,400 = 6,000 + 32,400, the budget account rolls to 750, and 2025 limits apply,
never prior-year limits."
"""

from __future__ import annotations

from decimal import Decimal as D

import pytest

from abacus.modules.assurance.compute.ebp import expenses as engine


def _expenses(disclosed: bool = True) -> list[engine.Expense]:
    return [
        engine.Expense("recordkeeping", D("24600.00"), D(0), D("24600.00"), "2i(2)", True),
        engine.Expense("tpa", D("7800.00"), D(0), D("7800.00"), "2i(2)", True),
        engine.Expense("audit_fee", D("9100.00"), D("3100.00"), D("6000.00"), "2i(1)", disclosed),
    ]


def test_ac_expenses_foot_to_38_400() -> None:
    tied = engine.tie(_expenses())
    assert tied.paid == D("38400.00")
    assert tied.by_line == {"2i(2)": D("32400.00"), "2i(1)": D("6000.00")}
    assert (tied.invoiced, tied.credits) == (D("41500.00"), D("3100.00"))
    assert tied.invoices_tie
    assert tied.exceptions == ()


def test_ac_the_budget_account_rolls_to_750() -> None:
    roll = engine.budget_account(
        [("beginning", D("1200.00")), ("revenue_share", D("2650.00")), ("applied", D("3100.00"))]
    )
    assert roll.ending == D("750.00")


def test_ac_2025_limits_apply() -> None:
    limits = engine.limits_for(2025)
    assert limits["402g"] == D("23500.00")
    assert limits["catch_up"] == D("7500.00")
    assert limits["catch_up_60_63"] == D("11250.00")
    assert limits["415c"] == D("70000.00")
    assert limits["401a17"] == D("350000.00")


def test_ac_a_prior_year_is_never_substituted() -> None:
    assert engine.limits_for(2024)["402g"] != engine.limits_for(2025)["402g"]
    with pytest.raises(engine.LimitsUnavailable):
        engine.limits_for(2031)


def test_ac_an_expense_with_no_disclosure_is_an_exception() -> None:
    assert engine.tie(_expenses(disclosed=False)).exceptions == ("audit_fee",)


def test_ac_an_amount_is_within_a_limit_up_to_and_including_it() -> None:
    limit = engine.limits_for(2025)["402g"]
    assert engine.within_limit(limit, "402g", 2025)
    assert not engine.within_limit(limit + D("0.01"), "402g", 2025)
