"""Contributions and remittance (A-05-T24; A-05 §4.4 `remittance`; EBP-04, EBP-07, AUD-27;
29 CFR 2510.3-102; DEC-2211): pure functions over plain values.

- **Timing.** Business days count weekdays that are not legal holidays (K-02's `legal_holidays`
  set, jurisdiction US, passed in by the caller): a payroll paid Fri Dec 26, 2025 and deposited
  Fri Jan 9, 2026 is **9 business days** later, Jan 1 excluded. The plan's **established
  practice** sets when deposits are due (a large plan's judgement; the 7-business-day safe
  harbor applies only to plans under 100 participants and is never used for a large plan).
- **VFCP lost earnings.** Principal x [(1 + r/365)^days - 1], compounding daily at each day's
  §6621(a)(2) quarterly rate (`reference/irc_6621_rates.yaml`, PROTECTED), from the due date to
  the deposit: 33,540.00 at 7% for 10 days is 64.38; half up to cents. A quarter missing from the
  file is a refusal. Form 5330 excise exposure is 15% of lost earnings: 9.66.
- **Schedule H line 4a** carries the late **deferrals** only (never the match): 33,540.
- **The waterfall** (EBP-04 a): payroll deferrals + match, less payrolls deposited after year
  end, = trust receipts; + rollovers; + the receivable = the financial statements' figure; each
  step foots by code: 878,400 + 392,100 = 1,270,500; - 48,600 = 1,221,900; + 96,400 = 1,318,300;
  + 48,600 = 1,366,900.

Every result carries the engine stamp (name, version, inputs hash).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal, localcontext
from functools import cache
from pathlib import Path
from typing import Final, cast

import yaml

from abacus.kernel.calendar import add_business_days, is_business_day
from abacus.kernel.numeric import CONTEXT, quantize_half_up

ENGINE_NAME: Final = "ebp_remittance"
ENGINE_VERSION: Final = "1"
SMALL_PLAN_LIMIT: Final = 100  # participants: under 100 may use the 7-business-day safe harbor
SMALL_PLAN_SAFE_HARBOR_DAYS: Final = 7
EXCISE_RATE: Final = Decimal("0.15")  # IRC §4975(a) first-tier tax on the amount involved
_RATES_FILE: Final = Path(__file__).with_name("reference") / "irc_6621_rates.yaml"


class RateMissing(LookupError):
    """A day falls in a quarter the §6621 rate file does not have yet."""


@dataclass(frozen=True)
class Stamp:
    engine_name: str
    engine_version: str
    inputs_hash: str


@dataclass(frozen=True)
class Timing:
    business_days: int  # after the pay date, through the deposit date
    calendar_days: int
    due_on: date
    late: bool
    stamp: Stamp


@dataclass(frozen=True)
class LostEarnings:
    principal: Decimal
    interest_days: int
    lost_earnings: Decimal
    excise_exposure: Decimal
    rate_refs: tuple[str, ...]
    stamp: Stamp


@dataclass(frozen=True)
class WaterfallStep:
    label: str
    amount: Decimal
    running: Decimal


@dataclass(frozen=True)
class Waterfall:
    steps: tuple[WaterfallStep, ...]
    total: Decimal
    foots: bool
    stamp: Stamp


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


def stamp(kind: str, inputs: Mapping[str, object]) -> Stamp:
    body = json.dumps(
        {"engine": ENGINE_NAME, "version": ENGINE_VERSION, "kind": kind, "inputs": _plain(inputs)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return Stamp(ENGINE_NAME, ENGINE_VERSION, hashlib.sha256(body.encode("utf-8")).hexdigest())


# --- timing -------------------------------------------------------------------------------------


def business_days_between(start: date, end: date, holidays: frozenset[date]) -> int:
    """Business days after `start` up to and including `end` (0 when end ≤ start)."""
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        if is_business_day(day, holidays):
            count += 1
    return count


def timing(
    pay_date: date,
    deposit_date: date,
    *,
    established_practice_days: int,
    participants: int,
    holidays: frozenset[date],
) -> Timing:
    """Due by the plan's established practice; a small plan's 7-day safe harbor caps the due
    date only when the plan has fewer than 100 participants (never for a large plan)."""
    if established_practice_days < 0:
        raise ValueError("established practice must not be negative")
    days = established_practice_days
    if participants < SMALL_PLAN_LIMIT:
        days = max(days, SMALL_PLAN_SAFE_HARBOR_DAYS)
    due_on = add_business_days(pay_date, days, holidays)
    inputs = {
        "pay_date": pay_date,
        "deposit_date": deposit_date,
        "practice": established_practice_days,
        "participants": participants,
        "holidays": sorted(h for h in holidays if pay_date <= h <= deposit_date),
    }
    return Timing(
        business_days=business_days_between(pay_date, deposit_date, holidays),
        calendar_days=(deposit_date - pay_date).days,
        due_on=due_on,
        late=deposit_date > due_on,
        stamp=stamp("timing", inputs),
    )


# --- lost earnings ------------------------------------------------------------------------------


@cache
def rates() -> dict[str, Decimal]:
    raw = cast(dict[str, object], yaml.safe_load(_RATES_FILE.read_text(encoding="utf-8")))
    table = cast(Mapping[str, object], raw["rates"])
    return {str(k): Decimal(str(v)) for k, v in table.items()}


def quarter_key(day: date) -> str:
    return f"{day.year}-Q{(day.month - 1) // 3 + 1}"


def lost_earnings(
    principal: Decimal,
    due_on: date,
    deposited_on: date,
    *,
    rate_table: Mapping[str, Decimal] | None = None,
) -> LostEarnings:
    """VFCP lost earnings from the due date to the deposit, compounding daily at each day's
    quarterly §6621(a)(2) rate; the excise exposure is 15% of it. Cents, half up."""
    if principal <= 0:
        raise ValueError("principal must be positive")
    table = rates() if rate_table is None else rate_table
    days = max(0, (deposited_on - due_on).days)
    factor = Decimal(1)
    refs: list[str] = []
    with localcontext(CONTEXT):
        for n in range(days):
            key = quarter_key(due_on + timedelta(days=n))
            if key not in table:
                raise RateMissing(key)
            if key not in refs:
                refs.append(key)
            factor *= 1 + table[key] / Decimal(100) / Decimal(365)
        earned = quantize_half_up(principal * (factor - 1), 2)
        excise = quantize_half_up(earned * EXCISE_RATE, 2)
    inputs = {"principal": principal, "due_on": due_on, "deposited_on": deposited_on}
    inputs |= {"rates": {k: table[k] for k in refs}}
    return LostEarnings(
        principal, days, earned, excise, tuple(refs), stamp("lost_earnings", inputs)
    )


def schedule_h_4a(late_deferrals: Sequence[Decimal]) -> Decimal:
    """Line 4a: the late participant contributions (deferrals only, never the match)."""
    return sum(late_deferrals, Decimal(0))


# --- the waterfall ------------------------------------------------------------------------------


def waterfall(
    *,
    deferrals: Decimal,
    match: Decimal,
    deposited_after_year_end: Decimal,
    rollovers: Decimal,
    receivable: Decimal,
    per_statements: Decimal,
) -> Waterfall:
    """EBP-04 a: each step and its running total, and whether it reaches the FS figure."""
    running = Decimal(0)
    steps: list[WaterfallStep] = []
    for label, amount in (
        ("deferrals", deferrals),
        ("match", match),
        ("deposited_after_year_end", -deposited_after_year_end),
        ("rollovers", rollovers),
        ("receivable", receivable),
    ):
        running += amount
        steps.append(WaterfallStep(label, amount, running))
    inputs = {
        "deferrals": deferrals,
        "match": match,
        "after": deposited_after_year_end,
        "rollovers": rollovers,
        "receivable": receivable,
        "per_statements": per_statements,
    }
    return Waterfall(tuple(steps), running, running == per_statements, stamp("waterfall", inputs))
