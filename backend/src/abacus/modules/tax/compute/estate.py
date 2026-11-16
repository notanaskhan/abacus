"""The estate engine (T-07-T22; TASK-8079; T-07 §3.7; SPEC-656 AC-12.1 to AC-13.5; ADR-050,
DEC-77).

Pure: `Decimal` in, `Decimal` out; no I/O but the parameter file, no clock. The Form 706 workpaper
the firm reviews on TXT-04; every figure is labelled "Accrued tie-out (shadow)" until a CCH 706
import exists (DEC-77), because the engine of record computes the return.

1. **Gross estate**: the inventory at date-of-death values; at alternate values (§2032) where the
   asset has one; and the **basis to the estate's 1041**: the stepped-up assets only (§1014) —
   income in respect of a decedent (IRD) gets no step-up and non-probate life insurance is not
   the estate's, so both are null by rule, never by entry.
2. **Taxable estate**: gross estate less the deductions (Schedules J, K, L, M, O).
3. **Adjusted taxable gifts**: each post-1976 gift less the year's annual exclusion (§2503(b)).
4. **Tentative tax** (§2001(c)) on the taxable estate plus adjusted taxable gifts.
5. **Credit**: the tentative tax on the applicable exclusion amount, the basic exclusion amount
   plus the DSUE carried in (§2010(c)); net estate tax = max(0, tentative - credit). The
   Without-DSUE scenario computes the credit on the BEA alone.
6. **Filing requirement**: gross estate plus adjusted taxable gifts over the BEA (§6018).
7. **Alternate valuation** (§2032(c)) is available only when it lowers both the gross estate and
   the tax; with no tax due it is not (AC-13.2).
8. **State**: a residence state with an exclusion flags whether its return is required; the
   engine never computes the state figure (AC-13.3).

Thornbury: 16,400,000 / 15,993,000 / 12,688,000; deductions 900,000; taxable 15,500,000; gifts
1,200,000; tentative 6,625,800 (345,800 + 40% x 15,700,000); credit on 18,000,000 = 7,145,800;
net tax 0; without DSUE credit 5,945,800 and tax 680,000; 17,600,000 > 15,000,000.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from decimal import ROUND_HALF_UP, Decimal
from functools import cache
from pathlib import Path
from typing import Final, Literal, cast

import yaml

ENGINE_NAME: Final = "tax.estate"
ENGINE_VERSION: Final = "1.0.0"
ZERO: Final = Decimal("0.00")
_CENT: Final = Decimal("0.01")
_DIR: Final = Path(__file__).parent / "parameters" / "estate"

BasisRule = Literal["stepped_up", "ird_no_step_up", "non_probate_excluded"]


def _c(value: Decimal) -> Decimal:
    return value.quantize(_CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True, slots=True)
class Asset:
    key: str
    schedule: str
    dod_value: Decimal
    avd_value: Decimal | None
    basis_rule: BasisRule


@dataclass(frozen=True, slots=True)
class Deduction:
    key: str
    schedule: str
    amount: Decimal


@dataclass(frozen=True, slots=True)
class Gift:
    key: str
    year: int
    amount: Decimal


@dataclass(frozen=True, slots=True)
class EstateInputs:
    tax_year: int
    assets: tuple[Asset, ...]
    deductions: tuple[Deduction, ...] = ()
    gifts: tuple[Gift, ...] = ()
    dsue: Decimal = ZERO
    residence_state: str | None = None
    elect_avd: bool = False


@dataclass(frozen=True, slots=True)
class EstateParameters:
    tax_year: int
    version: int
    bea: Decimal
    schedule: tuple[tuple[Decimal, Decimal, Decimal], ...]
    annual_exclusion: dict[int, Decimal]
    state_exclusions: dict[str, Decimal]
    filing_months: int
    extension_months: int


@cache
def parameters(tax_year: int) -> EstateParameters:
    """`parameters/estate/ty<tax_year>.yaml` (PROTECTED); a missing year raises LookupError."""
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.is_file():
        raise LookupError(f"estate parameters: ty{tax_year}")
    raw = cast(dict[str, object], yaml.safe_load(path.read_text("utf-8")))
    rows = cast(list[list[str]], raw["rate_schedule"])
    return EstateParameters(
        tax_year=int(cast(int, raw["tax_year"])),
        version=int(cast(int, raw["version"])),
        bea=Decimal(str(raw["basic_exclusion_amount"])),
        schedule=tuple((Decimal(a), Decimal(b), Decimal(c)) for a, b, c in rows),
        annual_exclusion={
            int(k): Decimal(str(v))
            for k, v in cast(dict[str, str], raw["annual_exclusion"]).items()
        },
        state_exclusions={
            k: Decimal(str(v)) for k, v in cast(dict[str, str], raw["state_exclusions"]).items()
        },
        filing_months=int(cast(int, raw["filing_months"])),
        extension_months=int(cast(int, raw["extension_months"])),
    )


def tentative_tax(amount: Decimal, params: EstateParameters) -> Decimal:
    """§2001(c): the bracket's base tax plus its rate on the amount over its floor."""
    if amount <= 0:
        return ZERO
    over, base, rate = next(row for row in reversed(params.schedule) if amount > row[0])
    return _c(base + (amount - over) * rate / 100)


