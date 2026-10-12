"""SPEC-029 AC-5 to AC-9 (TASK-055): document kinds by rule; each mechanical check's pass,
problem and not-applicable cases computed by code; ledger cross-checks for the firm only."""

from __future__ import annotations

import io
import json
from dataclasses import asdict
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from openpyxl import Workbook

from abacus.modules.evidence.checks import (
    CheckResult,
    ExtractedFields,
    aging_checks,
    duplicate,
    normalised_name,
    readable,
    schedule_checks,
    statement_checks,
)
from abacus.modules.evidence.cross_checks import Account, aging_cross_check, bank_cross_check
from abacus.modules.evidence.extraction import XLSX, extract
from abacus.modules.requests.classification import document_kind
from abacus_tools.synthetic.documents import aging_schedule_xlsx

YEAR_END = date(2026, 12, 31)
D = Decimal


def _statement(**changes: object) -> ExtractedFields:
    values: dict[str, object] = {
        "status": "extracted",
        "reason": None,
        "period_start": date(2026, 12, 1),
        "period_end": YEAR_END,
        "as_of": None,
        "entity_name": "Example Company Inc",
        "opening": D("10000.00"),
        "closing": D("12124.50"),
        "credits": D("5250.00"),
        "debits": D("3125.50"),
    }
    values.update(changes)
    return ExtractedFields(**values)  # pyright: ignore[reportArgumentType] -- test values


def _by_code(results: list[CheckResult]) -> dict[str, CheckResult]:
    return {r.code: r for r in results}


def _aging(content: bytes) -> ExtractedFields:
    found = extract(content, XLSX)
    document = json.loads(json.dumps(asdict(found), default=str))
    assert found.aging is not None
    return ExtractedFields(
        "extracted", None, None, None, found.aging.as_of, None, None, None, None, None, document
    )


ROWS = [
    ("Acme Supply", [D("1200.00"), D("300.00"), D(0), D(0), D("75.00")]),
    ("Beta Tools", [D("50.00"), D(0), D("20.00"), D(0), D(0)]),
]


# --- AC-5: document kinds ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("description", "kind"),
    [
        ("Bank statement for December", "bank_statement"),
        ("Bank statements, all accounts", "bank_statement"),
        ("AR aging at year end", "ar_aging"),
        ("Aged payables listing", "ap_aging"),
        ("Fixed asset roll-forward", "schedule"),
        ("Accrued expenses schedule", "schedule"),
        ("Board minutes", None),
        ("Trial balance as of year end", None),
    ],
)
def test_ac5_document_kinds_come_from_fixed_keywords(description: str, kind: str | None) -> None:
    assert document_kind(description, "Area") == kind


# --- AC-6: bank statements ----------------------------------------------------------------------


def test_ac6_a_statement_for_the_year_end_passes_every_check() -> None:
    results = _by_code(statement_checks(_statement(), YEAR_END, "Example Company, Inc."))
    assert {c: r.outcome for c, r in results.items()} == {
        "stale_as_of": "passed",
        "wrong_period": "passed",
        "wrong_entity": "passed",
        "totals_dont_add_up": "passed",
    }


def test_ac6_a_statement_a_month_early_is_the_wrong_period_not_stale() -> None:
    fields = _statement(period_start=date(2026, 11, 1), period_end=date(2026, 11, 30))
    results = _by_code(statement_checks(fields, YEAR_END, "Example Company Inc"))
    assert results["stale_as_of"].outcome == "passed"
    wrong = results["wrong_period"]
    assert (wrong.outcome, wrong.expected_date, wrong.found_date) == (
        "problem",
        YEAR_END,
        date(2026, 11, 30),
    )


def test_ac6_a_statement_ending_more_than_45_days_before_is_stale() -> None:
    fields = _statement(period_start=date(2026, 10, 1), period_end=date(2026, 10, 31))
    results = _by_code(statement_checks(fields, YEAR_END, "Example Company Inc"))
    assert results["stale_as_of"].outcome == "problem"
    assert (results["wrong_period"].outcome, results["wrong_period"].reason) == (
        "not_applicable",
        "stale",
    )


def test_ac6_with_only_an_end_date_the_31_days_before_it_count() -> None:
    fields = _statement(period_start=None, period_end=date(2027, 1, 15))
    results = _by_code(statement_checks(fields, YEAR_END, "Example Company Inc"))
    assert results["wrong_period"].outcome == "passed"


def test_ac6_another_company_is_the_wrong_entity() -> None:
    results = _by_code(statement_checks(_statement(), YEAR_END, "Sister Company LLC"))
    assert results["wrong_entity"].outcome == "problem"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Example Co., Inc.", "example"),
        ("THE EXAMPLE COMPANY", "example"),
        ("Smith & Jones LLP", "smith jones"),
    ],
)
def test_ac6_names_are_compared_without_case_punctuation_or_legal_suffixes(
    name: str, expected: str
) -> None:
    assert normalised_name(name) == expected


def test_ac6_a_closing_balance_that_does_not_add_up_reports_the_difference() -> None:
    results = _by_code(statement_checks(_statement(closing=D("12000.00")), YEAR_END, "Example"))
    found = results["totals_dont_add_up"]
    assert (found.outcome, found.difference) == ("problem", D("-124.50"))


def test_ac6_totals_are_not_applicable_when_not_all_printed() -> None:
    results = _by_code(statement_checks(_statement(credits=None), YEAR_END, "Example"))
    assert results["totals_dont_add_up"].outcome == "not_applicable"


# --- AC-7: agings and schedules ----------------------------------------------------------------


