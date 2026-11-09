"""K-1 treatments' arithmetic (T-04-T11; T-04 §4.4, AC-6.3, AC-7.2; DEC-3124).

Feld 2025 goldens (Ridgeline Property Partners, LP): QBI 20% x 307,900 = 61,580 <
max(50% x W-2, 25% x W-2 + 2.5% x 3,938,000) = 98,450; outside basis 1,912,500 + 2,762,075 =
4,674,575; box 2 sourced by property % IL 46.0 / CO 31.5 / NY 22.5 → 141,634 + 96,989 + 69,277 =
307,900 (largest remainder); PTET 25% of 28,044 + 17,070 + 18,982 → 7,011 + 4,268 + 4,746 = 16,025
(each share half up).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from abacus.kernel.numeric import allocate
from abacus.modules.tax.compute.individual.engine import Stamp, pct, section, stamp, whole


@dataclass(frozen=True)
class Qbi:
    tentative: Decimal  # 20% of QBI
    limit: Decimal  # the wage and UBIA limit
    deduction: Decimal
    below_limit: bool
    stamp: Stamp


def qbi_199a(qbi: Decimal, w2_wages: Decimal, ubia: Decimal, tax_year: int) -> Qbi:
    p = section(tax_year, "qbi_199a")
    tentative = whole(qbi * pct(str(p["deduction_pct"])))
    limit = whole(
        max(
            w2_wages * pct(str(p["w2_wage_pct"])),
            w2_wages * pct(str(p["w2_wage_alt_pct"])) + ubia * pct(str(p["ubia_pct"])),
        )
    )
    inputs = {"qbi": qbi, "w2_wages": w2_wages, "ubia": ubia, "tax_year": tax_year}
    return Qbi(
        tentative, limit, min(tentative, limit), tentative < limit, stamp("k1.qbi_199a", inputs)
    )


@dataclass(frozen=True)
class OutsideBasis:
    total: Decimal
    stamp: Stamp


def outside_basis(tax_capital: Decimal, liability_share_752: Decimal) -> OutsideBasis:
    inputs = {"tax_capital": tax_capital, "s752": liability_share_752}
    return OutsideBasis(tax_capital + liability_share_752, stamp("k1.outside_basis", inputs))


@dataclass(frozen=True)
class Sourcing:
    shares: tuple[tuple[str, Decimal], ...]
    stamp: Stamp


def state_sourcing(amount: Decimal, by_state: Sequence[tuple[str, Decimal]]) -> Sourcing:
    """Whole dollars by property percentage, footing exactly (largest remainder)."""
    shares = allocate(amount, [w for _, w in by_state], places=0)
    inputs = {"amount": amount, "by_state": [[s, w] for s, w in by_state]}
    return Sourcing(
        tuple((s, v) for (s, _), v in zip(by_state, shares, strict=True)),
        stamp("k1.state_sourcing", inputs),
    )


@dataclass(frozen=True)
class PtetShares:
    shares: tuple[tuple[str, Decimal], ...]
    total: Decimal
    stamp: Stamp


def ptet_share(entity_ptet: Sequence[tuple[str, Decimal]], tax_year: int) -> PtetShares:
    """The partner's share of each entity PTET, each half up (the per-partner override)."""
    share = pct(str(section(tax_year, "ptet")["partner_share_pct"]))
    shares = tuple((state, whole(v * share)) for state, v in entity_ptet)
    inputs = {"entity": [[s, v] for s, v in entity_ptet], "tax_year": tax_year}
    return PtetShares(
        shares, sum((v for _, v in shares), Decimal(0)), stamp("k1.ptet_share", inputs)
    )
