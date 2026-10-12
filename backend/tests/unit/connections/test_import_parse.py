"""SPEC-028 AC-5, AC-6 (TASK-052): parsing QuickBooks Online and Xero trial balance exports into
the common ledger model, and refusing what doesn't fit, with a short code."""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook

from abacus.modules.connections.connector import Period
from abacus.modules.connections.import_formats import FORMATS
from abacus.modules.connections.import_parse import ParsedImport, parse_export, parse_isolated
from abacus.modules.connections.ledger_import import check_export
from abacus.modules.ledger.api import NormaliseError, validate
from abacus_tools.synthetic.ledger_exports import qbo_trial_balance_csv, xero_trial_balance_xlsx
from abacus_tools.synthetic.model import TrialBalance, TrialBalanceLine

START, END = date(2026, 1, 1), date(2026, 12, 31)
TB = TrialBalance(
    END,
    (
        TrialBalanceLine("1000", "Checking", Decimal("12345.67"), Decimal(0)),
        TrialBalanceLine("1200", "Accounts Receivable (A/R)", Decimal("5000.00"), Decimal(0)),
        TrialBalanceLine("2000", "Accounts Payable", Decimal(0), Decimal("3345.67")),
        TrialBalanceLine("4000", "Sales", Decimal(0), Decimal("14000.00")),
    ),
)


def _lines(parsed: ParsedImport) -> list[tuple[str, str, Decimal, Decimal]]:
    tb = parsed.trial_balance
    return [(x.account_code, x.account_name, x.debit, x.credit) for x in tb.lines]


def test_ac5_quickbooks_online_csv() -> None:
    parsed = parse_export(qbo_trial_balance_csv(TB), "qbo_tb_csv", START, END)
    assert _lines(parsed) == [
        ("1000", "Checking", Decimal("12345.67"), Decimal(0)),
        ("1200", "Accounts Receivable (A/R)", Decimal("5000.00"), Decimal(0)),
        ("2000", "Accounts Payable", Decimal(0), Decimal("3345.67")),
        ("4000", "Sales", Decimal(0), Decimal("14000.00")),
    ]
    tb = parsed.trial_balance
    assert (tb.declared_debit, tb.declared_credit) == (Decimal("17345.67"), Decimal("17345.67"))
    assert not parsed.totals_from_lines and tb.currency == "USD"
    assert (tb.period_start, tb.period_end) == (START, END)
    assert validate(tb, period_start=START, period_end=END) is None


def test_ac5_xero_xlsx_with_parentheses_and_trailing_codes() -> None:
    parsed = parse_export(xero_trial_balance_xlsx(TB), "xero_tb_xlsx", START, END)
    assert _lines(parsed)[0] == ("1000", "Checking", Decimal("12345.67"), Decimal(0))
    assert _lines(parsed)[2] == ("2000", "Accounts Payable", Decimal(0), Decimal("3345.67"))
    assert validate(parsed.trial_balance, period_start=START, period_end=END) is None


def test_ac5_a_credit_written_as_a_negative_debit_lands_on_the_credit_side() -> None:
    parsed = parse_export(
        qbo_trial_balance_csv(TB, negative_debits=True), "qbo_tb_csv", START, END
    )
    assert _lines(parsed)[3] == ("4000", "Sales", Decimal(0), Decimal("14000.00"))


def test_q2_without_a_total_row_the_totals_come_from_the_lines() -> None:
    parsed = parse_export(qbo_trial_balance_csv(TB, total_row=False), "qbo_tb_csv", START, END)
    assert parsed.totals_from_lines
    assert parsed.trial_balance.declared_debit == Decimal("17345.67")


def test_ac6_a_different_period_is_caught_by_validation() -> None:
    parsed = parse_export(
        qbo_trial_balance_csv(TB, as_of=date(2026, 11, 30)), "qbo_tb_csv", START, END
    )
    assert parsed.trial_balance.period_end == date(2026, 11, 30)
    assert validate(parsed.trial_balance, period_start=START, period_end=END) == "period_mismatch"


