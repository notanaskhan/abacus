"""Planning savings calculators (T-08-T19; TAX-15; ADR-050: code computes, the model never does).

Each calculator is a pure function of the return's figures and the CPA-reviewed parameter file
(`tax/compute/parameters/planning/ty<year>.yaml`, PROTECTED), returning the estimate and its
basis: the calculator, the input lines it read (by reference: engine summary keys) and the
parameter version, which `planning_opportunities.savings_basis` keeps so the figure can be
recomputed and traced. Amounts are `Decimal`, whole dollars, half up.

The donor-advised-fund bunching estimate (TAX-15 a, the Felds):

    floor      = 0.5% * AGI                                   = 0.5% * 598,030 = 2,990
    without    = SALT + mortgage interest                     = 10,591 + 18,240 = 28,831
    unbunched  = 2 * max(standard, without + gifts - floor)   = 2 * 38,341 = 76,682
    bunched    = max(standard, without + 2 * gifts - floor) + max(standard, without)
               = 50,841 + 31,500 = 82,341
    savings    = (bunched - unbunched) * marginal rate        = 5,659 * 32% = 1,811
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Final, Literal, cast

import yaml

ZERO: Final = Decimal(0)
HUNDRED: Final = Decimal(100)
_DIR: Final = Path(__file__).resolve().parents[1] / "compute" / "parameters" / "planning"
FilingStatus = Literal["mfj", "single", "hoh", "mfs"]


def whole(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("1"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Parameters:
    tax_year: int
    version: int
    planning_years: tuple[int, ...]
    reviewed_by: str | None
    standard_deduction: Mapping[str, Decimal]
    brackets: Mapping[str, tuple[tuple[Decimal | None, Decimal], ...]]
    sections: Mapping[str, Mapping[str, Decimal]]

    @property
    def version_ref(self) -> str:
        """`planning_screens.rules_version` and the basis's pin: `ty2025.v1`."""
        return f"ty{self.tax_year}.v{self.version}"

    def get(self, section: str, key: str) -> Decimal:
        return self.sections[section][key]


@cache
def parameters(tax_year: int) -> Parameters:
    """`parameters/planning/ty<tax_year>.yaml` (PROTECTED); a missing year raises LookupError."""
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.is_file():
        raise LookupError(f"planning parameters: ty{tax_year}")
    raw = cast(dict[str, object], yaml.safe_load(path.read_text("utf-8")))
    brackets = {
        status: tuple(
            (None if top is None else Decimal(str(top)), Decimal(str(rate))) for top, rate in rows
        )
        for status, rows in cast(dict[str, list[list[object]]], raw["brackets"]).items()
    }
    skip = {"version", "tax_year", "planning_years", "reviewed_by", "source"}
    skip |= {"standard_deduction", "brackets"}
    sections = {
        name: {k: Decimal(str(v)) for k, v in cast(dict[str, object], body).items()}
        for name, body in raw.items()
        if name not in skip
    }
    return Parameters(
        tax_year=int(cast(int, raw["tax_year"])),
        version=int(cast(int, raw["version"])),
        planning_years=tuple(int(y) for y in cast(list[int], raw["planning_years"])),
        reviewed_by=cast("str | None", raw.get("reviewed_by")),
        standard_deduction={
            k: Decimal(str(v))
            for k, v in cast(dict[str, object], raw["standard_deduction"]).items()
        },
        brackets=brackets,
        sections=sections,
    )


def marginal_rate(taxable_income: Decimal, status: FilingStatus, params: Parameters) -> Decimal:
    """The rate (percent) of the bracket the taxable income falls in."""
    for top, rate in params.brackets[status]:
        if top is None or taxable_income <= top:
            return rate
    return params.brackets[status][-1][1]


def bracket_room(taxable_income: Decimal, status: FilingStatus, params: Parameters) -> Decimal:
    """Taxable income left before the next bracket (zero in the top bracket)."""
    for top, _rate in params.brackets[status]:
        if top is None:
            return ZERO
        if taxable_income <= top:
            return top - taxable_income
    return ZERO


@dataclass(frozen=True)
class Estimate:
    calculator: str
    savings: Decimal | None  # None: a risk-reduction or eligibility item, no estimate
    inputs: Mapping[str, str]  # engine summary key -> the value read (decimal strings)
    figures: Mapping[str, str] = field(default_factory=dict[str, str])  # code's steps, by name
    parameter_version: str = ""

    def basis(self) -> dict[str, object]:
        """`savings_basis` (jsonb): calculator, inputs by reference, parameter version."""
        return {
            "calculator": self.calculator,
            "inputs": dict(sorted(self.inputs.items())),
            "figures": dict(sorted(self.figures.items())),
            "parameter_version": self.parameter_version,
        }


def _s(amount: Decimal) -> str:
    return format(amount, "f")


def daf_bunching(
    *,
    agi: Decimal,
    salt: Decimal,
    mortgage_interest: Decimal,
    annual_gifts: Decimal,
    rate_pct: Decimal,
    status: FilingStatus,
    params: Parameters,
) -> Estimate:
    """Two years of gifts given in the first through a donor-advised fund (module docstring)."""
    standard = params.standard_deduction[status]
    years = int(params.get("daf_bunching", "years"))
    floor = whole(agi * params.get("daf_bunching", "floor_pct") / HUNDRED)
    without = salt + mortgage_interest
    yearly = max(standard, max(without + annual_gifts - floor, without))
    unbunched = years * yearly
    first = max(standard, max(without + years * annual_gifts - floor, without))
    bunched = first + (years - 1) * max(standard, without)
    difference = bunched - unbunched
    savings = whole(max(difference, ZERO) * rate_pct / HUNDRED)
    return Estimate(
        "daf_bunching",
        savings,
        {"1040.11": _s(agi), "scha.5e": _s(salt), "scha.8a": _s(mortgage_interest),
         "scha.11": _s(annual_gifts)},
        {"floor": _s(floor), "without_gifts": _s(without), "standard": _s(standard),
         "unbunched": _s(unbunched), "bunched": _s(bunched), "difference": _s(difference),
         "rate_pct": _s(rate_pct)},
        params.version_ref,
    )  # fmt: skip


def deferral_savings(
    calculator: str,
    *,
    amount: Decimal,
    rate_pct: Decimal,
    inputs: Mapping[str, str],
    params: Parameters,
) -> Estimate:
    """A deduction or exclusion of `amount` at the marginal rate (solo 401(k), dependent care)."""
    return Estimate(
        calculator,
        whole(amount * rate_pct / HUNDRED),
        inputs,
        {"amount": _s(amount), "rate_pct": _s(rate_pct)},
        params.version_ref,
    )


def no_estimate(calculator: str, inputs: Mapping[str, str], params: Parameters) -> Estimate:
    return Estimate(calculator, None, inputs, {}, params.version_ref)


__all__ = [
    "Estimate",
    "FilingStatus",
    "Parameters",
    "bracket_room",
    "daf_bunching",
    "deferral_savings",
    "marginal_rate",
    "no_estimate",
    "parameters",
    "whole",
]
