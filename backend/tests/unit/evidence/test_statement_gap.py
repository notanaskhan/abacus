"""SPEC-031 AC-5 (TASK-060): which cash accounts still need a statement, by code."""

from __future__ import annotations

from decimal import Decimal

from abacus.modules.evidence.client_view import Gap, statement_gap
from abacus.modules.evidence.cross_checks import Account


def _cash(*names: str) -> list[Account]:
    return [Account(f"10{i}", n, Decimal(100)) for i, n in enumerate(names)]


def test_ac5_all_accounts_covered() -> None:
    gap = statement_gap(_cash("Checking 2290", "Savings x8812"), ["8812", "2290"])
    assert gap == Gap(["2290", "8812"], [])


def test_ac5_one_account_still_needed() -> None:
    gap = statement_gap(_cash("Cash 2290", "Cash 8812", "Cash 4471"), ["2290", "8812"])
    assert gap == Gap(["2290", "8812"], ["4471"])


def test_ac5_an_account_without_digits_is_named_and_takes_an_unmatched_statement() -> None:
    cash = _cash("Operating 2290", "Payroll account")
    assert statement_gap(cash, ["2290"]) == Gap(["2290"], ["Payroll account"])
    assert statement_gap(cash, ["2290", None]) == Gap(["2290", "Payroll account"], [])


def test_ac5_no_cash_accounts_means_no_gap_line() -> None:
    assert statement_gap([], ["2290"]) is None
