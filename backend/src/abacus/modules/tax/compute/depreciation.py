"""E3: the depreciation engine (T-06-T13; T-06 §3 F1; SPEC-702 AC-1, AC-2, AC-4, AC-6; DEC-77,
ADR-050). Pure and `Decimal` only: no I/O beyond the protected parameter files, no model.

MACRS GDS (IRC §168; Rev. Proc. 87-57) computed by formula, which equals the published tables up
to their three-decimal rounding:

- **Methods.** `SL` over the recovery period; `200DB` and `150DB` switching to straight line on
  the remaining basis in the first year SL gives at least as much (§168(b)(1)).
- **Conventions.** `MM` mid-month (real property), `HY` half-year, `MQ` mid-quarter. The
  mid-quarter test (§168(d)(3)): more than 40% of the year's aggregate depreciable basis of
  personal property placed in service in the fourth quarter puts every such asset of that year
  on `MQ`.
- **Bonus** (§168(k)): the elected percentage on cost less §179; eligibility by the acquisition
  date or the written binding contract date (after Jan 19, 2025: 100%). Without a cited date the
  check stays `check`: the engine never infers a date (INV-2).
- **§179** limit and phase-out; the **§163(j)** small-business test.
- **Rounding.** Each figure is exact; the register rounds every column to whole dollars by the
  largest remainder (DEC-77), so the rounded rows foot to the rounded total.
- **Ties.** Accumulated to TB 1650, expense to TB 5600, cost to TB 1600 and Form 8825 by
  property; **recapture** classes for dispositions (§1245, unrecaptured §1250).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from decimal import ROUND_FLOOR, Decimal
from functools import cache
from pathlib import Path
from typing import Final, Literal, cast

import yaml

ZERO: Final = Decimal("0")
ONE: Final = Decimal("1")
TWELVE: Final = Decimal("12")
_DIR: Final = Path(__file__).parent / "parameters" / "depreciation"
ENGINE_VERSION: Final = "e3.1"

Method = Literal["SL", "200DB", "150DB"]
Convention = Literal["MM", "HY", "MQ"]
BonusCheck = Literal["tie", "check", "not_eligible"]
Recapture = Literal["section_1245", "section_1250", "none"]
# Recovery periods in years; 27.5 and 39 are real property (mid-month, straight line only).
RecoveryClass = Literal["3", "5", "7", "10", "15", "20", "27.5", "39"]
REAL_PROPERTY: Final = frozenset({"27.5", "39"})
_MQ_FRACTION: Final = {
    1: Decimal("0.875"),
    2: Decimal("0.625"),
    3: Decimal("0.375"),
    4: Decimal("0.125"),
}


class ParameterMissing(LookupError):
    """A parameter the computation needs is not published or not yet reviewed for that year."""


@dataclass(frozen=True, slots=True)
class Parameters:
    tax_year: int
    bonus_full_after: date
    bonus_full_pct: Decimal
    bonus_phase_down_pct: Decimal
    section_179_limit: Decimal | None
    section_179_phase_out: Decimal | None
    small_business_gross_receipts: Decimal | None
    reviewed_by: str | None


def _dec(value: object) -> Decimal | None:
    return None if value is None else Decimal(str(value))


@cache
def parameters(tax_year: int) -> Parameters:
    """`parameters/depreciation/ty<tax_year>.yaml` (PROTECTED); a missing year raises."""
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.exists():
        raise ParameterMissing(f"depreciation parameters: ty{tax_year}")
    raw = cast(dict[str, object], yaml.safe_load(path.read_text("utf-8")))
    bonus = cast(dict[str, object], raw["bonus"])
    s179 = cast(dict[str, object], raw["section_179"])
    return Parameters(
        tax_year=int(cast(int, raw["tax_year"])),
        bonus_full_after=date.fromisoformat(str(bonus["full_after"])),
        bonus_full_pct=Decimal(str(bonus["full_pct"])),
        bonus_phase_down_pct=Decimal(str(bonus["phase_down_pct"])),
        section_179_limit=_dec(s179.get("limit")),
        section_179_phase_out=_dec(s179.get("phase_out_threshold")),
        small_business_gross_receipts=_dec(raw.get("small_business_gross_receipts")),
        reviewed_by=cast(str | None, raw.get("reviewed_by")),
    )


@dataclass(frozen=True, slots=True)
class Asset:
    asset_id: str
    property_key: str  # the Form 8825 property ("elm_street")
    placed_in_service: date
    cost: Decimal
    recovery_class: RecoveryClass
    method: Method
    convention: Convention
    bonus_pct: Decimal = ZERO  # the elected percentage (0 to 100)
    section_179: Decimal = ZERO
    acquired_on: date | None = None
    binding_contract_on: date | None = None  # a cited contract date (C4), never inferred

    def __post_init__(self) -> None:
        if self.cost < ZERO or self.section_179 < ZERO or self.section_179 > self.cost:
            raise ValueError(f"{self.asset_id}: cost and §179 must be 0 <= §179 <= cost")
        if not ZERO <= self.bonus_pct <= Decimal("100"):
            raise ValueError(f"{self.asset_id}: bonus is a percentage")
        if self.recovery_class in REAL_PROPERTY and (
            self.method != "SL" or self.convention != "MM"
        ):
            raise ValueError(f"{self.asset_id}: real property is straight line, mid-month")
        if self.recovery_class not in REAL_PROPERTY and self.convention == "MM":
            raise ValueError(f"{self.asset_id}: mid-month is for real property only")


@dataclass(frozen=True, slots=True)
class Row:
    """One asset's year, exact (unrounded)."""

    asset_id: str
    property_key: str
    cost: Decimal
    prior: Decimal  # accumulated before the year
    current: Decimal  # the year's depreciation, bonus and §179 included
    bonus: Decimal
    section_179: Decimal

    @property
    def accumulated(self) -> Decimal:
        return self.prior + self.current


