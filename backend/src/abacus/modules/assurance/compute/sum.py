"""The SUM engine (A-06-T07; A-06 §3 F4; SPEC-642 AC-6; ADR-050; DEC-1964). Pure: Decimal only,
no clock, no database, no I/O.

The summary of uncorrected misstatements under both AU-C 450 views:

- **rollover**: each uncorrected misstatement's effect on this year's change in net assets (or
  income), with the turnaround of last year's uncorrected misstatements carried in;
- **iron curtain**: each uncorrected misstatement's effect on the year-end balances, cumulative
  of last year's still uncorrected;
- the **aggregate** is the larger of the two in absolute value; it is shown as a percent of
  performance materiality (one decimal, half up) and of overall materiality (the threshold bar's
  fill, one decimal), with the bar's ticks at CT and PM as percents of overall;
- **below CT** items are listed but never accumulated; an aggregate at or above the firm's
  approaching-PM line (K-02; 50% of PM unless the firm sets another) is flagged.

Two column sets: `ebp_net_assets` (EBP: effect on net assets available for benefits) and
`commercial` (pre-tax income and balance sheet). The engine never chooses a conclusion: the EP
concludes on the snapshot (INV-1).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, localcontext
from typing import Final, Literal, cast

from abacus.kernel.numeric import CONTEXT, quantize_half_up

ENGINE_NAME: Final = "sum"
ENGINE_VERSION: Final = "1"
DEFAULT_APPROACHING_PM_PCT: Final = Decimal(50)
_HUNDRED: Final = Decimal(100)

ColumnSet = Literal["ebp_net_assets", "commercial"]


class SumInvalid(ValueError):
    code = "sum_invalid"


@dataclass(frozen=True)
class Item:
    """One uncorrected misstatement or prior-year carry. `rollover` and `iron_curtain` are its
    signed effects under each view, computed by the misstatement's own record (the projection
    from sampling, the entry's lines); `below_ct` items are listed, never accumulated."""

    ref: str
    rollover: Decimal
    iron_curtain: Decimal
    below_ct: bool = False
    prior_year: bool = False


@dataclass(frozen=True)
class Thresholds:
    overall: Decimal
    pm: Decimal
    ct: Decimal


@dataclass(frozen=True)
class Result:
    column_set: ColumnSet
    rollover: Decimal
    iron_curtain: Decimal
    aggregate: Decimal
    pct_of_pm: Decimal
    fill_pct_of_overall: Decimal
    ct_tick_pct: Decimal
    pm_tick_pct: Decimal
    approaching_pm: bool
    above_pm: bool
    accumulated: tuple[str, ...]
    below_ct: tuple[str, ...]
    engine_name: str
    engine_version: str
    inputs_hash: str


def _text(value: object) -> object:
    if isinstance(value, Decimal):
        return format(value.normalize(CONTEXT), "f")
    if isinstance(value, (list, tuple)):
        return [_text(v) for v in cast("list[object] | tuple[object, ...]", value)]
    return value


def _hash(**parts: object) -> str:
    body = json.dumps(
        {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            **{k: _text(v) for k, v in parts.items()},
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _pct(part: Decimal, whole: Decimal) -> Decimal:
    with localcontext(CONTEXT):
        return quantize_half_up(part / whole * _HUNDRED, 1)


def evaluate(
    items: Sequence[Item],
    thresholds: Thresholds,
    *,
    column_set: ColumnSet,
    approaching_pm_pct: Decimal = DEFAULT_APPROACHING_PM_PCT,
) -> Result:
    """The SUM for these items against these thresholds (AC-6)."""
    if thresholds.overall <= 0 or thresholds.pm <= 0 or thresholds.ct < 0:
        raise SumInvalid("thresholds")
    if not thresholds.ct <= thresholds.pm <= thresholds.overall:
        raise SumInvalid("thresholds")
    if not Decimal(0) < approaching_pm_pct <= _HUNDRED:
        raise SumInvalid("approaching_pm_pct")
    refs = [i.ref for i in items]
    if len(set(refs)) != len(refs):
        raise SumInvalid("ref")
    counted = [i for i in items if not i.below_ct]
    with localcontext(CONTEXT):
        rollover = sum((i.rollover for i in counted), Decimal(0))
        iron = sum((i.iron_curtain for i in counted), Decimal(0))
    aggregate = max(abs(rollover), abs(iron))
    pct_pm = _pct(aggregate, thresholds.pm)
    return Result(
        column_set=column_set,
        rollover=quantize_half_up(rollover, 2),
        iron_curtain=quantize_half_up(iron, 2),
        aggregate=quantize_half_up(aggregate, 2),
        pct_of_pm=pct_pm,
        fill_pct_of_overall=_pct(aggregate, thresholds.overall),
        ct_tick_pct=_pct(thresholds.ct, thresholds.overall),
        pm_tick_pct=_pct(thresholds.pm, thresholds.overall),
        approaching_pm=pct_pm >= approaching_pm_pct,
        above_pm=aggregate >= thresholds.pm,
        accumulated=tuple(i.ref for i in counted),
        below_ct=tuple(i.ref for i in items if i.below_ct),
        engine_name=ENGINE_NAME,
        engine_version=ENGINE_VERSION,
        inputs_hash=_hash(
            column_set=column_set,
            items=[[i.ref, i.rollover, i.iron_curtain, i.below_ct, i.prior_year] for i in items],
            thresholds=[thresholds.overall, thresholds.pm, thresholds.ct],
            approaching_pm_pct=approaching_pm_pct,
        ),
    )


def classify_below_ct(amount: Decimal, ct: Decimal) -> bool:
    """Under clearly trivial: logged, not accumulated (AUD-16 d: 4,210 under 12,610)."""
    return abs(amount) < ct
