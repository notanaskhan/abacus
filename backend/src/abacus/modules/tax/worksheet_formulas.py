"""Derived lines of the individual return, computed by code (T-04-T16; ADR-050, ADR-052;
T-04 §4.3; SPEC-649). A field whose derivation is `formula` names one of these by
`formula_ref`; the data never holds an expression. Each formula reads other fields of the same
worksheet by their keys, in `Decimal`, and the recompute walks them in dependency order until
nothing moves, so an edit to line 20 recomputes lines 21, 22, 24, 33, 34 and 37 (the balance
due) deterministically.

Form 1040 (2025): 21 = 19 + 20; 22 = max(0, 18 - 21); 24 = 22 + 23; 33 = 25d + 26 + 32;
34 = max(0, 33 - 24) (overpaid); 37 = max(0, 24 - 33) (amount you owe).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

ZERO: Final = Decimal("0.00")
Values = Mapping[str, Decimal | None]


@dataclass(frozen=True)
class Formula:
    ref: str
    inputs: tuple[str, ...]
    compute: Callable[[Callable[[str], Decimal]], Decimal]


def _sum(*keys: str) -> Callable[[Callable[[str], Decimal]], Decimal]:
    return lambda v: sum((v(k) for k in keys), ZERO)


def _less(a: str, b: str) -> Callable[[Callable[[str], Decimal]], Decimal]:
    """max(0, a - b)."""
    return lambda v: max(ZERO, v(a) - v(b))


_L33: Final = ("line_25d", "line_26", "line_32")
FORMULAS: Final[dict[str, Formula]] = {
    f.ref: f
    for f in (
        Formula("f1040.line_21", ("line_19", "line_20"), _sum("line_19", "line_20")),
        Formula("f1040.line_22", ("line_18", "line_21"), _less("line_18", "line_21")),
        Formula("f1040.line_24", ("line_22", "line_23"), _sum("line_22", "line_23")),
        Formula("f1040.line_33", _L33, _sum(*_L33)),
        Formula("f1040.line_34", ("line_24", "line_33"), _less("line_33", "line_24")),
        Formula("f1040.line_37", ("line_24", "line_33"), _less("line_24", "line_33")),
    )
}


class UnknownFormula(ValueError):
    """A field names a formula no code defines: the worksheet cannot recompute (fail closed)."""


def recompute(
    values: Mapping[str, Decimal | None], formulas: Mapping[str, str]
) -> dict[str, Decimal]:
    """`formulas`: field key -> formula ref. Returns every formula field whose value changed,
    with its new value, after iterating to a fixed point (at most one pass per formula)."""
    current: dict[str, Decimal | None] = dict(values)
    changed: dict[str, Decimal] = {}
    for ref in formulas.values():
        if ref not in FORMULAS:
            raise UnknownFormula(ref)
    for _ in range(len(formulas) + 1):
        moved = False
        for key, ref in formulas.items():
            formula = FORMULAS[ref]

            def value(k: str) -> Decimal:
                found = current.get(k)
                return found if found is not None else ZERO

            new = formula.compute(value).quantize(Decimal("0.01"))
            if current.get(key) != new:
                current[key] = new
                changed[key] = new
                moved = True
        if not moved:
            return changed
    return changed