def annual_exclusion(year: int, params: EstateParameters) -> Decimal:
    known = sorted(params.annual_exclusion)
    if year in params.annual_exclusion:
        return params.annual_exclusion[year]
    return params.annual_exclusion[known[0] if year < known[0] else known[-1]]


@dataclass(frozen=True, slots=True)
class GiftLine:
    key: str
    year: int
    amount: Decimal
    exclusion: Decimal
    taxable: Decimal


@dataclass(frozen=True, slots=True)
class EstateResult:
    gross_estate_dod: Decimal
    gross_estate_avd: Decimal
    basis_to_1041: Decimal
    deductions: Decimal
    taxable_estate: Decimal
    gifts: tuple[GiftLine, ...]
    adjusted_taxable_gifts: Decimal
    tentative_tax_base: Decimal
    tentative_tax: Decimal
    bea: Decimal
    dsue: Decimal
    applicable_exclusion: Decimal
    credit: Decimal
    net_tax: Decimal
    credit_without_dsue: Decimal
    tax_without_dsue: Decimal
    filing_threshold_amount: Decimal
    filing_required: bool
    avd_available: bool
    state: str | None
    state_required: bool | None
    basis_by_asset: dict[str, Decimal | None]
    engine_name: str
    engine_version: str
    parameter_set: str
    inputs_hash: str


def basis_of(asset: Asset, use_avd: bool) -> Decimal | None:
    """§1014: stepped-up assets take the estate's value; IRD and non-probate items take none."""
    if asset.basis_rule != "stepped_up":
        return None
    return asset.avd_value if use_avd and asset.avd_value is not None else asset.dod_value


def _hash(inputs: EstateInputs) -> str:
    payload = json.dumps(asdict(inputs), sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def _tax_on(
    taxable: Decimal, gifts: Decimal, exclusion: Decimal, params: EstateParameters
) -> Decimal:
    return max(ZERO, tentative_tax(taxable + gifts, params) - tentative_tax(exclusion, params))


def compute(inputs: EstateInputs) -> EstateResult:
    params = parameters(inputs.tax_year)
    dod = _c(sum((a.dod_value for a in inputs.assets), ZERO))
    avd = _c(
        sum(
            ((a.avd_value if a.avd_value is not None else a.dod_value) for a in inputs.assets),
            ZERO,
        )
    )
    deductions = _c(sum((d.amount for d in inputs.deductions), ZERO))
    gift_lines = tuple(
        GiftLine(
            g.key,
            g.year,
            _c(g.amount),
            annual_exclusion(g.year, params),
            _c(max(ZERO, g.amount - annual_exclusion(g.year, params))),
        )
        for g in sorted(inputs.gifts, key=lambda g: (g.year, g.key))
    )
    gifts = _c(sum((g.taxable for g in gift_lines), ZERO))
    taxable = _c(dod - deductions)
    base = _c(taxable + gifts)
    tentative = tentative_tax(base, params)
    exclusion = _c(params.bea + inputs.dsue)
    credit = tentative_tax(exclusion, params)
    net = _c(max(ZERO, tentative - credit))
    credit_bea = tentative_tax(params.bea, params)
    without = _c(max(ZERO, tentative - credit_bea))
    threshold = _c(dod + gifts)
    # §2032(c): only when it lowers both the gross estate and the tax (with the DSUE applied).
    avd_tax = _tax_on(_c(avd - deductions), gifts, exclusion, params)
    avd_available = avd < dod and avd_tax < net
    use_avd = inputs.elect_avd and avd_available
    basis = {a.key: basis_of(a, use_avd) for a in inputs.assets}
    state_ex = params.state_exclusions.get(inputs.residence_state or "")
    return EstateResult(
        gross_estate_dod=dod,
        gross_estate_avd=avd,
        basis_to_1041=_c(sum((b for b in basis.values() if b is not None), ZERO)),
        deductions=deductions,
        taxable_estate=taxable,
        gifts=gift_lines,
        adjusted_taxable_gifts=gifts,
        tentative_tax_base=base,
        tentative_tax=tentative,
        bea=_c(params.bea),
        dsue=_c(inputs.dsue),
        applicable_exclusion=exclusion,
        credit=credit,
        net_tax=net,
        credit_without_dsue=credit_bea,
        tax_without_dsue=without,
        filing_threshold_amount=threshold,
        filing_required=threshold > params.bea,
        avd_available=avd_available,
        state=inputs.residence_state,
        state_required=None if state_ex is None else dod > state_ex,
        basis_by_asset=basis,
        engine_name=ENGINE_NAME,
        engine_version=ENGINE_VERSION,
        parameter_set=f"ty{params.tax_year}.v{params.version}",
        inputs_hash=_hash(inputs),
    )


def outputs_of(result: EstateResult) -> dict[str, object]:
    """The JSON a computation version stores (money as strings)."""
    raw = asdict(result)
    out: dict[str, object] = {}
    for key, value in raw.items():
        if isinstance(value, Decimal):
            out[key] = f"{value:.2f}"
        elif key == "gifts":
            out[key] = [
                {k: (f"{v:.2f}" if isinstance(v, Decimal) else v) for k, v in g.items()}
                for g in cast(Sequence[dict[str, object]], value)
            ]
        elif key == "basis_by_asset":
            out[key] = {
                k: (None if v is None else f"{v:.2f}")
                for k, v in cast(dict[str, Decimal | None], value).items()
            }
        else:
            out[key] = value
    return out
