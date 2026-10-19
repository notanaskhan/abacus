"""Synthetic general ledger detail that reconciles to a synthetic trial balance by construction
(SPEC-034; TASK-069; ADR-085), in QuickBooks Online's CSV and Xero's XLSX layouts.

Balance sheet accounts (numbered 1-3) open at their closing balance, except cash; each income
statement account's closing balance is posted in twelve monthly amounts against cash; cash opens at
whatever makes the openings balance. `volume` adds offsetting pairs (cash and the first other
balance sheet account) that change no balance, for large files. Flaws break exactly one check:
`missing_month`, `drift` (one cent moved between two income statement accounts), `missing_account`,
`extra_account`, `unbalanced`, `outside_period`. Synthetic data only.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, timedelta
from decimal import Decimal

from openpyxl import Workbook

from abacus_tools.synthetic.model import TrialBalance, TrialBalanceLine

ZERO = Decimal(0)
CENT = Decimal("0.01")


@dataclass(frozen=True)
class Posting:
    code: str
    name: str
    on: date
    kind: str
    reference: str
    counterparty: str
    description: str
    debit: Decimal
    credit: Decimal


@dataclass(frozen=True)
class SyntheticGl:
    accounts: tuple[tuple[str, str], ...]  # (code, name) in order
    openings: dict[str, Decimal]  # balance sheet accounts only
    postings: tuple[Posting, ...]


def _closing(line: TrialBalanceLine) -> Decimal:
    return line.debit - line.credit


def _balance_sheet(code: str) -> bool:
    return code[:1] in "123"


def _months(start: date, end: date) -> list[date]:
    """The 15th of each month from `start`'s month to `end`'s."""
    found: list[date] = []
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        found.append(date(year, month, 15))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return found


def build(
    tb: TrialBalance,
    *,
    start: date,
    flaws: Iterable[str] = (),
    volume: int = 0,
    test_entries: bool = False,
) -> SyntheticGl:
    """`test_entries` (SPEC-037; TASK-083): adds manual journals that journal entry testing's
    criteria should select (large, round, near year end, weekend, keywords), each paired with its
    reversal so the ledger still reconciles."""
    flaws = set(flaws)
    lines = list(tb.lines)
    cash = next(
        (
            x
            for x in lines
            if _balance_sheet(x.account_code)
            and ("cash" in x.account_name.lower() or "checking" in x.account_name.lower())
        ),
        next(x for x in lines if _balance_sheet(x.account_code)),
    )
    income = [x for x in lines if not _balance_sheet(x.account_code) and _closing(x) != 0]
    postings: list[Posting] = []
    months = _months(start, tb.as_of)
    count = len(months)
    for n, line in enumerate(income):
        total = _closing(line)
        part = (total / count).quantize(CENT)
        amounts = [part] * (count - 1) + [total - part * (count - 1)]
        for i, (amount, on) in enumerate(zip(amounts, months, strict=True)):
            if amount == 0:
                continue
            ref = f"JE-{n + 1:03d}-{i + 1:02d}"
            if amount > 0:
                postings.append(
                    Posting(
                        line.account_code,
                        line.account_name,
                        on,
                        "Expense",
                        ref,
                        "Supplier",
                        "Monthly cost",
                        amount,
                        ZERO,
                    )
                )
                postings.append(
                    Posting(
                        cash.account_code,
                        cash.account_name,
                        on,
                        "Expense",
                        ref,
                        "Supplier",
                        "Monthly cost",
                        ZERO,
                        amount,
                    )
                )
            else:
                postings.append(
                    Posting(
                        line.account_code,
                        line.account_name,
                        on,
                        "Invoice",
                        ref,
                        "Customer",
                        "Monthly sales",
                        ZERO,
                        -amount,
                    )
                )
                postings.append(
                    Posting(
                        cash.account_code,
                        cash.account_name,
                        on,
                        "Invoice",
                        ref,
                        "Customer",
                        "Monthly sales",
                        -amount,
                        ZERO,
                    )
                )
    other = next((x for x in lines if _balance_sheet(x.account_code) and x is not cash), None)
    if other is not None:
        for k in range(volume // 4):
            on = months[k % count] - timedelta(days=k % 10)
            amount = Decimal(100 + k % 900) + Decimal(k % 100) / 100
            ref = f"TR-{k + 1:07d}"
            postings.append(
                Posting(
                    other.account_code,
                    other.account_name,
                    on,
                    "Transfer",
                    ref,
                    "",
                    "Transfer out",
                    ZERO,
                    amount,
                )
            )
            postings.append(
                Posting(
                    cash.account_code,
                    cash.account_name,
                    on,
                    "Transfer",
                    ref,
                    "",
                    "Transfer out",
                    amount,
                    ZERO,
                )
            )
            postings.append(
                Posting(
                    other.account_code,
                    other.account_name,
                    on,
                    "Transfer",
                    ref + "R",
                    "",
                    "Transfer back",
                    amount,
                    ZERO,
                )
            )
            postings.append(
                Posting(
                    cash.account_code,
                    cash.account_name,
                    on,
                    "Transfer",
                    ref + "R",
                    "",
                    "Transfer back",
                    ZERO,
                    amount,
                )
            )
    activity = sum((p.debit - p.credit for p in postings if p.code == cash.account_code), ZERO)
    openings = {
        x.account_code: (_closing(x) - activity if x is cash else _closing(x))
        for x in lines
        if _balance_sheet(x.account_code)
    }
    accounts = [(x.account_code, x.account_name) for x in lines]
    if "missing_month" in flaws:
        dropped = months[2]
        postings = [p for p in postings if p.on.month != dropped.month]
        # the cash account no longer rolls forward either; the month check fails first
    if "drift" in flaws and len(income) >= 2:  # a balanced cent between two accounts
        a, b = income[0], income[1]
        on, ref = months[6], "JE-D"
        postings.append(
            Posting(a.account_code, a.account_name, on, "Journal", ref, "", "Reclass", CENT, ZERO)
        )
        postings.append(
            Posting(b.account_code, b.account_name, on, "Journal", ref, "", "Reclass", ZERO, CENT)
        )
    if "missing_account" in flaws:
        gone = next(
            x.account_code
            for x in lines
            if _balance_sheet(x.account_code)
            and x is not cash
            and _closing(x) != 0
            and not any(p.code == x.account_code for p in postings)
        )
        accounts = [a for a in accounts if a[0] != gone]
        openings.pop(gone, None)
    if "extra_account" in flaws:
        accounts.append(("9999", "Suspense"))
        postings.append(
            Posting(
                "9999",
                "Suspense",
                months[5],
                "Journal",
                "JE-X",
                "",
                "Unexplained",
                Decimal("250.00"),
                ZERO,
            )
        )
        postings.append(
            Posting(
                cash.account_code,
                cash.account_name,
                months[5],
                "Journal",
                "JE-X",
                "",
                "Unexplained",
                ZERO,
                Decimal("250.00"),
            )
        )
    if "unbalanced" in flaws:
        postings.append(
            Posting(
                income[0].account_code,
                income[0].account_name,
                months[4],
                "Journal",
                "JE-U",
                "",
                "One-sided",
                Decimal("10.00"),
                ZERO,
            )
        )
    if "outside_period" in flaws:
        postings[0] = replace(postings[0], on=tb.as_of + timedelta(days=1))
    if test_entries and other is not None:
        postings.extend(_test_entries(cash, other, tb.as_of))
    return SyntheticGl(tuple(accounts), openings, tuple(postings))


def _by_account(gl: SyntheticGl) -> dict[str, list[Posting]]:
    found: dict[str, list[Posting]] = {code: [] for code, _ in gl.accounts}
    for p in gl.postings:
        found.setdefault(p.code, []).append(p)
    return found


def _money(value: Decimal) -> str:
    return f"{value:,.2f}"


def qbo_general_ledger_csv(
    gl: SyntheticGl, *, company: str = "Example Company", year: int = 2026
) -> bytes:
    """QuickBooks Online's General Ledger: account headings ("1000 Checking"), a "Beginning
    Balance" row for balance sheet accounts, signed amounts, and "Total for ..." rows."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["General Ledger"])
    writer.writerow([company])
    writer.writerow([f"January - December {year}"])
    writer.writerow([])
    writer.writerow(
        [
            "",
            "Date",
            "Transaction Type",
            "Num",
            "Name",
            "Memo/Description",
            "Split",
            "Amount",
            "Balance",
        ]
    )
    names = dict(gl.accounts)
    for code, postings in _by_account(gl).items():
        name = names.get(code, code)
        writer.writerow([f"{code} {name}", "", "", "", "", "", "", "", ""])
        balance = gl.openings.get(code, ZERO)
        if code in gl.openings:
            writer.writerow(["", "", "Beginning Balance", "", "", "", "", "", _money(balance)])
        for p in sorted(postings, key=lambda x: (x.on, x.reference)):
            amount = p.debit - p.credit
            balance += amount
            writer.writerow(
                [
                    "",
                    p.on.strftime("%m/%d/%Y"),
                    p.kind,
                    p.reference,
                    p.counterparty,
                    p.description,
                    "",
                    _money(amount),
                    _money(balance),
                ]
            )
        writer.writerow(
            [
                f"Total for {code} {name}",
                "",
                "",
                "",
                "",
                "",
                "",
                _money(sum((x.debit - x.credit for x in postings), ZERO)),
                "",
            ]
        )
    return out.getvalue().encode("utf-8")


