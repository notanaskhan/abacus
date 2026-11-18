"""E8: the basis and section 752 engine (T-06-T16; T-06 §3 F3; SPEC-702; DEC-77, ADR-050). Pure,
`Decimal` only, no I/O and no model.

- **Section 752 shares**: nonrecourse and qualified nonrecourse liabilities are shared by
  year-end profit percentage (Treas. Reg. 1.752-3(a)(3)), split to whole dollars by largest
  remainder (`kernel.numeric.allocate`), so the shares foot exactly to the liabilities.
- **Deemed distributions**: a decrease in a partner's share is a section 752(b) deemed
  distribution (a basis decrease); an increase is a 752(a) deemed contribution.
- **Outside basis** = beginning + increases - decreases, never below zero; **inside share** = tax
  capital + section 752 share. A partner who bought an interest carries the purchase premium
  (price paid - capital acquired) in outside basis only: the section 743(b) placeholder, pending
  a section 754 election, which is the difference between the two.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Final, Literal

from abacus.kernel.numeric import allocate

ZERO: Final = Decimal("0")
ENGINE_VERSION: Final = "e8.1"
Tally = Literal["reconciled", "off"]


def liability_shares(total: Decimal, profit_pct: Mapping[str, Decimal]) -> dict[str, Decimal]:
    """Each partner's section 752 share of `total` by year-end profit percentage."""
    names = list(profit_pct)
    shares = allocate(total, [profit_pct[n] for n in names], places=0)
    return dict(zip(names, shares, strict=True))


@dataclass(frozen=True, slots=True)
class BasisRoll:
    beginning: Decimal
    increases: Decimal
    decreases: Decimal
    ending: Decimal


def roll(
    beginning: Decimal, increases: Sequence[Decimal], decreases: Sequence[Decimal]
) -> BasisRoll:
    up = sum(increases, ZERO)
    down = sum(decreases, ZERO)
    return BasisRoll(beginning, up, down, max(beginning + up - down, ZERO))


def deemed(prior_share: Decimal, current_share: Decimal) -> tuple[Decimal, Decimal]:
    """(752(a) contribution, 752(b) distribution) from the change in a partner's share."""
    change = current_share - prior_share
    return (change, ZERO) if change >= ZERO else (ZERO, -change)


@dataclass(frozen=True, slots=True)
class PartnerBasis:
    partner: str
    tax_capital: Decimal
    s752_share: Decimal
    outside: Decimal
    inside: Decimal
    difference: Decimal
    tally: Tally


def partner_basis(
    partner: str, *, tax_capital: Decimal, s752_share: Decimal, outside: Decimal
) -> PartnerBasis:
    inside = tax_capital + s752_share
    diff = outside - inside
    return PartnerBasis(
        partner,
        tax_capital,
        s752_share,
        outside,
        inside,
        diff,
        "reconciled" if diff == ZERO else "off",
    )


def s743b_placeholder(price_paid: Decimal, capital_acquired: Decimal) -> Decimal:
    """The purchase premium carried in outside basis only, pending a section 754 election."""
    return price_paid - capital_acquired
