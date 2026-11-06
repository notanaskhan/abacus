"""A-05-T42 (TASK-3307; DEC-2306): loans and withholding engines, from the row.

"The rollforward foots to 312,400 with 36 loans, offsets total 14,850, and Part IV 4b answers No
because participant loans are excluded." Exact Decimal equality.
"""

from __future__ import annotations

from decimal import Decimal as D

from abacus.modules.assurance.compute.ebp import loans as engine


def test_ac_the_rollforward_foots_to_312_400_with_36_loans() -> None:
    beginning = (
        [engine.Loan(f"A{i:02}", D("6500.00"), D(0), D("1000.00"), D(0), D("5500.00"))
         for i in range(31)]
        + [engine.Loan(f"P{i}", D("4000.00"), D(0), D("4000.00"), D(0), D(0)) for i in range(7)]
        + [engine.Loan("O1", D("4850.00"), D(0), D(0), D("4850.00"), D(0)),
           engine.Loan("O2", D("5200.00"), D(0), D(0), D("5200.00"), D(0)),
           engine.Loan("O3", D("4800.00"), D(0), D(0), D("4800.00"), D(0))]
    )  # fmt: skip
    new = [
        engine.Loan(f"N{i}", D(0), D("19240.00"), D(0), D(0), D("19240.00")) for i in range(5)
    ]
    rolled = engine.rollforward([*beginning, *new])
    assert (rolled.count_beginning, rolled.count_new, rolled.count_paid_off,
            rolled.count_offset, rolled.count_ending) == (41, 5, 7, 3, 36)  # fmt: skip
    assert rolled.offsets == D("14850.00")
    assert rolled.new == D("96200.00")
    assert rolled.foots


def test_ac_offsets_total_14_850() -> None:
    assert engine.offsets_total([D("4850.00"), D("5200.00"), D("4800.00")]) == D("14850.00")


def test_ac_part_iv_4b_answers_no() -> None:
    assert engine.part_iv_4b() == "no"


def test_ac_the_limit_is_the_lesser_of_50000_and_half_vested() -> None:
    assert engine.loan_limit(D("20000.00"), D("30000.00"), 60, False).limit == D("15000.00")
    assert not engine.loan_limit(D("20000.00"), D("30000.00"), 60, False).within
    assert engine.loan_limit(D("50000.00"), D("400000.00"), 60, False).limit == D("50000.00")


def test_ac_five_year_term_except_a_residence_loan() -> None:
    assert not engine.loan_limit(D("1000.00"), D("10000.00"), 120, False).within_term
    assert engine.loan_limit(D("1000.00"), D("10000.00"), 120, True).within_term


def test_ac_withholding_rates_and_the_cash_limit() -> None:
    assert engine.withholding("eligible_rollover", D("10000.00")) == D("2000.00")
    assert engine.withholding("hardship", D("10000.00")) == D("1000.00")
    assert engine.withholding("rmd", D("10000.00")) == D("1000.00")
    assert engine.withholding("direct_rollover", D("10000.00")) == D(0)
    # An offset counts toward the rate, and withholding is limited to the cash.
    assert engine.withholding("loan_offset", D("500.00"), D("4850.00")) == D("500.00")


def test_ac_the_comparative_is_off_by_its_difference() -> None:
    found = engine.py_comparative(D("288500.00"), D("291700.00"))
    assert not found.agrees
    assert found.off_by == D("-3200.00")
    assert engine.py_comparative(D("288500.00"), None).agrees
