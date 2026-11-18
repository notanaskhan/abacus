"""E9: the apportionment and PTET engine (T-06-T17; T-06 §3 F4; SPEC-702; DEC-77, ADR-050).
Pure and `Decimal` only: no I/O beyond the protected rate files, no model.

- **Sourcing**: a rental partnership's income is sourced by property location (Form 8825 rows):
  each state's numerator is its properties' net income, the denominator Schedule K line 2; shares
  are shown to one decimal and must sum to 100.0.
- **PTET** = state base x the state's rate, rounded half up to whole dollars.
- **Partner credits** split each state's PTET by period-weighted percentage through
  `kernel.numeric.allocate` (largest remainder), so every state's credits foot exactly to its
  PTET. A partner whose PTET statement rounds half up keeps that figure (a recorded override);
  the others share the rest by largest remainder.
- **Checks**: a state without a published rate (`ParameterMissing`), a factor with no property
  (`unmapped`), and a PTET with no payment (`payment_gap`).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Final

import yaml

from abacus.kernel.numeric import allocate

ZERO: Final = Decimal("0")
HUNDRED: Final = Decimal("100")
ENGINE_VERSION: Final = "e9.1"
_DIR: Final = Path(__file__).parent / "parameters" / "ptet"


class ParameterMissing(LookupError):
    """No published PTET rate for this state and year."""


@cache
def rates(tax_year: int) -> dict[str, Decimal]:
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.exists():
        raise ParameterMissing(f"ptet ty{tax_year}")
    data = yaml.safe_load(path.read_text())
    return {str(k): Decimal(str(v)) for k, v in dict(data["rates"]).items()}


def rate(tax_year: int, state: str) -> Decimal:
    found = rates(tax_year).get(state)
    if found is None:
        raise ParameterMissing(f"ptet ty{tax_year} {state}")
    return found


@dataclass(frozen=True, slots=True)
class Apportionment:
    state: str
    numerator: Decimal
    denominator: Decimal
    share: Decimal  # percent, one decimal


def apportion(numerators: Mapping[str, Decimal], denominator: Decimal) -> list[Apportionment]:
    if sum(numerators.values(), ZERO) != denominator:
        raise ValueError("state numerators do not foot to the base")
    return [
        Apportionment(
            s, n, denominator, (n * HUNDRED / denominator).quantize(Decimal("0.1"), ROUND_HALF_UP)
        )
        for s, n in numerators.items()
    ]


def ptet(base: Decimal, rate_pct: Decimal) -> Decimal:
    return (base * rate_pct / HUNDRED).quantize(Decimal("1"), ROUND_HALF_UP)


def partner_credits(
    state_ptet: Decimal,
    weights: Mapping[str, Decimal],
    *,
    half_up: Sequence[str] = (),
) -> dict[str, Decimal]:
    """Split one state's PTET by period-weighted percentage; `half_up` partners keep their own
    half-up figure and the rest share the remainder by largest remainder (foots exactly)."""
    total_w = sum(weights.values(), ZERO)
    fixed = {
        p: (state_ptet * weights[p] / total_w).quantize(Decimal("1"), ROUND_HALF_UP)
        for p in half_up
    }
    rest = [p for p in weights if p not in fixed]
    shares = allocate(state_ptet - sum(fixed.values(), ZERO), [weights[p] for p in rest], places=0)
    out = dict(zip(rest, shares, strict=True)) | fixed
    return {p: out[p] for p in weights}


def payment_gaps(ptet_by_state: Mapping[str, Decimal], paid: Mapping[str, Decimal]) -> list[str]:
    """States whose elected PTET has no payment of the full amount."""
    return [s for s, amount in ptet_by_state.items() if paid.get(s, ZERO) < amount]
