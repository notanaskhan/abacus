"""State residency and allocation (T-04-T11; T-04 §4.4, AC-8.2; DEC-3124).

Feld 2025 goldens: allocation 268,400 + 6,910 + 14,820 + 307,900 = 598,030; IT-112-R
min(11,279, 41,070 x 238,623 / 615,605 = 15,920) = 11,279 (NYC takes no other-state credit);
IT-225 add-backs 4,746 + 11,279 = 16,025; residency 281 NYC days with a NYC abode → full-year NYS
and NYC; 150 days with Rhinebeck as the main home → a conflict for a person to resolve.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

from abacus.modules.tax.compute.individual.engine import Stamp, parameter_table, stamp, whole

ResidencyOption = Literal["full_year_nys_nyc", "full_year_nys_part_year_nyc", "part_year_nys"]


@dataclass(frozen=True)
class Total:
    total: Decimal
    stamp: Stamp


def allocation(parts: Sequence[Decimal]) -> Total:
    """The federal amounts the state return starts from."""
    return Total(sum(parts, Decimal(0)), stamp("residency.allocation", {"parts": list(parts)}))


@dataclass(frozen=True)
class OtherStateCredit:
    limit: Decimal
    credit: Decimal
    stamp: Stamp


def it112r(
    other_state_tax: Decimal, ny_tax: Decimal, other_state_income: Decimal, ny_agi: Decimal
) -> OtherStateCredit:
    """The lesser of the other state's tax and NY tax x (other-state income / NY AGI)."""
    if ny_agi <= 0:
        raise ValueError("NY AGI must be positive")
    limit = whole(ny_tax * other_state_income / ny_agi)
    inputs = {
        "other_state_tax": other_state_tax,
        "ny_tax": ny_tax,
        "other_state_income": other_state_income,
        "ny_agi": ny_agi,
    }
    return OtherStateCredit(limit, min(other_state_tax, limit), stamp("residency.it112r", inputs))


def it225(addbacks: Sequence[Decimal]) -> Total:
    return Total(sum(addbacks, Decimal(0)), stamp("residency.it225", {"addbacks": list(addbacks)}))


@dataclass(frozen=True)
class ResidencyFacts:
    nyc_days: int
    has_nyc_abode: bool
    main_home_outside_nyc: bool


@dataclass(frozen=True)
class ResidencyCall:
    recommended: ResidencyOption
    conflict: bool
    stamp: Stamp


def residency_rules(facts: ResidencyFacts, tax_year: int) -> ResidencyCall:
    """Code's recommendation only; a person confirms (ADR-005). More than the statutory days with
    an abode is full-year; fewer, with the main home elsewhere, conflicts with a full-year call."""
    days = int(str(parameter_table(tax_year, "residency")["statutory_days"]))
    statutory = facts.nyc_days > days and facts.has_nyc_abode
    inputs = {"facts": facts.__dict__, "tax_year": tax_year}
    if statutory:
        return ResidencyCall("full_year_nys_nyc", False, stamp("residency.rules", inputs))
    return ResidencyCall(
        "full_year_nys_part_year_nyc",
        facts.main_home_outside_nyc,
        stamp("residency.rules", inputs),
    )