@dataclass(frozen=True, slots=True)
class RoundedRow:
    asset_id: str
    property_key: str
    cost: int
    prior: int
    current: int
    accumulated: int


@dataclass(frozen=True, slots=True)
class Register:
    tax_year: int
    rows: tuple[RoundedRow, ...]
    cost: int
    prior: int
    current: int
    accumulated: int
    by_property: Mapping[str, int] = field(default_factory=dict[str, int])
    engine_version: str = ENGINE_VERSION

    def crossfoots(self) -> bool:
        return (
            all(r.prior + r.current == r.accumulated for r in self.rows)
            and sum(r.cost for r in self.rows) == self.cost
            and sum(r.prior for r in self.rows) == self.prior
            and sum(r.current for r in self.rows) == self.current
            and self.prior + self.current == self.accumulated
            and sum(self.by_property.values()) == self.current
        )


# --- conventions -----------------------------------------------------------------------------


def _quarter(day: date) -> int:
    return (day.month - 1) // 3 + 1


def mid_quarter_applies(assets: Iterable[Asset], tax_year: int) -> bool:
    """§168(d)(3): over 40% of the year's personal-property basis (after §179) placed in service
    in the fourth quarter. Real property and assets of other years do not count."""
    placed = [
        a
        for a in assets
        if a.placed_in_service.year == tax_year and a.recovery_class not in REAL_PROPERTY
    ]
    total = sum((a.cost - a.section_179 for a in placed), ZERO)
    if total == ZERO:
        return False
    q4 = sum((a.cost - a.section_179 for a in placed if _quarter(a.placed_in_service) == 4), ZERO)
    return q4 * Decimal("100") > total * Decimal("40")


def _first_year_fraction(asset: Asset, convention: Convention) -> Decimal:
    if convention == "MM":
        return (TWELVE - asset.placed_in_service.month + Decimal("0.5")) / TWELVE
    if convention == "HY":
        return Decimal("0.5")
    return _MQ_FRACTION[_quarter(asset.placed_in_service)]


