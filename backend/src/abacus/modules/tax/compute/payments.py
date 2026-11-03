"""The payments engine (T-03-T04; T-03 §4.4, F4, F5; DEC-77, DEC-2203): extension safe harbors
and estimated-tax installments as pure functions.

Code computes every figure on TAX-13 (ADR-050); a model never does this arithmetic. Inputs are
`Decimal`s and the engine parameters (`parameters/ty<year>.yaml`, PROTECTED, pinned by goldens);
nothing reads a clock, a database or the network. Rounding is explicit: half up to the
parameter file's places, at each step the spec rounds (TAX-13 b), or by largest remainder when a
schedule must foot. Every result carries an engine stamp (name, version, inputs hash), which the
service persists beside the figure.

- **Safe harbor** (extensions): the target is the form's percentage of the projected liability
  (90% for a 1040 under Treas. Reg. §301.6651-1(c)(3); 100% for a 1041, 1120 or 706); a
  pass-through or exempt return has none. What was paid by the original due date is withholding
  plus estimates plus the extension payments, and meets the harbor when it reaches the target.
  Feld: 90% x 122,500 = 110,250; 113,476 + 10,000 = 123,476 ≥ 110,250.
- **Required annual payment** (estimates, IRC §6654(d)): the method's percentage of the prior- or
  current-year tax, less projected withholding, never below zero. Prior year is 110% when the
  prior-year AGI was over the threshold. Feld federal: round(1.10 x 123,223) = 135,545 -
  55,585 = 79,960; NY: round(1.10 x 52,805) = 58,086 - 26,790 = 31,296.
- **Installments**: the annual payment over the quarters, each rounded half up (79,960 / 4 =
  19,990; 50,930 / 4 = 12,733), or split by largest remainder so the four foot.
- An estate's first two tax years need no estimates (IRC §6654(l)(2)).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, localcontext
from functools import cache
from pathlib import Path
from typing import Final, Literal, cast

import yaml

from abacus.kernel.numeric import CONTEXT, allocate, quantize_half_up

ENGINE_NAME: Final = "tax.payments"
ENGINE_VERSION: Final = "1"
_DIR: Final = Path(__file__).with_name("parameters")

Method = Literal[
    "prior_year_100",
    "prior_year_110",
    "current_year_90",
    "not_required_withholding",
    "not_required_estate_first_years",
    "prospect",
]
Rounding = Literal["half_up_each", "largest_remainder"]


@dataclass(frozen=True)
class Stamp:
    engine_name: str
    engine_version: str
    inputs_hash: str


@dataclass(frozen=True)
class EstimateParameters:
    current_year_pct: Decimal
    prior_year_pct: Decimal
    prior_year_high_income_pct: Decimal
    agi_threshold: Decimal
    agi_threshold_married_separate: Decimal
    estate_exempt_tax_years: int
    quarters: int
    rounding: Rounding
    rounding_places: int


@dataclass(frozen=True)
class Parameters:
    version: int
    tax_year: int
    extension_safe_harbor_pct: Mapping[str, Decimal | None]
    estimates: EstimateParameters
    likely_window_days: int


@dataclass(frozen=True)
class SafeHarbor:
    """The target for a return form, or no target (`pct` None: pass-through or exempt)."""

    pct: Decimal | None
    target: Decimal | None
    stamp: Stamp


@dataclass(frozen=True)
class PaidCheck:
    paid_by_original_due: Decimal
    target: Decimal | None
    meets: bool | None  # None when the form has no target
    shortfall: Decimal  # zero when it meets (or has no target)
    stamp: Stamp


@dataclass(frozen=True)
class AnnualRequired:
    method: Method
    pct: Decimal | None
    base: Decimal | None  # the method's percentage of the tax, rounded
    annual: Decimal | None  # None for a not-required or prospect schedule
    stamp: Stamp


@dataclass(frozen=True)
class Installments:
    amounts: tuple[Decimal, ...]
    rounding: Rounding
    stamp: Stamp


# --- parameters ---------------------------------------------------------------------------------


def _dec(raw: object) -> Decimal:
    if isinstance(raw, bool) or not isinstance(raw, (str, int)):
        raise ValueError(f"parameter must be a string or an integer, not {raw!r}")
    return Decimal(str(raw))


def parse_parameters(raw: Mapping[str, object]) -> Parameters:
    """The parameter file's mapping, validated (a missing or wrong key raises)."""
    pct = cast(Mapping[str, object], raw["extension_safe_harbor_pct"])
    est = cast(Mapping[str, object], raw["estimates"])
    likely = cast(Mapping[str, object], raw["likely_to_extend"])
    rounding = cast(str, est["rounding"])
    if rounding not in ("half_up_each", "largest_remainder"):
        raise ValueError(f"unknown rounding {rounding!r}")
    return Parameters(
        version=int(cast(int, raw["version"])),
        tax_year=int(cast(int, raw["tax_year"])),
        extension_safe_harbor_pct={
            str(form): (None if value is None else _dec(value)) for form, value in pct.items()
        },
        estimates=EstimateParameters(
            current_year_pct=_dec(est["current_year_pct"]),
            prior_year_pct=_dec(est["prior_year_pct"]),
            prior_year_high_income_pct=_dec(est["prior_year_high_income_pct"]),
            agi_threshold=_dec(est["agi_threshold"]),
            agi_threshold_married_separate=_dec(est["agi_threshold_married_separate"]),
            estate_exempt_tax_years=int(cast(int, est["estate_exempt_tax_years"])),
            quarters=int(cast(int, est["quarters"])),
            rounding=rounding,
            rounding_places=int(cast(int, est["rounding_places"])),
        ),
        likely_window_days=int(cast(int, likely["window_days"])),
    )


