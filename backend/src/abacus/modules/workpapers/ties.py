"""The tie engine (SPEC-310; A-02 §3.3; ADR-050: code computes). Pure and exact `Decimal`.

Three kinds of check on a trial balance:
- `balanced`: debits equal credits for a column (end or beginning of year).
- `tie`: the selected accounts' net, optionally negated for credit-normal accounts, equals an
  expected value cited to its document.
- `rollforward`: the same actual, against an expected value built from signed components
  ("288,500.00 + 96,200.00 - 57,450.00 - 14,850.00 = 312,400.00", with true minus signs).

A check is `tie` within its tolerance, `off` (with the difference, actual minus expected)
outside it, and `pending` when the trial balance can't answer (an account it doesn't hold, or a
beginning-of-year column with no prior year).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

Kind = Literal["balanced", "tie", "rollforward"]
Column = Literal["eoy", "boy"]
Status = Literal["tie", "off", "pending"]
_ZERO: Final = Decimal("0.00")
MINUS: Final = "\u2212"  # the typographic minus sign the design uses


@dataclass(frozen=True)
class Component:
    label: str
    sign: int  # +1 or -1
    value: Decimal


@dataclass(frozen=True)
class Definition:
    kind: Kind
    accounts: tuple[str, ...]
    column: Column
    negate: bool
    expected: Decimal | None  # tie
    components: tuple[Component, ...]  # rollforward
    tolerance: Decimal


@dataclass(frozen=True)
class Balances:
    """What a trial balance offers a check: each account's net per column (None without a prior
    year), and the debit and credit totals per column."""

    eoy: Mapping[str, Decimal]
    boy: Mapping[str, Decimal] | None
    totals: Mapping[str, tuple[Decimal, Decimal] | None]  # column -> (debit, credit)


@dataclass(frozen=True)
class Result:
    status: Status
    actual: Decimal | None
    expected: Decimal | None
    difference: Decimal | None
    formula: str | None
    missing: tuple[str, ...]


def money(value: Decimal) -> str:
    sign = MINUS if value < 0 else ""
    whole, _, cents = f"{abs(value):.2f}".partition(".")
    return f"{sign}{int(whole):,}.{cents}"


def rollforward_text(components: Sequence[Component], total: Decimal) -> str:
    parts: list[str] = []
    for i, c in enumerate(components):
        amount = money(c.value)
        if i == 0:
            parts.append(amount if c.sign > 0 else f"{MINUS}{amount}")
        else:
            parts.append(f"{'+' if c.sign > 0 else MINUS} {amount}")
    return f"{' '.join(parts)} = {money(total)}"


def _verdict(actual: Decimal, expected: Decimal, tolerance: Decimal) -> tuple[Status, Decimal]:
    difference = actual - expected
    return ("tie" if abs(difference) <= tolerance else "off"), difference


def evaluate(d: Definition, balances: Balances) -> Result:
    if d.kind == "balanced":
        pair = balances.totals.get(d.column)
        if pair is None:
            return Result("pending", None, None, None, None, ())
        debit, credit = pair
        status, difference = _verdict(debit, credit, d.tolerance)
        return Result(status, debit, credit, difference, None, ())
    nets = balances.eoy if d.column == "eoy" else balances.boy
    if nets is None:
        return Result("pending", None, None, None, None, ())
    missing = tuple(a for a in d.accounts if a not in nets)
    if missing or not d.accounts:
        return Result("pending", None, None, None, None, missing)
    actual = sum((nets[a] for a in d.accounts), _ZERO)
    if d.negate:
        actual = -actual
    if d.kind == "tie":
        if d.expected is None:
            return Result("pending", actual, None, None, None, ())
        status, difference = _verdict(actual, d.expected, d.tolerance)
        return Result(status, actual, d.expected, difference, None, ())
    total = sum((c.value * c.sign for c in d.components), _ZERO)
    status, difference = _verdict(actual, total, d.tolerance)
    return Result(status, actual, total, difference, rollforward_text(d.components, total), ())