def xero_general_ledger_xlsx(
    gl: SyntheticGl, *, company: str = "Example Company", year: int = 2026
) -> bytes:
    """Xero's General Ledger Detail: account headings ("Checking (1000)"), "Opening Balance",
    postings with Debit and Credit, "Total ..." and "Closing Balance" rows."""
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("General Ledger")
    sheet.append(["General Ledger Detail"])
    sheet.append([company])
    sheet.append([f"For the period 1 January {year} to 31 December {year}"])
    sheet.append([])
    sheet.append(
        ["Date", "Source", "Description", "Reference", "Debit", "Credit", "Running Balance"]
    )
    names = dict(gl.accounts)
    for code, postings in _by_account(gl).items():
        name = names.get(code, code)
        sheet.append([f"{name} ({code})", None, None, None, None, None, None])
        balance = gl.openings.get(code, ZERO)
        if code in gl.openings:
            sheet.append(["Opening Balance", None, None, None, None, None, float(balance)])
        for p in sorted(postings, key=lambda x: (x.on, x.reference)):
            balance += p.debit - p.credit
            sheet.append(
                [
                    p.on.strftime("%d %b %Y"),
                    p.kind,
                    p.description,
                    p.reference,
                    float(p.debit) if p.debit else None,
                    float(p.credit) if p.credit else None,
                    float(balance),
                ]
            )
        debit = sum((x.debit for x in postings), ZERO)
        credit = sum((x.credit for x in postings), ZERO)
        sheet.append(
            [f"Total {name} ({code})", None, None, None, float(debit), float(credit), None]
        )
        sheet.append(["Closing Balance", None, None, None, None, None, float(balance)])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


