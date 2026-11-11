"""E13 part 2: tie-out checks (T-05-T08; ADR-237 §4; ADR-050; DEC-3407).

Code checks every tie; a model never does arithmetic. Each check returns a `Tally`: its state, the
difference (exact `Decimal`) and what it compared, so a workpaper's tick mark and SHL-09's
explanation come from the same answer.

- `foot(parts, total)`: the column's parts sum to its total.
- `crossfoot(rows, row_totals, column_totals)`: every row sums to its row total, every column to
  its column total, and the row totals and column totals reach the same grand total.
- `tie(a, b)`: two figures from different places agree.
- `off_by(a, b, tolerance)`: within `tolerance` (a rounding allowance) is `within`, not `ties`.

States: `ties` (difference 0), `within` (0 < |difference| ≤ tolerance), `off` (beyond it) and
`missing` (a figure is absent: never treated as 0).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Final

ZERO: Final = Decimal(0)


class TallyState(StrEnum):
    TIES = "ties"
    WITHIN = "within"
    OFF = "off"
    MISSING = "missing"


@dataclass(frozen=True, slots=True)
class Tally:
    check: str  # foot · crossfoot · tie · off_by
    state: TallyState
    difference: Decimal | None
    label: str = ""

    @property
    def ok(self) -> bool:
        return self.state in (TallyState.TIES, TallyState.WITHIN)


def _state(difference: Decimal, tolerance: Decimal) -> TallyState:
    if difference == 0:
        return TallyState.TIES
    return TallyState.WITHIN if abs(difference) <= tolerance else TallyState.OFF


def off_by(
    a: Decimal | None, b: Decimal | None, tolerance: Decimal = ZERO, *, label: str = ""
) -> Tally:
    if a is None or b is None:
        return Tally("off_by", TallyState.MISSING, None, label)
    if tolerance < 0:
        raise ValueError("tolerance must not be negative")
    difference = a - b
    return Tally("off_by", _state(difference, tolerance), difference, label)


def tie(a: Decimal | None, b: Decimal | None, *, label: str = "") -> Tally:
    found = off_by(a, b, ZERO, label=label)
    return Tally("tie", found.state, found.difference, label)


def foot(parts: Sequence[Decimal | None], total: Decimal | None, *, label: str = "") -> Tally:
    if total is None or any(p is None for p in parts):
        return Tally("foot", TallyState.MISSING, None, label)
    difference = sum((p for p in parts if p is not None), ZERO) - total
    return Tally("foot", _state(difference, ZERO), difference, label)


def crossfoot(
    rows: Sequence[Sequence[Decimal | None]],
    row_totals: Sequence[Decimal | None],
    column_totals: Sequence[Decimal | None],
    *,
    label: str = "",
) -> list[Tally]:
    """One tally per row, one per column, then the grand total's (rows' totals vs columns')."""
    if len(rows) != len(row_totals):
        raise ValueError("one total per row")
    width = len(column_totals)
    if any(len(r) != width for r in rows):
        raise ValueError("every row has one cell per column")
    out = [
        foot(r, t, label=f"{label} row {i + 1}")
        for i, (r, t) in enumerate(zip(rows, row_totals, strict=True))
    ]
    for c in range(width):
        out.append(foot([r[c] for r in rows], column_totals[c], label=f"{label} column {c + 1}"))
    grand_rows = (
        None
        if any(t is None for t in row_totals)
        else sum((t for t in row_totals if t is not None), ZERO)
    )
    out.append(foot(list(column_totals), grand_rows, label=f"{label} grand total"))
    return out
