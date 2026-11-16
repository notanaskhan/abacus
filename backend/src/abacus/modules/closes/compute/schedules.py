"""Close schedules and their tie to the GL (C-01-T21; C-01 §3 F6; CLS-04; ADR-050).

Pure: Decimal only, no clock, no database, no I/O.

- **Activity.** A prepaid or deferred revenue amortises its scheduled total straight-line over its
  periods, a fixed asset depreciates the same way, and an accrual builds up its total the same
  way; the last period takes the cents rounding left over, so the periods foot to the total
  (prepaid 8,400 / 12 = 700). A period's line holds its inflows (the opening total in its first
  period, after the starting balance), its activity (the AJE the schedule calls for) and the
  ending balance.
- **The tie.** The schedule's ending balance against the GL's: equal reads `tie` (or `recorded`
  when the entry that tied it was found recorded in QuickBooks); a pending proposed entry whose
  effect on the account closes the difference exactly reads `ties_once_posted` ("Ties once
  posted", CLS-04 c); anything else is `off` by the difference.
- **Rollups.** The account tree's balances roll up in code: account type, then classification.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_DOWN, Decimal
from typing import Final, Literal

ENGINE_NAME: Final = "closes.schedules"
ENGINE_VERSION: Final = "1"
ENGINE_STAMP: Final = f"{ENGINE_NAME}/{ENGINE_VERSION}"
CENT: Final = Decimal("0.01")
ZERO: Final = Decimal("0.00")

Kind = Literal["prepaid", "fixed_asset", "accrual", "deferred_revenue"]
Frequency = Literal["monthly", "quarterly", "annual"]
Tie = Literal["tie", "off", "ties_once_posted", "recorded"]
_STEP: Final[Mapping[str, int]] = {"monthly": 1, "quarterly": 3, "annual": 12}


class ScheduleInvalid(ValueError):
    code = "schedule_invalid"


@dataclass(frozen=True)
class Arrangement:
    kind: Kind
    scheduled_total: Decimal
    start_on: date
    finish_on: date
    frequency: Frequency = "monthly"
    starting_balance: Decimal = ZERO  # the balance carried in when the schedule starts mid-way


@dataclass(frozen=True)
class Line:
    period: str  # YYYY-MM
    inflows: Decimal
    aje: Decimal
    ending_balance: Decimal


@dataclass(frozen=True)
class PendingEntry:
    """A proposed entry not yet recorded: its number and its net effect on the account."""

    number: str
    effect: Decimal


@dataclass(frozen=True)
class TieResult:
    tie: Tie
    gl_balance: Decimal
    schedule_balance: Decimal
    off_by: Decimal | None
    pending_entry_number: str | None


def _period(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _months(start: date, finish: date) -> int:
    return (finish.year - start.year) * 12 + finish.month - start.month + 1


def _add(period: str, months: int) -> str:
    year, month = int(period[:4]), int(period[5:])
    index = year * 12 + month - 1 + months
    return f"{index // 12:04d}-{index % 12 + 1:02d}"


def periods_of(arrangement: Arrangement) -> tuple[str, ...]:
    """The periods the schedule posts in, first to last."""
    if arrangement.finish_on < arrangement.start_on:
        raise ScheduleInvalid("finish before start")
    step = _STEP[arrangement.frequency]
    months = _months(arrangement.start_on, arrangement.finish_on)
    if months % step:
        raise ScheduleInvalid("the term is not a whole number of periods")
    first = _period(arrangement.start_on)
    return tuple(_add(first, i * step + step - 1) for i in range(months // step))


def schedule(arrangement: Arrangement, through: str | None = None) -> tuple[Line, ...]:
    """Every period's line, or those through `through` (YYYY-MM)."""
    total = Decimal(arrangement.scheduled_total).quantize(CENT)
    if total <= 0:
        raise ScheduleInvalid("the scheduled total is positive")
    periods = periods_of(arrangement)
    each = (total / len(periods)).quantize(CENT, rounding=ROUND_DOWN)
    builds = arrangement.kind == "accrual"
    balance = Decimal(arrangement.starting_balance).quantize(CENT)
    out: list[Line] = []
    posted = ZERO
    for n, period in enumerate(periods):
        last = n == len(periods) - 1
        step = (total - posted) if last else each
        posted += step
        inflows = ZERO
        if n == 0 and not builds:
            inflows = (total - balance) if balance else total
            balance += inflows
        balance = balance + step if builds else balance - step
        out.append(
            Line(period, inflows.quantize(CENT), step.quantize(CENT), balance.quantize(CENT))
        )
        if through is not None and period >= through:
            break
    return tuple(out)


def balance_at(arrangement: Arrangement, period: str) -> Decimal:
    """The schedule's ending balance at `period` (zero before it starts and after it ends,
    except an accrual, which holds its total once built)."""
    lines = schedule(arrangement)
    if period < lines[0].period:
        return ZERO
    found = [line for line in lines if line.period <= period]
    return found[-1].ending_balance


def tie(
    gl_balance: Decimal,
    schedule_balance: Decimal,
    pending: Sequence[PendingEntry] = (),
    *,
    recorded: bool = False,
) -> TieResult:
    gl = Decimal(gl_balance).quantize(CENT)
    sched = Decimal(schedule_balance).quantize(CENT)
    difference = (gl - sched).quantize(CENT)
    if difference == 0:
        return TieResult("recorded" if recorded else "tie", gl, sched, None, None)
    for entry in pending:
        if (gl + Decimal(entry.effect)).quantize(CENT) == sched:
            return TieResult("ties_once_posted", gl, sched, difference, entry.number)
    return TieResult("off", gl, sched, difference, None)


def rollup(
    leaves: Iterable[tuple[str, str, Decimal]],
) -> dict[str, dict[str, Decimal]]:
    """(classification, account type, balance) leaves rolled up: {classification: {type: sum}},
    with `""` holding each classification's total."""
    out: dict[str, dict[str, Decimal]] = {}
    for classification, account_type, amount in leaves:
        group = out.setdefault(classification, {"": ZERO})
        group[account_type] = (group.get(account_type, ZERO) + amount).quantize(CENT)
        group[""] = (group[""] + amount).quantize(CENT)
    return out


def inputs_hash(arrangement: Arrangement, period: str, gl_balance: Decimal) -> str:
    body = json.dumps(
        {
            "engine": ENGINE_NAME,
            "version": ENGINE_VERSION,
            "kind": arrangement.kind,
            "total": format(Decimal(arrangement.scheduled_total).quantize(CENT), "f"),
            "start": arrangement.start_on.isoformat(),
            "finish": arrangement.finish_on.isoformat(),
            "frequency": arrangement.frequency,
            "starting": format(Decimal(arrangement.starting_balance).quantize(CENT), "f"),
            "period": period,
            "gl": format(Decimal(gl_balance).quantize(CENT), "f"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(body.encode()).hexdigest()