def test_ac7_an_aging_for_the_year_end_that_adds_up_passes() -> None:
    results = _by_code(aging_checks(_aging(aging_schedule_xlsx(ROWS)), YEAR_END))
    assert results["wrong_period"].outcome == "passed"
    assert results["totals_dont_add_up"].outcome == "passed"


def test_ac7_an_aging_whose_total_row_is_off_is_a_problem() -> None:
    content = aging_schedule_xlsx(ROWS, total_off_by=D("10.00"))
    found = _by_code(aging_checks(_aging(content), YEAR_END))["totals_dont_add_up"]
    assert (found.outcome, found.difference) == ("problem", D("10.00"))


def test_ac7_an_aging_as_of_another_date_is_the_wrong_period() -> None:
    content = aging_schedule_xlsx(ROWS, as_of=date(2026, 11, 30))
    assert _by_code(aging_checks(_aging(content), YEAR_END))["wrong_period"].outcome == "problem"


def test_ac7_formulas_without_saved_results_are_not_applicable_never_zero() -> None:
    content = aging_schedule_xlsx(ROWS, formulas=True)
    found = _by_code(aging_checks(_aging(content), YEAR_END))["totals_dont_add_up"]
    assert (found.outcome, found.reason) == ("not_applicable", "no_values")


def _schedule(rows: list[list[object]]) -> ExtractedFields:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)
    out = io.BytesIO()
    workbook.save(out)
    document = json.loads(json.dumps(asdict(extract(out.getvalue(), XLSX)), default=str))
    return ExtractedFields(
        "extracted", None, None, None, None, None, None, None, None, None, document
    )


def test_ac7_a_schedule_total_row_is_checked_against_the_rows_above() -> None:
    good = _schedule([["Item", "Amount"], ["Rent", 100], ["Utilities", 50.25], ["Total", 150.25]])
    bad = _schedule([["Item", "Amount"], ["Rent", 100], ["Utilities", 50.25], ["Total", 160]])
    assert schedule_checks(good)[0].outcome == "passed"
    assert (schedule_checks(bad)[0].outcome, schedule_checks(bad)[0].difference) == (
        "problem",
        D("9.75"),
    )


def test_ac7_a_schedule_without_a_total_row_is_not_applicable() -> None:
    found = schedule_checks(_schedule([["Item", "Amount"], ["Rent", 100]]))[0]
    assert (found.outcome, found.reason) == ("not_applicable", "no_total_row")


# --- AC-8: duplicates and unreadable ------------------------------------------------------------


def test_ac8_the_same_file_elsewhere_names_that_item() -> None:
    other = uuid4()
    assert duplicate(other, True).ref_item_id == other
    assert duplicate(None, False).outcome == "passed"


def test_ac8_an_unreadable_file_is_a_client_problem_with_its_reason() -> None:
    found = readable(_statement(status="unreadable", reason="scanned"))
    assert (found.outcome, found.audience, found.reason) == ("problem", "client", "scanned")


# --- AC-9: ledger cross-checks, firm only -------------------------------------------------------


CASH = [
    Account("1000", "Checking 4471", D("12000.00"), "Cash and equivalents"),
    Account("1010", "Savings 9012", D("5000.00"), "Cash and equivalents"),
    Account("1200", "Accounts receivable", D("1700.00"), "Receivables"),
    Account("1210", "Allowance for doubtful accounts", D("-55.00"), "Receivables"),
    Account("2000", "Accounts payable", D("-800.00"), "Payables"),
]


def test_ac9_the_statement_matches_its_cash_account_by_last_four_digits() -> None:
    found = bank_cross_check(D("12124.50"), "4471", CASH, has_methodology=True)
    assert (found.outcome, found.audience, found.account_code, found.difference) == (
        "problem",
        "firm",
        "1000",
        D("124.50"),
    )


def test_ac9_with_two_cash_accounts_and_no_match_it_does_not_guess() -> None:
    found = bank_cross_check(D("1.00"), "0000", CASH, has_methodology=True)
    assert (found.outcome, found.reason) == ("not_applicable", "account_unclear")


def test_ac9_the_only_cash_account_is_used_without_a_methodology() -> None:
    accounts = [Account("1000", "Operating cash", D("50.00")), CASH[2]]
    found = bank_cross_check(D("50.00"), None, accounts, has_methodology=False)
    assert (found.outcome, found.account_code) == ("passed", "1000")


def test_ac9_accounts_named_for_a_bank_but_not_cash_are_not_cash_accounts() -> None:
    accounts = [
        Account("1000", "Operating cash", D("50.00")),
        Account("7100", "Bank fees", D("12.00")),
        Account("2500", "Bank loan", D("-900.00")),
    ]
    found = bank_cross_check(D("50.00"), None, accounts, has_methodology=False)
    assert (found.outcome, found.account_code) == ("passed", "1000")


def test_ac9_no_trial_balance_for_the_year_end_is_not_applicable() -> None:
    assert bank_cross_check(D("1.00"), "4471", None, True).reason == "no_trial_balance"


def test_ac9_ar_aging_against_receivables_excluding_the_allowance() -> None:
    found = aging_cross_check(D("1645.00"), payables=False, accounts=CASH)
    assert (found.outcome, found.account_code, found.difference) == (
        "problem",
        "1200",
        D("-55.00"),
    )


def test_ac9_ap_aging_against_payables_as_a_credit_balance() -> None:
    found = aging_cross_check(D("800.00"), payables=True, accounts=CASH)
    assert (found.outcome, found.account_code, found.amount) == ("passed", "2000", D("800.00"))
