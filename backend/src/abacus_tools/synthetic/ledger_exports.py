"""Synthetic ledger exports in each system's layout (SPEC-028; TASK-052 D4): QuickBooks Online's
trial balance CSV and Xero's trial balance XLSX, from a synthetic trial balance. Options add the
quirks real exports have: parenthesised negatives, a credit entered as a negative debit, section
headings and sub-totals, and no total row. Synthetic data only."""

from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal

from openpyxl import Workbook

from abacus_tools.synthetic.model import TrialBalance


def _money(value: Decimal, *, parentheses: bool = False) -> str:
    if value == 0:
        return ""
    if value < 0:
        return f"({-value:,.2f})" if parentheses else f"-{-value:,.2f}"
    return f"{value:,.2f}"


def qbo_trial_balance_csv(
    tb: TrialBalance,
    *,
    company: str = "Example Company",
    as_of: date | None = None,
    total_row: bool = True,
    negative_debits: bool = False,
    headings: bool = True,
) -> bytes:
    """QuickBooks Online: title lines, a header row with a blank account column, accounts as
    "<number> <name>", a TOTAL row. `negative_debits` writes credits as negative debits."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    end = as_of or tb.as_of
    writer.writerow(["Trial Balance"])
    writer.writerow([company])
    writer.writerow([f"As of {end:%B} {end.day}, {end.year}"])
    writer.writerow([])
    writer.writerow(["", "Debit", "Credit"])
    if headings:
        writer.writerow(["Accounts", "", ""])
    for line in tb.lines:
        name = f"{line.account_code} {line.account_name}"
        if negative_debits and line.credit:
            writer.writerow([name, _money(-line.credit), ""])
        else:
            writer.writerow([name, _money(line.debit), _money(line.credit)])
    if total_row:
        debit = sum((x.debit for x in tb.lines), Decimal(0))
        credit = sum((x.credit for x in tb.lines), Decimal(0))
        writer.writerow(["TOTAL", f"${debit:,.2f}", f"${credit:,.2f}"])
    return out.getvalue().encode("utf-8")


def xero_trial_balance_xlsx(
    tb: TrialBalance,
    *,
    company: str = "Example Company",
    as_of: date | None = None,
    total_row: bool = True,
    parentheses: bool = True,
) -> bytes:
    """Xero: title lines, a header row ("Account", "Debit", "Credit", "YTD Debit", "YTD
    Credit"), accounts as "<name> (<code>)", section headings, a Total row. Year-to-date columns
    carry the balances; amounts are text, negatives in parentheses when asked."""
    workbook = Workbook()
    sheet = workbook.active
    if sheet is None:
        raise RuntimeError("openpyxl made a workbook without a sheet")
    end = as_of or tb.as_of
    sheet.append(["Trial Balance"])
    sheet.append([company])
    sheet.append([f"As at {end.day} {end:%B} {end.year}"])
    sheet.append([])
    sheet.append(["Account", "Debit", "Credit", "YTD Debit", "YTD Credit"])
    sheet.append(["Revenue", None, None, None, None])
    for line in tb.lines:
        net = line.debit - line.credit
        debit = _money(net, parentheses=parentheses) if net > 0 else ""
        credit = _money(-net, parentheses=parentheses) if net < 0 else ""
        sheet.append([f"{line.account_name} ({line.account_code})", "", "", debit, credit])
    if total_row:
        debit = sum((x.debit for x in tb.lines), Decimal(0))
        credit = sum((x.credit for x in tb.lines), Decimal(0))
        sheet.append(["Total", "", "", f"{debit:,.2f}", f"{credit:,.2f}"])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()