# --- schedules -------------------------------------------------------------------------------


def _life(asset: Asset) -> Decimal:
    return Decimal(asset.recovery_class)


def regular_schedule(asset: Asset, convention: Convention, basis: Decimal) -> list[Decimal]:
    """Year-by-year depreciation of `basis` from the placed-in-service year (index 0) to the
    end of recovery; the amounts sum to `basis` exactly."""
    if basis == ZERO:
        return []
    life = _life(asset)
    first = _first_year_fraction(asset, convention)
    out: list[Decimal] = []
    remaining = basis
    if asset.method == "SL":
        annual = basis / life
        amount = annual * first
        out.append(amount)
        remaining -= amount
        while remaining > ZERO:
            amount = min(annual, remaining)
            out.append(amount)
            remaining -= amount
        return out
    factor = Decimal("2") if asset.method == "200DB" else Decimal("1.5")
    rate = factor / life
    years_left = life  # remaining recovery period at the start of each year, in years
    portion = first
    # The last year's straight line (remaining over the fraction of a year left) is at least the
    # remaining basis, so the loop ends with the basis recovered exactly.
    while remaining > ZERO:
        db = remaining * rate * portion
        # In the last (part) year straight line takes the rest; a Decimal residue never divides
        # by a spent recovery period.
        sl = remaining if years_left <= portion else remaining / years_left * portion
        amount = min(remaining, max(db, sl))
        out.append(amount)
        remaining -= amount
        years_left -= portion
        portion = max(min(ONE, years_left), ZERO)
    return out


def bonus_rate(asset: Asset, params: Parameters) -> Decimal:
    """The rate the asset's dates allow (§168(k)); real property takes none."""
    if asset.recovery_class in REAL_PROPERTY:
        return ZERO
    acquired = asset.binding_contract_on or asset.acquired_on
    if acquired is not None and acquired > params.bonus_full_after:
        return params.bonus_full_pct
    return params.bonus_phase_down_pct


def bonus_check(asset: Asset, params: Parameters) -> BonusCheck:
    """TXP-03's Bonus eligibility tally for one asset: `tie` when the elected bonus is what the
    cited dates allow, `check` when the dates cannot show it (a full-rate election with no cited
    acquisition or binding-contract date after the cut-off)."""
    if asset.recovery_class in REAL_PROPERTY:
        return "not_eligible" if asset.bonus_pct > ZERO else "tie"
    if asset.bonus_pct == ZERO:
        return "tie"
    dated = asset.binding_contract_on or asset.acquired_on
    if dated is None:
        return "check"
    return "tie" if asset.bonus_pct <= bonus_rate(asset, params) else "check"


def year_row(asset: Asset, tax_year: int, *, mid_quarter: bool = False) -> Row:
    """The asset's row for `tax_year`: prior accumulated and the year's depreciation, exact."""
    convention: Convention = (
        "MQ" if mid_quarter and asset.recovery_class not in REAL_PROPERTY else asset.convention
    )
    depreciable = asset.cost - asset.section_179
    bonus = depreciable * asset.bonus_pct / Decimal("100")
    schedule = regular_schedule(asset, convention, depreciable - bonus)
    first_year = asset.placed_in_service.year
    by_year = {first_year + i: amount for i, amount in enumerate(schedule)}
    by_year[first_year] = by_year.get(first_year, ZERO) + bonus + asset.section_179
    prior = sum((v for y, v in by_year.items() if y < tax_year), ZERO)
    current = by_year.get(tax_year, ZERO)
    return Row(
        asset_id=asset.asset_id,
        property_key=asset.property_key,
        cost=asset.cost,
        prior=prior,
        current=current,
        bonus=bonus if first_year == tax_year else ZERO,
        section_179=asset.section_179 if first_year == tax_year else ZERO,
    )


