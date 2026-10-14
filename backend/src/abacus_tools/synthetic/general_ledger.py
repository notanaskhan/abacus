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
    tb: TrialBalance, *, start: date, flaws: Iterable[str] = (), volume: int = 0
) -> SyntheticGl:
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
