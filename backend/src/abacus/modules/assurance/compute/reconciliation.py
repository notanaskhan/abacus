"""Confirmation reconciliation, by code (A-08-T11 golden engine; A-08-T18 reads it; AU-C 505;
ADR-050).

The balance per books, the reconciling items a person (or the agent, proposed) lists, and the
balance per respondent: what is left unreconciled is books + items - respondent, to the cent. Zero
reads "tie". Whether a remaining difference is below clearly trivial compares its absolute value
with the engagement's CT. The standard library only.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

CENT: Final = Decimal("0.01")


@dataclass(frozen=True)
class Reconciled:
    books: Decimal
    items_total: Decimal
    respondent: Decimal
    unreconciled: Decimal
    ties: bool
    below_clearly_trivial: bool | None


def reconcile(
    books: Decimal,
    respondent: Decimal,
    items: Iterable[Decimal],
    clearly_trivial: Decimal | None = None,
) -> Reconciled:
    """books + Σ items - respondent, quantized to the cent (no rounding: amounts are cents)."""
    listed = [Decimal(i) for i in items]
    total = sum(listed, Decimal("0.00"))
    left = (books + total - respondent).quantize(CENT)
    below = None if clearly_trivial is None else abs(left) < clearly_trivial
    return Reconciled(books, total.quantize(CENT), respondent, left, left == 0, below)