@cache
def parameters(tax_year: int) -> Parameters:
    """`parameters/ty<tax_year>.yaml` (PROTECTED). A year without a file raises `LookupError`."""
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.is_file():
        raise LookupError(f"tax payments parameters: ty{tax_year}")
    raw = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    return parse_parameters(raw)


# --- the stamp ----------------------------------------------------------------------------------


def _plain(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Mapping):
        items = cast(Mapping[object, object], value).items()
        return {str(k): _plain(v) for k, v in sorted(items, key=lambda kv: str(kv[0]))}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in cast(Sequence[object], value)]
    return value


def stamp(kind: str, inputs: Mapping[str, object], params: Parameters) -> Stamp:
    """SHA-256 of the canonical JSON of the inputs, the parameter year and version."""
    body = json.dumps(
        {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "kind": kind,
            "parameters": [params.tax_year, params.version],
            "inputs": _plain(inputs),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return Stamp(ENGINE_NAME, ENGINE_VERSION, hashlib.sha256(body.encode("utf-8")).hexdigest())


def _pct(value: Decimal, pct: Decimal, places: int) -> Decimal:
    with localcontext(CONTEXT):
        return quantize_half_up(value * pct / Decimal(100), places)


# --- extensions ---------------------------------------------------------------------------------


def safe_harbor(
    return_form: str, projected_liability: Decimal | None, params: Parameters
) -> SafeHarbor:
    """The safe-harbor target for a return form (cents, half up). `LookupError` for a form the
    parameter file does not name."""
    if return_form not in params.extension_safe_harbor_pct:
        raise LookupError(f"safe harbor: {return_form}")
    pct = params.extension_safe_harbor_pct[return_form]
    target = None
    if pct is not None and projected_liability is not None:
        if projected_liability < 0:
            raise ValueError("projected liability must not be negative")
        target = _pct(projected_liability, pct, 2)
    inputs = {"form": return_form, "projected_liability": projected_liability}
    return SafeHarbor(pct, target, stamp("safe_harbor", inputs, params))


def paid_by_original_due(
    withholding_plus_estimates: Decimal,
    extension_payments: Sequence[Decimal],
    target: Decimal | None,
    params: Parameters,
) -> PaidCheck:
    """Withholding and estimates plus every extension payment, against the target."""
    if withholding_plus_estimates < 0 or any(p < 0 for p in extension_payments):
        raise ValueError("payments must not be negative")
    paid = withholding_plus_estimates + sum(extension_payments, Decimal(0))
    meets = None if target is None else paid >= target
    shortfall = Decimal(0) if target is None or paid >= target else target - paid
    inputs = {
        "withholding_plus_estimates": withholding_plus_estimates,
        "extension_payments": list(extension_payments),
        "target": target,
    }
    return PaidCheck(paid, target, meets, shortfall, stamp("paid_by_original_due", inputs, params))


# --- estimates ----------------------------------------------------------------------------------


def prior_year_method(
    prior_agi: Decimal, params: Parameters, *, married_separate: bool = False
) -> Method:
    """110% when the prior-year AGI is over the threshold (IRC §6654(d)(1)(C)), else 100%."""
    e = params.estimates
    threshold = e.agi_threshold_married_separate if married_separate else e.agi_threshold
    return "prior_year_110" if prior_agi > threshold else "prior_year_100"


def estate_exempt(estate_tax_year_index: int, params: Parameters) -> bool:
    """An estate's first `estate_exempt_tax_years` tax years (1-based) need no estimates."""
    if estate_tax_year_index < 1:
        raise ValueError("an estate's first tax year is 1")
    return estate_tax_year_index <= params.estimates.estate_exempt_tax_years


def required_annual_payment(
    method: Method,
    *,
    prior_year_tax: Decimal | None,
    projected_withholding: Decimal | None,
    params: Parameters,
    current_year_tax: Decimal | None = None,
) -> AnnualRequired:
    """The method's percentage of the tax (rounded), less projected withholding, never below
    zero. Not-required and prospect methods have no amount."""
    e = params.estimates
    places = e.rounding_places
    inputs = {
        "method": method,
        "prior_year_tax": prior_year_tax,
        "current_year_tax": current_year_tax,
        "projected_withholding": projected_withholding,
    }
    pct: Decimal | None
    tax: Decimal | None
    if method == "prior_year_100":
        pct, tax = e.prior_year_pct, prior_year_tax
    elif method == "prior_year_110":
        pct, tax = e.prior_year_high_income_pct, prior_year_tax
    elif method == "current_year_90":
        pct, tax = e.current_year_pct, current_year_tax
    else:
        return AnnualRequired(method, None, None, None, stamp("annual_required", inputs, params))
    if tax is None:
        raise ValueError(f"{method} needs its tax figure")
    if tax < 0 or (projected_withholding is not None and projected_withholding < 0):
        raise ValueError("tax and withholding must not be negative")
    base = _pct(tax, pct, places)
    annual = max(Decimal(0), base - (projected_withholding or Decimal(0)))
    annual = quantize_half_up(annual, places)
    return AnnualRequired(method, pct, base, annual, stamp("annual_required", inputs, params))


def installment_amounts(
    annual: Decimal, params: Parameters, *, rounding: Rounding | None = None
) -> Installments:
    """The annual payment over the parameter file's quarters. `half_up_each` rounds each share
    on its own (TAX-13 b); `largest_remainder` makes them foot to the annual payment."""
    e = params.estimates
    how = rounding or e.rounding
    if annual < 0:
        raise ValueError("the annual payment must not be negative")
    places = e.rounding_places
    if how == "half_up_each":
        share = quantize_half_up(annual / Decimal(e.quarters), places)
        amounts = tuple(share for _ in range(e.quarters))
    else:
        amounts = allocate(quantize_half_up(annual, places), [Decimal(1)] * e.quarters, places)
    inputs = {"annual": annual, "rounding": how}
    return Installments(amounts, how, stamp("installments", inputs, params))
