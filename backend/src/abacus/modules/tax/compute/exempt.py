"""E12: the Form 990 engine (T-06-T18; T-06 §3 F5; SPEC-702; DEC-77, ADR-050). Pure and
`Decimal` only, no I/O and no model.

- **Part IX functional allocation**: a line is charged directly to one column or split by a time
  study's percentages through `kernel.numeric.allocate` (largest remainder, whole dollars), so
  program + management and general + fundraising equals the line total on every row
  (crossfoot) and every column foots.
- **Program ratio** = program service expenses / total functional expenses, one decimal.
- **Schedule A public support** (IRC 170(b)(1)(A)(vi), Part II): public support / total support
  over the five-year period; the test is met at 33 1/3 percent or more (the 10 percent
  facts-and-circumstances test is a person's judgment, never the engine's).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from typing import Final, Literal

from abacus.kernel.numeric import allocate

ZERO: Final = Decimal("0")
HUNDRED: Final = Decimal("100")
ENGINE_VERSION: Final = "e12.1"
Column = Literal["program", "management_general", "fundraising"]
COLUMNS: Final[tuple[Column, ...]] = ("program", "management_general", "fundraising")
PUBLIC_SUPPORT_TEST: Final = Fraction(1, 3)


@dataclass(frozen=True, slots=True)
class ExpenseLine:
    line: str
    label: str
    total: Decimal
    program: Decimal
    management_general: Decimal
    fundraising: Decimal
    basis: Literal["direct", "time_study"]

    @property
    def crossfoots(self) -> bool:
        return self.program + self.management_general + self.fundraising == self.total


def direct(line: str, label: str, total: Decimal, column: Column) -> ExpenseLine:
    split = {c: (total if c == column else ZERO) for c in COLUMNS}
    return ExpenseLine(line, label, total, split["program"], split["management_general"],
                       split["fundraising"], "direct")  # fmt: skip


def time_study(
    line: str, label: str, total: Decimal, pct: Mapping[Column, Decimal]
) -> ExpenseLine:
    if sum(pct.values(), ZERO) != HUNDRED:
        raise ValueError("time-study percentages must sum to 100")
    shares = allocate(total, [pct.get(c, ZERO) for c in COLUMNS], places=0)
    return ExpenseLine(line, label, total, shares[0], shares[1], shares[2], "time_study")


@dataclass(frozen=True, slots=True)
class PartIX:
    lines: tuple[ExpenseLine, ...]
    total: Decimal
    program: Decimal
    management_general: Decimal
    fundraising: Decimal
    program_ratio: Decimal  # percent, one decimal


def part_ix(lines: Sequence[ExpenseLine]) -> PartIX:
    for ln in lines:
        if not ln.crossfoots:
            raise ValueError(f"Part IX line {ln.line} does not crossfoot")
    total = sum((ln.total for ln in lines), ZERO)
    program = sum((ln.program for ln in lines), ZERO)
    mg = sum((ln.management_general for ln in lines), ZERO)
    fr = sum((ln.fundraising for ln in lines), ZERO)
    ratio = (
        ZERO if total == 0 else (program * HUNDRED / total).quantize(Decimal("0.1"), ROUND_HALF_UP)
    )
    return PartIX(tuple(lines), total, program, mg, fr, ratio)


@dataclass(frozen=True, slots=True)
class PublicSupport:
    public_support: Decimal
    total_support: Decimal
    pct: Decimal  # percent, one decimal
    met: bool


def public_support(public: Decimal, total: Decimal) -> PublicSupport:
    if total <= 0 or public < 0 or public > total:
        raise ValueError("public support must be between 0 and total support")
    met = Fraction(public) / Fraction(total) >= PUBLIC_SUPPORT_TEST
    pct = (public * HUNDRED / total).quantize(Decimal("0.1"), ROUND_HALF_UP)
    return PublicSupport(public, total, pct, met)
