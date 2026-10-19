"""A procedure's population, built by code from a reconciled general ledger snapshot (ADR-132;
SPEC-037 AC-1; TASK-083).

Postings group into journal entries by ledger's `journal_key` (the same grouping the journal
listing workbook uses). The population must tie to its snapshot, every line in exactly one entry
and debits equal to the snapshot's, before anything is selected. Pure: no database, no clock.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final

from abacus.modules.ledger.api import GlEntry, JournalKey, journals

RULE_VERSION: Final = 1  # how postings become entries; recorded on each population


@dataclass(frozen=True)
class Entry:
    key: JournalKey
    posted_on: date
    kind: str | None
    reference: str | None
    counterparty: str | None
    descriptions: tuple[str, ...]
    line_nos: tuple[int, ...]
    accounts: tuple[str, ...]
    amount: Decimal  # the entry's total debits
    credit: Decimal


@dataclass(frozen=True)
class Population:
    entries: tuple[Entry, ...]
    line_count: int
    total_debit: Decimal
    total_credit: Decimal
    postings_per_account: dict[str, int]


def build_population(postings: Iterable[GlEntry]) -> Population:
    """Every posting in exactly one entry, entries in date, type and reference order."""
    entries: list[Entry] = []
    per_account: Counter[str] = Counter()
    lines = 0
    debit = credit = Decimal(0)
    for key, group in journals(postings):
        lines += len(group)
        per_account.update(p.account_code for p in group)
        group_debit = sum((p.debit for p in group), Decimal(0))
        group_credit = sum((p.credit for p in group), Decimal(0))
        debit += group_debit
        credit += group_credit
        first = group[0]
        entries.append(
            Entry(
                key,
                first.posted_on,
                first.kind,
                first.reference,
                first.counterparty,
                tuple(dict.fromkeys(p.description for p in group if p.description)),
                tuple(p.line_no for p in group),
                tuple(dict.fromkeys(p.account_code for p in group)),
                group_debit,
                group_credit,
            )
        )
    return Population(tuple(entries), lines, debit, credit, dict(per_account))


def tie_out(population: Population, *, line_count: int, total_debit: Decimal) -> str | None:
    """None when the population ties to its snapshot; else why not (AC-1)."""
    if population.line_count != line_count:
        return "line_count"
    if population.total_debit != total_debit:
        return "total_debit"
    if population.total_debit != population.total_credit:
        return "unbalanced"
    return None