# --- QuickBooks Desktop, NetSuite, Sage Intacct (SPEC-034 Q1; TASK-071) -----------------------


def qbd_general_ledger_xlsx(
    gl: SyntheticGl, *, company: str = "Example Company", year: int = 2026
) -> bytes:
    """QuickBooks Desktop's General Ledger: account headings ("1000 · Checking"), a "Beginning
    Balance" row with the balance, postings with Debit and Credit, "Total ..." rows."""
    workbook = Workbook(write_only=True)
    sheet = workbook.create_sheet("General Ledger")
    sheet.append([company])
    sheet.append(["General Ledger"])
    sheet.append([f"January through December {year}"])
    sheet.append([])
    sheet.append(
        [None, "Type", "Date", "Num", "Name", "Memo", "Split", "Debit", "Credit", "Balance"]
    )
    names = dict(gl.accounts)
    for code, postings in _by_account(gl).items():
        heading = f"{code} · {names.get(code, code)}"
        sheet.append([heading] + [None] * 9)
        balance = gl.openings.get(code, ZERO)
        if code in gl.openings:
            sheet.append([None, "Beginning Balance"] + [None] * 7 + [float(balance)])
        for p in sorted(postings, key=lambda x: (x.on, x.reference)):
            balance += p.debit - p.credit
            sheet.append(
                [
                    None,
                    p.kind,
                    p.on.strftime("%m/%d/%Y"),
                    p.reference,
                    p.counterparty,
                    p.description,
                    None,
                    float(p.debit) if p.debit else None,
                    float(p.credit) if p.credit else None,
                    float(balance),
                ]
            )
        debit = sum((x.debit for x in postings), ZERO)
        credit = sum((x.credit for x in postings), ZERO)
        sheet.append([f"Total {heading}"] + [None] * 6 + [float(debit), float(credit), None])
    out = io.BytesIO()
    workbook.save(out)
    return out.getvalue()


