"""E10: the S-corporation AAA engine (T-06-T24; TASK-8719; T-06 §3 F5; SPEC-702; DEC-77, ADR-050).
Pure, `Decimal` only, no I/O and no model.

- **Columns**: AAA (accumulated adjustments account), PTI (previously taxed income), E&P
  (accumulated earnings and profits) and OAA (other adjustments account, tax-exempt items).
- **AAA roll**: beginning + income items - loss and deduction items - nondeductible expenses;
  distributions come off last and never take AAA below zero (§1368(e)(1)(A)), while losses can.
- **Distribution ordering** (§1368(c)): AAA, then PTI, then E&P (a dividend), then OAA, then the
  remainder reduces stock basis; a distribution above AAA routes to the next column.
- **Shareholder allocation**: pro rata per share per day (§1377(a)(1)), to whole dollars by
  largest remainder, so the shares foot exactly to the item.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Final

from abacus.kernel.numeric import allocate

ZERO: Final = Decimal("0")
ENGINE_VERSION: Final = "e10.1"
ORDER: Final = ("aaa", "pti", "ep", "oaa", "basis")


@dataclass(frozen=True, slots=True)
class AaaRoll:
    beginning: Decimal
    income: Decimal
    losses: Decimal
    nondeductible: Decimal
    before_distributions: Decimal
    distributions: Decimal
    ending: Decimal


def aaa_roll(
    beginning: Decimal,
    *,
    income: Decimal,
    losses: Decimal,
    nondeductible: Decimal,
    distributions: Decimal,
) -> AaaRoll:
    before = beginning + income - losses - nondeductible
    from_aaa = min(distributions, max(before, ZERO))
    return AaaRoll(beginning, income, losses, nondeductible, before, from_aaa, before - from_aaa)


def distribute(amount: Decimal, balances: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """The distribution by column in §1368(c)'s order; what no column holds reduces basis."""
    left = amount
    out: dict[str, Decimal] = {}
    for column in ORDER[:-1]:
        take = min(left, max(balances.get(column, ZERO), ZERO))
        out[column] = take
        left -= take
    out["basis"] = left
    return out


def per_share_per_day(
    item: Decimal, shareholders: Mapping[str, tuple[int, int]], *, year_days: int = 365
) -> dict[str, Decimal]:
    """`shareholders`: name → (shares, days held). Whole dollars by largest remainder."""
    names = list(shareholders)
    weights = [Decimal(shareholders[n][0] * shareholders[n][1]) / year_days for n in names]
    return dict(zip(names, allocate(item, weights, places=0), strict=True))


__all__ = ["ENGINE_VERSION", "ORDER", "AaaRoll", "aaa_roll", "distribute", "per_share_per_day"]
