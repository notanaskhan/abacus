"""The entity engines' ties (T-05-T09; DEC-3408): `foot` and `tie` returning a `Tally`. The compute
contract keeps each compute package to its own modules and `kernel.numeric`, so the entity engines
hold their own two checks (the workbook's are `workpapers/compute/tieouts.py`, the same states)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

ZERO: Final = Decimal(0)
TallyState = Literal["ties", "off", "missing"]


@dataclass(frozen=True, slots=True)
class Tally:
    check: str
    state: TallyState
    difference: Decimal | None
    label: str = ""

    @property
    def ok(self) -> bool:
        return self.state == "ties"


def tie(a: Decimal | None, b: Decimal | None, *, label: str = "") -> Tally:
    if a is None or b is None:
        return Tally("tie", "missing", None, label)
    difference = a - b
    return Tally("tie", "ties" if difference == 0 else "off", difference, label)


def foot(parts: Sequence[Decimal | None], total: Decimal | None, *, label: str = "") -> Tally:
    if total is None or any(p is None for p in parts):
        return Tally("foot", "missing", None, label)
    difference = sum((p for p in parts if p is not None), ZERO) - total
    return Tally("foot", "ties" if difference == 0 else "off", difference, label)
