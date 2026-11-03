"""The bracket check (N-04 US-4.3; QN-3; DEC-77): the agency's tax change under the year's
ordinary-income schedule (`rate_schedules/ty*.yaml`, PROTECTED).

It verifies the agency's figure and never replaces it: the result is "agrees", "differs" with the
expected figure beside the notice's, or "Not checked" with a reason (a preferential-rate change,
a year or filing status without a schedule). Whitley TY2024 MFJ: tax(151,720) - tax(148,600) =
22% x 3,120 = 686.40, the notice's change.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, localcontext
from functools import cache
from pathlib import Path
from typing import Literal, cast

import yaml

from abacus.kernel.numeric import CONTEXT, quantize_half_up
from abacus.modules.notices.compute.stamp import Stamp, stamp

FilingStatus = Literal["single", "mfj", "mfs", "hoh", "qss"]
_DIR = Path(__file__).with_name("rate_schedules")
PREFERENTIAL = "Not checked — preferential rates"
NO_SCHEDULE = "Not checked — no rate schedule for this year"


@dataclass(frozen=True)
class Schedule:
    bounds: tuple[Decimal, ...]
    rates: tuple[Decimal, ...]


@dataclass(frozen=True)
class BracketCheck:
    checked: bool
    rate: Decimal | None  # the marginal rate when both incomes sit in one bracket
    expected: Decimal | None
    notice: Decimal
    agrees: bool
    reason: str | None
    stamp: Stamp


@cache
def schedule(tax_year: int, filing_status: FilingStatus) -> Schedule | None:
    path = _DIR / f"ty{tax_year}.yaml"
    if not path.exists():
        return None
    raw = cast(dict[str, object], yaml.safe_load(path.read_text(encoding="utf-8")))
    schedules = cast(dict[str, list[int]], raw["schedules"])
    bounds = schedules["mfj" if filing_status == "qss" else filing_status]
    rates = cast(list[str], raw["rates"])
    return Schedule(tuple(Decimal(b) for b in bounds), tuple(Decimal(r) for r in rates))


def tax(taxable_income: Decimal, table: Schedule) -> Decimal:
    """The schedule's tax on `taxable_income`, to the cent (half up)."""
    with localcontext(CONTEXT):
        owed, lower = Decimal(0), Decimal(0)
        income = max(taxable_income, Decimal(0))
        for upper, rate in zip((*table.bounds, None), table.rates, strict=True):
            top = income if upper is None else min(income, upper)
            if top > lower:
                owed += (top - lower) * rate
            if upper is None or income <= upper:
                break
            lower = upper
        return quantize_half_up(owed, 2)


def _rate(income: Decimal, table: Schedule) -> Decimal:
    for upper, rate in zip(table.bounds, table.rates, strict=False):
        if income <= upper:
            return rate
    return table.rates[-1]


def check(
    filing_status: FilingStatus,
    tax_year: int,
    ti_before: Decimal,
    ti_after: Decimal,
    notice_tax_change: Decimal,
    *,
    preferential: bool = False,
) -> BracketCheck:
    inputs = {
        "filing_status": filing_status,
        "tax_year": tax_year,
        "ti_before": ti_before,
        "ti_after": ti_after,
        "notice": notice_tax_change,
        "preferential": preferential,
    }
    mark = stamp("bracket.check", inputs)
    if preferential:
        return BracketCheck(False, None, None, notice_tax_change, False, PREFERENTIAL, mark)
    table = schedule(tax_year, filing_status)
    if table is None:
        return BracketCheck(False, None, None, notice_tax_change, False, NO_SCHEDULE, mark)
    with localcontext(CONTEXT):
        expected = quantize_half_up(tax(ti_after, table) - tax(ti_before, table), 2)
    same = _rate(ti_before, table) == _rate(ti_after, table)
    agrees = expected == quantize_half_up(notice_tax_change, 2)
    return BracketCheck(
        True,
        _rate(ti_after, table) if same else None,
        expected,
        notice_tax_change,
        agrees,
        None if agrees else "The notice's tax change differs from the schedule",
        mark,
    )
