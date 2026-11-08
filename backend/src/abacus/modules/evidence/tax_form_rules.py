"""Tax information-return rules for the form maps (P-11-T34; TASK-6209; DEC-2809; P-11 F8, AC8.4,
AC8.7). PROTECTED.

Information returns differ from IRS notices in three ways the notice maps never needed:

- **The year is on the title line** ("Form 1099-DIV 2025"), not after "Tax year:". A map that
  declares `year_after` reads the four digits that follow that anchor on its line.
- **CORRECTED.** A map that declares `corrected_anchor` writes `<form>.corrected = true` when the
  anchor is marked: either the word stands alone (a corrected copy printed as such), or the printed
  "CORRECTED (if checked)" carries a check mark beside it. The printed caption alone is not a mark.
- **Code tie-outs** check format and ordering only (1099-DIV 1b ≤ 1a; W-2 box 4 ≤ box 3; 1099-R 2a
  ≤ 1): a field that breaks one is kept as read and flagged `low_confidence`, never corrected and
  never summed (AC8.7).

Only maps of the `tax_forms` family declare these keys, and that family runs only where the firm's
`evidence.form_extraction` variant covers it (`notices_tax_forms` or `all`), so the notice path is
unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from decimal import Decimal, InvalidOperation
from typing import Final

_YEAR: Final = re.compile(r"\b(20\d{2})\b")
_CHECKED: Final = frozenset({"x", "✓", "✔", "☒", "■", "[x]"})


@dataclass(frozen=True)
class TieOut:
    """`smaller` may not exceed `larger` when both were read."""

    smaller: str
    larger: str


def title_year(joined: str, year_after: str) -> int | None:
    """The tax year printed after the form's title anchor on the same stretch of text."""
    at = joined.find(year_after)
    if at < 0:
        return None
    match = _YEAR.search(joined[at + len(year_after) : at + len(year_after) + 40])
    return int(match.group(1)) if match else None


def corrected(words: Sequence[str], anchor: str) -> bool:
    """A marked CORRECTED box: the word alone, or the "(if checked)" caption with a mark beside
    it. The caption with no mark is a blank box."""
    lowered = [w.lower() for w in words]
    target = anchor.lower()
    for i, word in enumerate(lowered):
        if word.strip(":") != target:
            continue
        following = lowered[i + 1 : i + 4]
        caption = (
            len(following) >= 2 and following[0] == "(if" and following[1].startswith("checked")
        )
        if not caption:
            return True
        neighbours = lowered[max(0, i - 1) : i] + lowered[i + 3 : i + 4]
        if any(n in _CHECKED for n in neighbours):
            return True
    return False


def _amount(value: str) -> Decimal | None:
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def broken_tie_outs(values: Mapping[str, str], tie_outs: Sequence[TieOut]) -> set[str]:
    """The field keys that break a tie-out (both sides read and numeric)."""
    broken: set[str] = set()
    for rule in tie_outs:
        small = values.get(rule.smaller)
        large = values.get(rule.larger)
        if small is None or large is None:
            continue
        a, b = _amount(small), _amount(large)
        if a is not None and b is not None and a > b:
            broken |= {rule.smaller, rule.larger}
    return broken


def flag(fields: Sequence[object], broken: set[str]) -> list[object]:
    """Mark the fields a tie-out broke `low_confidence` (as read; nothing changes the value)."""
    out: list[object] = []
    for f in fields:
        key = getattr(f, "field_key", None)
        out.append(replace(f, low_confidence=True) if key in broken else f)  # type: ignore[type-var]  # the extractor's field dataclass, typed object here
    return out


__all__ = ["TieOut", "broken_tie_outs", "corrected", "flag", "title_year"]
