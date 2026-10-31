"""The account-mapping rules, by code (A-03-T08; A-03 §3 F6 US-6.1; ADR-341 §5; ADR-050).

Pure: no database, no clock, no other module. `ledger.mapping` reads the rows and calls these.

- **Order** (`resolve_line`): a person's edit, then the prior year's FS line for the same
  normalised account code (matched by FS-line key, so a later grouping-set version still matches),
  then the version's account-number ranges (first rule in order wins, numeric-aware), else
  unmapped. No rule suggests: `suggested` is A-09's TB mapper's (ADR-005).
- **Tallies** (`tallies`): mapped, need review, by method, and TB balanced (the snapshot's lines
  net to zero: debits equal credits).
- **Subtotals** (`subtotals`): each grouping's mapped accounts summed; where the source TB carries
  a summary line for that grouping, the difference reads `off` (never adjusted).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal
from uuid import UUID

Method = Literal["manual", "prior_year", "number_range"]
Confidence = Literal["high", "medium", "low"]
# The confidence a method carries, in words (A-03 §3 F6: "Prior-year match · High, Number range ·
# Medium"); a person's edit carries none ("—").
CONFIDENCE: Final[Mapping[Method, Confidence | None]] = {
    "prior_year": "high",
    "number_range": "medium",
    "manual": None,
}
_ZERO: Final = Decimal(0)


def account_key(code: str) -> tuple[int, int, str]:
    """Numeric codes compare as numbers ("900" < "1000"); others as text after them."""
    text = code.strip()
    return (0, int(text), "") if text.isdigit() else (1, 0, text)


def normalised_code(code: str) -> str:
    """An account code as the prior-year match compares it: letters and digits, lower case."""
    return re.sub(r"[^0-9a-z]", "", code.lower())


def rule_line(code: str, ranges: Sequence[tuple[str, str, UUID]]) -> UUID | None:
    """The first range (in order) holding the account code."""
    key = account_key(code)
    for low, high, line in ranges:
        if account_key(low) <= key <= account_key(high):
            return line
    return None


def resolve_line(
    code: str,
    edited: UUID | None,
    prior: Mapping[str, str],
    by_key: Mapping[str, UUID],
    ranges: Sequence[tuple[str, str, UUID]],
) -> tuple[UUID | None, Method | None]:
    """One account's FS line and how it was found: a person's edit, then the prior year's line
    for the same normalised code, then the number ranges, else unmapped."""
    if edited is not None:
        return edited, "manual"
    key = prior.get(normalised_code(code))
    if key is not None and key in by_key:
        return by_key[key], "prior_year"
    found = rule_line(code, ranges)
    return (found, "number_range") if found is not None else (None, None)


@dataclass(frozen=True)
class Tallies:
    total: int
    mapped: int
    need_review: int
    prior_year: int
    number_range: int
    manual: int
    tb_balanced: bool


def tallies(methods: Sequence[Method | None], balances: Iterable[Decimal]) -> Tallies:
    """MAPPED "n of N", NEED REVIEW, by method, and TB BALANCED (lines net to zero)."""
    mapped = sum(1 for m in methods if m is not None)
    return Tallies(
        total=len(methods),
        mapped=mapped,
        need_review=len(methods) - mapped,
        prior_year=sum(1 for m in methods if m == "prior_year"),
        number_range=sum(1 for m in methods if m == "number_range"),
        manual=sum(1 for m in methods if m == "manual"),
        tb_balanced=sum(balances, _ZERO) == 0,
    )


@dataclass(frozen=True)
class Subtotal:
    grouping_key: str
    subtotal: Decimal
    source_total: Decimal | None
    off: Decimal | None


def subtotals(
    groupings: Sequence[str],
    mapped: Iterable[tuple[str, Decimal]],
    source_totals: Mapping[str, Decimal] | None = None,
) -> list[Subtotal]:
    """Each grouping's subtotal of its mapped accounts (`(grouping_key, balance)` pairs), in the
    groupings' order; `off` is the subtotal less the source TB's summary line where it has one,
    None where it ties or carries no summary line."""
    sums = dict.fromkeys(groupings, _ZERO)
    for key, balance in mapped:
        if key in sums:
            sums[key] += balance
    out: list[Subtotal] = []
    for key in groupings:
        source = (source_totals or {}).get(key)
        off = None if source is None or sums[key] == source else sums[key] - source
        out.append(Subtotal(key, sums[key], source, off))
    return out
