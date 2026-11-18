"""E4: the book-tax engine (T-06-T15; T-06 §3 F2; SPEC-702; DEC-77, ADR-050). Pure, `Decimal`
only, no I/O and no model.

- **M-3 requirement** (Form 1065 / 1120 Schedule M-3 instructions): total assets at year end of
  at least $10,000,000 require Schedule M-3; between $10 million and $50 million an entity may
  file Schedule M-1 in place of M-3 Parts II and III (Part I and the M-1 alternative remain), which
  this engine reports as reference only (never both filed).
- **Parts II-III**: every row foots (a) + (b) + (c) = (d); column (a) totals Part I line 11 (net
  income per the income statement) and column (d) totals Analysis of Net Income line 1.
- **Schedule M-1** (reference or the 1120 path): line 1 net income per books, additions, then
  subtractions to income per return; the 1120 path starts from net income per books with the
  income-tax expense added back.
- **M-2 roll**: beginning + net income + other increases - distributions - other decreases =
  ending, compared with Schedule L line 21.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

ZERO: Final = Decimal("0")
ENGINE_VERSION: Final = "e4.1"
M3_THRESHOLD: Final = Decimal("10000000")
M1_OPTION_CEILING: Final = Decimal("50000000")
Kind = Literal["temporary", "permanent", "none"]
Tally = Literal["tie", "off"]


@dataclass(frozen=True, slots=True)
class M3Row:
    item: str
    col_a: Decimal  # income (loss) per income statement
    col_b: Decimal  # temporary difference
    col_c: Decimal  # permanent difference
    col_d: Decimal  # income (loss) per tax return

    @property
    def foots(self) -> bool:
        return self.col_a + self.col_b + self.col_c == self.col_d


@dataclass(frozen=True, slots=True)
class M3Requirement:
    required: bool
    m1_option: bool  # may file M-1 in place of Parts II-III (reference only)


@dataclass(frozen=True, slots=True)
class M3Reconciliation:
    rows: tuple[M3Row, ...]
    book_income: Decimal
    temporary: Decimal
    permanent: Decimal
    income_per_return: Decimal
    part_i_tie: Tally
    analysis_tie: Tally


@dataclass(frozen=True, slots=True)
class M1:
    line_1: Decimal
    additions: Decimal
    line_5: Decimal
    subtractions: Decimal
    line_9: Decimal


@dataclass(frozen=True, slots=True)
class M2Roll:
    beginning: Decimal
    net_income: Decimal
    other_increases: Decimal
    distributions: Decimal
    other_decreases: Decimal
    ending: Decimal
    schedule_l: Decimal
    difference: Decimal
    tally: Tally


def m3_requirement(total_assets: Decimal) -> M3Requirement:
    required = total_assets >= M3_THRESHOLD
    return M3Requirement(required, required and total_assets < M1_OPTION_CEILING)


def reconcile_m3(
    rows: Sequence[M3Row], *, part_i_line_11: Decimal, analysis_line_1: Decimal
) -> M3Reconciliation:
    """Parts II-III totals with both tie-outs; a row that does not foot raises (the engine never
    produces one, and the table CHECK refuses one)."""
    for row in rows:
        if not row.foots:
            raise ValueError(f"M-3 row does not foot: {row.item}")
    a = sum((r.col_a for r in rows), ZERO)
    b = sum((r.col_b for r in rows), ZERO)
    c = sum((r.col_c for r in rows), ZERO)
    d = sum((r.col_d for r in rows), ZERO)
    return M3Reconciliation(
        tuple(rows),
        a,
        b,
        c,
        d,
        "tie" if a == part_i_line_11 else "off",
        "tie" if d == analysis_line_1 else "off",
    )


def m1(
    net_income_per_books: Decimal, additions: Sequence[Decimal], subtractions: Sequence[Decimal]
) -> M1:
    add = sum(additions, ZERO)
    sub = sum(subtractions, ZERO)
    line_5 = net_income_per_books + add
    return M1(net_income_per_books, add, line_5, sub, line_5 - sub)


def m1_from_1120(pretax_book_income: Decimal, income_tax_expense: Decimal) -> M1:
    """The 1120 path: net income per books (after tax) on line 1, the tax expense added back."""
    return m1(pretax_book_income - income_tax_expense, [income_tax_expense], [])


def roll_m2(
    *,
    beginning: Decimal,
    net_income: Decimal,
    other_increases: Decimal = ZERO,
    distributions: Decimal = ZERO,
    other_decreases: Decimal = ZERO,
    schedule_l_line_21: Decimal,
) -> M2Roll:
    ending = beginning + net_income + other_increases - distributions - other_decreases
    diff = ending - schedule_l_line_21
    return M2Roll(
        beginning,
        net_income,
        other_increases,
        distributions,
        other_decreases,
        ending,
        schedule_l_line_21,
        diff,
        "tie" if diff == ZERO else "off",
    )
