"""E11: the ASC 740 provision engine (T-06-T25; TASK-8720; T-06 §3 F5; SPEC-702; DEC-77, ADR-050).
Pure, `Decimal` only, no I/O and no model.

- **Provision** = current tax + deferred tax.
- **Blended state rate net of federal benefit** = state rate x (1 - federal rate).
- **Rate reconciliation**: the statutory federal rate on pretax income, the state rate net of the
  federal benefit, then each permanent difference and credit at its own amount; the reconciled
  total must tie to the provision. What does not tie is the **unclassified difference** (never
  plugged): an exception the screen offers to explain.
- **Effective tax rate** = provision / pretax income, to one place (half up).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Final

ZERO: Final = Decimal("0")
ENGINE_VERSION: Final = "e11.1"
CENT: Final = Decimal("0.01")
ONE: Final = Decimal("0.1")


def blended_state_rate(state_rate: Decimal, federal_rate: Decimal) -> Decimal:
    return state_rate * (1 - federal_rate)


@dataclass(frozen=True, slots=True)
class Reconciliation:
    statutory: Decimal
    state_net: Decimal
    items: Mapping[str, Decimal]
    reconciled_total: Decimal
    provision: Decimal
    unclassified: Decimal
    etr_pct: Decimal

    @property
    def ties(self) -> bool:
        return self.unclassified == ZERO


def provision(current: Decimal, deferred: Decimal) -> Decimal:
    return current + deferred


def reconcile(
    pretax: Decimal,
    *,
    current: Decimal,
    deferred: Decimal,
    federal_rate: Decimal,
    state_rate: Decimal,
    items: Mapping[str, Decimal],
) -> Reconciliation:
    total = provision(current, deferred)
    statutory = (pretax * federal_rate).quantize(CENT, ROUND_HALF_UP)
    state_net = (pretax * blended_state_rate(state_rate, federal_rate)).quantize(
        CENT, ROUND_HALF_UP
    )
    reconciled = statutory + state_net + sum(items.values(), ZERO)
    etr = (total * 100 / pretax).quantize(ONE, ROUND_HALF_UP)
    return Reconciliation(
        statutory, state_net, dict(items), reconciled, total, total - reconciled, etr
    )


__all__ = ["ENGINE_VERSION", "Reconciliation", "blended_state_rate", "provision", "reconcile"]
