"""Derived artefacts: trial balances, bank statements, agings (SPEC-001 AC-4, AC-6, AC-7)."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import date, timedelta
from decimal import Decimal

from abacus_tools.synthetic.ledger import ACCOUNTS, AP, AR, BankEvent, Books, OpenItem
from abacus_tools.synthetic.model import (
    ZERO,
    Aging,
    AgingLine,
    BankAccount,
    BankLine,
    BankStatement,
    JournalEntry,
    ReconcilingItem,
    TrialBalance,
    TrialBalanceLine,
)


def balances_at(entries: Iterable[JournalEntry], as_of: date) -> dict[str, Decimal]:
    """Net debit balance per account from every entry dated on or before `as_of`."""
    out = {a.code: ZERO for a in ACCOUNTS}
    for entry in entries:
        if entry.date <= as_of:
            for line in entry.lines:
                out[line.account_code] += line.debit - line.credit
    return out


def trial_balances(
    entries: tuple[JournalEntry, ...], ends: tuple[date, ...], entity: str
) -> tuple[TrialBalance, ...]:
    running = {a.code: ZERO for a in ACCOUNTS}
    out: list[TrialBalance] = []
    index = 0
    for end in ends:
        while index < len(entries) and entries[index].date <= end:
            for line in entries[index].lines:
                running[line.account_code] += line.debit - line.credit
            index += 1
        out.append(trial_balance_from(running, end, entity))
    return tuple(out)


def trial_balance_from(balances: dict[str, Decimal], as_of: date, entity: str) -> TrialBalance:
    lines: list[TrialBalanceLine] = []
    for a in ACCOUNTS:
        net = balances[a.code]
        debit, credit = (net, ZERO) if net > 0 else (ZERO, -net if net < 0 else ZERO)
        lines.append(TrialBalanceLine(a.code, a.name, debit, credit))
    return TrialBalance(as_of, tuple(lines), entity)


def bank_statements(books: Books) -> tuple[BankStatement, ...]:
    out: list[BankStatement] = []
    for account in books.bank_accounts:
        events = sorted(
            (e for e in books.bank_events if e.gl_account == account.gl_account_code),
            key=lambda e: (e.cleared, e.posted, e.description, e.amount),
        )
        balance = books.opening_cash[account.gl_account_code]
        for end in books.month_ends:
            first = date(end.year, end.month, 1)
            out.append(_statement(account, events, first, end, balance))
            balance = out[-1].closing_balance
    return tuple(out)


def _statement(
    account: BankAccount, events: list[BankEvent], first: date, end: date, opening: Decimal
) -> BankStatement:
    lines: list[BankLine] = []
    balance = opening
    for event in events:
        if first <= event.cleared <= end:
            balance += event.amount
            lines.append(BankLine(event.cleared, event.description, event.amount, balance))
    items: list[ReconcilingItem] = []
    for event in events:
        if event.posted <= end < event.cleared:
            if event.amount > 0:
                items.append(
                    ReconcilingItem(
                        "deposit_in_transit",
                        f"{event.description} {event.posted.isoformat()}",
                        event.amount,
                    )
                )
            else:
                items.append(
                    ReconcilingItem("outstanding_cheque", event.description, -event.amount)
                )
    return BankStatement(
        account.account_number, first, end, "USD", opening, balance, tuple(lines), tuple(items)
    )


def aging(kind: str, items: list[OpenItem], as_of: date) -> Aging:
    buckets: dict[str, list[Decimal]] = {}
    for item in items:
        if item.issued > as_of or (item.settles is not None and item.settles <= as_of):
            continue
        overdue = (as_of - item.due).days
        slot = (
            0
            if overdue <= 0
            else 1
            if overdue <= 30
            else 2
            if overdue <= 60
            else 3
            if overdue <= 90
            else 4
        )
        row = buckets.setdefault(item.counterparty, [ZERO] * 5)
        row[slot] += item.amount
    lines = tuple(
        AgingLine(party, row[0], row[1], row[2], row[3], row[4], total=sum(row, ZERO))
        for party, row in sorted(buckets.items())
    )
    return Aging("ar" if kind == "ar" else "ap", as_of, AR if kind == "ar" else AP, lines)


def previous_month_end(d: date) -> date:
    return date(d.year, d.month, 1) - timedelta(days=1)