def _flat_rows(
    gl: SyntheticGl, year: int
) -> list[tuple[str, str, date, str, str, str, str, Decimal, Decimal]]:
    """(code, name, date, type, reference, party, description, debit, credit), openings first."""
    names = dict(gl.accounts)
    rows: list[tuple[str, str, date, str, str, str, str, Decimal, Decimal]] = []
    for code, opening in gl.openings.items():
        if code in names:
            debit, credit = (opening, ZERO) if opening >= 0 else (ZERO, -opening)
            rows.append(
                (
                    code,
                    names[code],
                    date(year, 1, 1),
                    "Opening Balance",
                    "",
                    "",
                    "Beginning balance",
                    debit,
                    credit,
                )
            )
    for p in sorted(gl.postings, key=lambda x: (x.on, x.reference, x.code)):
        rows.append(
            (
                p.code,
                p.name,
                p.on,
                p.kind,
                p.reference,
                p.counterparty,
                p.description,
                p.debit,
                p.credit,
            )
        )
    return rows


def netsuite_general_ledger_csv(
    gl: SyntheticGl, *, company: str = "Example Company", year: int = 2026
) -> bytes:
    """NetSuite's General Ledger, flat: every line names its account ("1000 - Checking");
    opening balances are rows typed "Opening Balance"."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([company])
    writer.writerow(["General Ledger"])
    writer.writerow([f"Jan {year} - Dec {year}"])
    writer.writerow([])
    writer.writerow(
        ["Account", "Date", "Type", "Document Number", "Name", "Memo", "Debit", "Credit"]
    )
    for code, name, on, kind, ref, party, memo, debit, credit in _flat_rows(gl, year):
        writer.writerow(
            [
                f"{code} - {name}",
                on.strftime("%m/%d/%Y"),
                kind,
                ref,
                party,
                "" if kind == "Opening Balance" else memo,
                _money(debit) if debit else "",
                _money(credit) if credit else "",
            ]
        )
    return out.getvalue().encode("utf-8")


def intacct_general_ledger_csv(
    gl: SyntheticGl, *, company: str = "Example Company", year: int = 2026
) -> bytes:
    """Sage Intacct's General ledger, flat: the account code and title in their own columns;
    opening balances are rows described "Beginning balance"."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([company])
    writer.writerow(["General ledger"])
    writer.writerow([f"01/01/{year} to 12/31/{year}"])
    writer.writerow([])
    writer.writerow(
        [
            "Account no.",
            "Account title",
            "Date",
            "Journal",
            "Document",
            "Description",
            "Debit",
            "Credit",
        ]
    )
    for code, name, on, kind, ref, _party, memo, debit, credit in _flat_rows(gl, year):
        journal = (
            ""
            if kind == "Opening Balance"
            else ("GJ" if kind in ("Journal", "Transfer") else kind)
        )
        writer.writerow(
            [
                code,
                name,
                on.strftime("%m/%d/%Y"),
                journal,
                ref,
                memo,
                _money(debit) if debit else "",
                _money(credit) if credit else "",
            ]
        )
    return out.getvalue().encode("utf-8")


def _test_entries(
    cash: TrialBalanceLine, other: TrialBalanceLine, year_end: date
) -> list[Posting]:
    """Pairs of manual journals that net to zero, each tripping criteria (SPEC-037 §4.4)."""
    saturday = year_end - timedelta(days=(year_end.weekday() - 5) % 7 or 7)
    cases = [
        ("TE-LARGE", year_end - timedelta(days=40), Decimal("400000.00"), "Reclass to accrual"),
        ("TE-ROUND", year_end - timedelta(days=90), Decimal("50000.00"), "Monthly accrual"),
        ("TE-YE", year_end - timedelta(days=1), Decimal("43210.09"), "Year-end adjust per CFO"),
        ("TE-WKND", saturday - timedelta(days=21), Decimal("29876.54"), "Correction"),
    ]
    found: list[Posting] = []
    for ref, on, amount, note in cases:
        for suffix, debit_line, credit_line in (("", other, cash), ("-R", cash, other)):
            for line, debit, credit in ((debit_line, amount, ZERO), (credit_line, ZERO, amount)):
                found.append(
                    Posting(
                        line.account_code,
                        line.account_name,
                        on,
                        "Journal Entry",
                        ref + suffix,
                        "",
                        note,
                        debit,
                        credit,
                    )
                )
    return found
