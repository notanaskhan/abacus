"""The search for unrecorded liabilities, by code (SPEC-038 AC-2 to AC-4; TASK-087; ADR-132).

Pure functions. A payment is a journal entry in the subsequent-period ledger crediting a confirmed
bank account; its amount is those credits. Each timing band (days after year end) has a threshold;
a payment at or above its band's threshold is selected, and people's picks join with reasons. For
each selected payment, the year-end ledger is searched for a matching bill: a credit to the
payables account from the same supplier (case and spacing ignored) for the same amount, dated on
or before year end. That is a fact for the person, never a conclusion.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from abacus.modules.ledger.api import GlEntry, JournalKey, journals
from abacus.modules.sampling.population import Entry, Population
from abacus.modules.sampling.selection import Selected

PAYMENTS_RULE_VERSION: Final = 1


@dataclass(frozen=True)
class Band:
    until_day: int | None  # the band covers payments up to this many days after year end
    threshold: Decimal


@dataclass(frozen=True)
class Bill:
    reference: str
    posted_on: date


def build_payments(
    postings: Iterable[GlEntry], bank: frozenset[str]
) -> tuple[Population, Decimal]:
    """Payments, and the snapshot's total bank-account credits they must tie to (AC-2)."""
    found: list[Entry] = []
    total = Decimal(0)
    lines = 0
    per_account: dict[str, int] = {}
    debit = credit = Decimal(0)
    for key, group in journals(postings):
        lines += len(group)
        for p in group:
            per_account[p.account_code] = per_account.get(p.account_code, 0) + 1
            debit += p.debit
            credit += p.credit
        paid = sum((p.credit for p in group if p.account_code in bank), Decimal(0))
        total += paid
        if paid <= 0:
            continue
        first = group[0]
        found.append(
            Entry(
                key,
                first.posted_on,
                first.kind,
                first.reference,
                first.counterparty,
                tuple(dict.fromkeys(p.description for p in group if p.description)),
                tuple(p.line_no for p in group),
                tuple(dict.fromkeys(p.account_code for p in group)),
                paid,
                paid,
            )
        )
    return Population(tuple(found), lines, debit, credit, per_account), total


def ties(population: Population, bank_credits: Decimal) -> str | None:
    paid = sum((e.amount for e in population.entries), Decimal(0))
    return None if paid == bank_credits else "bank_credits"


def band_of(posted_on: date, year_end: date, bands: Sequence[Band]) -> int:
    days = (posted_on - year_end).days
    for n, band in enumerate(bands, start=1):
        if band.until_day is None or days <= band.until_day:
            return n
    return len(bands)


def select_payments(
    population: Population,
    year_end: date,
    bands: Sequence[Band],
    picks: Mapping[JournalKey, str] | None = None,
) -> list[Selected]:
    """AC-3: each payment at or above its band's threshold, plus people's picks."""
    reasons = dict(picks or {})
    chosen: list[Selected] = []
    for entry in population.entries:
        n = band_of(entry.posted_on, year_end, bands)
        rules: list[str] = []
        if entry.amount >= bands[n - 1].threshold:
            rules.append("band")
        if entry.key in reasons:
            rules.append("picked")
        if rules:
            chosen.append(Selected(entry, tuple(rules), reasons.get(entry.key), n))
    known = {e.key for e in population.entries}
    if any(k not in known for k in reasons):
        raise KeyError("a pick names a payment outside the population")
    return chosen


def _party(name: str | None) -> str:
    return " ".join((name or "").casefold().split())


def bills_by_party(
    year_postings: Iterable[GlEntry], payables: frozenset[str], year_end: date
) -> dict[tuple[str, Decimal], Bill]:
    """AC-4: credits to the payables account on or before year end, by supplier and amount."""
    found: dict[tuple[str, Decimal], Bill] = {}
    for p in year_postings:
        if p.account_code in payables and p.credit > 0 and p.posted_on <= year_end:
            found.setdefault(
                (_party(p.counterparty), p.credit),
                Bill(p.reference or "", p.posted_on),
            )
    return found


def recorded_bill(selected: Selected, bills: Mapping[tuple[str, Decimal], Bill]) -> Bill | None:
    return bills.get((_party(selected.entry.counterparty), selected.entry.amount))