def test_ac6_an_unbalanced_export_is_caught() -> None:
    lopsided = TrialBalance(
        END, (*TB.lines[:3], TrialBalanceLine("4000", "Sales", Decimal(0), Decimal("12750.00")))
    )
    parsed = parse_export(qbo_trial_balance_csv(lopsided), "qbo_tb_csv", START, END)
    assert validate(parsed.trial_balance, period_start=START, period_end=END) == "unbalanced"


@pytest.mark.parametrize(
    ("content", "chosen", "code"),
    [
        (xero_trial_balance_xlsx(TB), "qbo_tb_csv", "looks_like_xero"),
        (qbo_trial_balance_csv(TB), "xero_tb_xlsx", "looks_like_qbo"),
        (b"just some text\nnot a trial balance\n", "qbo_tb_csv", "unrecognised_format"),
        (b"PK\x03\x04not really a zip", "xero_tb_xlsx", "unreadable"),
    ],
)
def test_ac6_the_wrong_or_an_unreadable_file_is_refused_with_a_code(
    content: bytes, chosen: str, code: str
) -> None:
    with pytest.raises(NormaliseError) as raised:
        parse_export(content, chosen, START, END)
    assert raised.value.code == code


def test_ac6_windows_1252_csv_is_read() -> None:
    accented = TrialBalance(
        END,
        (
            TrialBalanceLine("1000", "Café float", Decimal("10.00"), Decimal(0)),
            TrialBalanceLine("3000", "Equity", Decimal(0), Decimal("10.00")),
        ),
    )
    content = qbo_trial_balance_csv(accented).decode("utf-8").encode("cp1252")
    assert _lines(parse_export(content, "qbo_tb_csv", START, END))[0][1] == "Café float"


def test_adr110_formulas_are_never_evaluated() -> None:

    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    sheet.append(["As at 31 December 2026"])
    sheet.append(["Account", "Debit", "Credit", "YTD Debit", "YTD Credit"])
    sheet.append(["Cash (1000)", "", "", "=1+1", ""])
    out = io.BytesIO()
    workbook.save(out)
    # No cached value was ever computed for the formula: it reads as empty, never as 2.
    parsed = parse_export(out.getvalue(), "xero_tb_xlsx", START, END)
    assert parsed.trial_balance.lines == ()


def test_d2_the_isolated_parse_returns_the_same_result() -> None:
    content = qbo_trial_balance_csv(TB)
    assert parse_isolated(content, "qbo_tb_csv", START, END) == parse_export(
        content, "qbo_tb_csv", START, END
    )


def test_ac6_an_unbalanced_export_reports_the_difference_computed_by_code() -> None:
    """TASK-053 D1: "Debits and credits differ by …" shows a value code computed."""
    lopsided = TrialBalance(
        END, (*TB.lines[:3], TrialBalanceLine("4000", "Sales", Decimal(0), Decimal("12750.00")))
    )
    fmt = FORMATS["qbo_tb_csv"]
    checked = check_export(fmt, qbo_trial_balance_csv(lopsided), Period(START, END))
    debits = sum((line.debit for line in lopsided.lines[:3]), Decimal(0))
    credits = sum((line.credit for line in lopsided.lines), Decimal(0))
    assert checked.failure == "unbalanced"
    assert checked.difference == debits - credits
    assert checked.found_period_end is None


def test_ac6_a_different_period_reports_the_period_the_export_covers() -> None:
    """TASK-053 D1: "This export covers … we need …" shows the period end found."""
    content = qbo_trial_balance_csv(TB, as_of=date(2026, 11, 30))
    checked = check_export(FORMATS["qbo_tb_csv"], content, Period(START, END))
    assert checked.failure == "period_mismatch"
    assert checked.found_period_end == date(2026, 11, 30)
    assert checked.difference is None


def test_ac6_a_good_export_reports_no_failure_values() -> None:
    checked = check_export(FORMATS["qbo_tb_csv"], qbo_trial_balance_csv(TB), Period(START, END))
    assert (checked.failure, checked.difference, checked.found_period_end) == (None, None, None)