# --- rounding ----------------------------------------------------------------------------------


def largest_remainder(values: Sequence[Decimal]) -> list[int]:
    """Whole dollars that sum to the rounded total: floor each, then give the leftover dollars
    to the largest fractional parts (ties to the earlier row)."""
    floors = [int(v.to_integral_value(rounding=ROUND_FLOOR)) for v in values]
    total = int(sum(values, ZERO).to_integral_value())  # ROUND_HALF_EVEN on the exact total
    left = total - sum(floors)
    order = sorted(range(len(values)), key=lambda i: (-(values[i] - floors[i]), i))
    out = list(floors)
    for i in order[: max(left, 0)]:
        out[i] += 1
    return out


def register(assets: Sequence[Asset], tax_year: int) -> Register:
    """The register for `tax_year` (TXP-03 a and b): rows, totals and Form 8825 by property."""
    mq = mid_quarter_applies(assets, tax_year)
    rows = [year_row(a, tax_year, mid_quarter=mq) for a in assets]
    cost = largest_remainder([r.cost for r in rows])
    prior = largest_remainder([r.prior for r in rows])
    current = largest_remainder([r.current for r in rows])
    rounded = tuple(
        RoundedRow(
            r.asset_id, r.property_key, cost[i], prior[i], current[i], prior[i] + current[i]
        )
        for i, r in enumerate(rows)
    )
    by_property: dict[str, int] = {}
    for row in rounded:
        by_property[row.property_key] = by_property.get(row.property_key, 0) + row.current
    return Register(
        tax_year=tax_year,
        rows=rounded,
        cost=sum(cost),
        prior=sum(prior),
        current=sum(current),
        accumulated=sum(prior) + sum(current),
        by_property=by_property,
    )


@dataclass(frozen=True, slots=True)
class Ties:
    """TXP-03's Ties to TB tally: cost to 1600, accumulated to 1650, expense to 5600."""

    cost: bool
    accumulated: bool
    expense: bool

    @property
    def tie(self) -> bool:
        return self.cost and self.accumulated and self.expense


def ties(reg: Register, tb: Mapping[str, int]) -> Ties:
    return Ties(
        cost=tb.get("1600") == reg.cost,
        accumulated=tb.get("1650") == reg.accumulated,
        expense=tb.get("5600") == reg.current,
    )


# --- §179, §163(j), recapture --------------------------------------------------------------------


def section_179_allowed(
    placed_in_service_cost: Decimal, elected: Decimal, params: Parameters
) -> Decimal:
    """§179(b)(1)-(2): the elected amount up to the limit, reduced dollar for dollar by cost over
    the phase-out threshold (the taxable-income limit is the engine's, DEC-77)."""
    if params.section_179_limit is None or params.section_179_phase_out is None:
        raise ParameterMissing(f"§179 for ty{params.tax_year}")
    reduction = max(placed_in_service_cost - params.section_179_phase_out, ZERO)
    limit = max(params.section_179_limit - reduction, ZERO)
    return min(elected, limit)


def small_business_exempt(prior_gross_receipts: Sequence[Decimal], params: Parameters) -> bool:
    """§163(j)(3): average annual gross receipts of the three prior years at or under the
    §448(c) threshold. Fewer than three years average the years there are."""
    if params.small_business_gross_receipts is None:
        raise ParameterMissing(f"§163(j) threshold for ty{params.tax_year}")
    years = list(prior_gross_receipts)[-3:]
    if not years:
        return True
    return sum(years, ZERO) / Decimal(len(years)) <= params.small_business_gross_receipts


def recapture_class(recovery_class: RecoveryClass) -> Recapture:
    """§1245 for personal property and land improvements; §1250 (unrecaptured gain) for real
    property placed in service after 1986 on straight line."""
    return "section_1250" if recovery_class in REAL_PROPERTY else "section_1245"
