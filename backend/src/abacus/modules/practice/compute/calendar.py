"""The calendar engine (K-02-T07; K-02 §3 F2; C21 part A): due dates and clocks as pure functions.

Inputs are the published rule rows and holiday dates the caller resolved (`practice.due_dates`
reads them from `platform.api`); nothing here reads a clock or a database, so the same inputs
always give the same dates (ADR-050, the Hypothesis properties in tests/property).

- A due date is the rule's day of the month that falls `months_after_period_end` months after the
  period end, clamped to that month's last day. The extension adds its months to the unrolled
  original date (Mar 15 + 6 = Sep 15, whatever Mar 15 rolled to), on the extension's own day
  when it names one (5558: Jul 31 + 3 months on the 15th is Oct 15).
- IRC §7503: a date on a Saturday, Sunday or legal holiday rolls to the next day that is none of
  them. Federal filings count federal and DC holidays (QK-5; DEC-76).
- A disaster postponement covers a date when the date falls in its window and the location is in
  one of its areas (an area with no counties covers the whole state); the date moves to the
  notice's postponed-to date, never earlier.
- Clocks are calendar days and never roll: AU-C 230 assembly and AU-C 265 communication +60, the
  FTC notice +30, and 8879 retention three years after its start (the later of the due date and
  the IRS received date; Feb 29 ends on Feb 28).
"""

from __future__ import annotations

import calendar
import hashlib
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal

# A-03-T21: the business-day arithmetic lives in the kernel; re-exported for K-02's callers.
from abacus.kernel.calendar import add_business_days as add_business_days
from abacus.kernel.calendar import is_business_day as is_business_day
from abacus.kernel.calendar import roll as roll

ClockKind = Literal[
    "au_c_230_assembly", "au_c_265_communication", "ftc_notice", "form_8879_retention"
]

# I-CLOCKS (chapter 10 §10.9.3): calendar days, or years for the 8879 retention.
CLOCK_DAYS: Final[Mapping[ClockKind, int]] = {
    "au_c_230_assembly": 60,
    "au_c_265_communication": 60,
    "ftc_notice": 30,
}
FORM_8879_RETENTION_YEARS: Final = 3


@dataclass(frozen=True)
class Offset:
    months: int
    day: int


@dataclass(frozen=True)
class Rule:
    """One form's rule as the engine needs it (from a `due_date_rules` row)."""

    form: str
    fye_rule: Literal["calendar_year", "fiscal_year", "any"]
    original: Offset
    extension_form: str | None
    extension_months: int | None
    # The extended date's day of the month, when it is not the original's (5558: Jul 31 + 2½
    # months is Oct 15; 7004 for a 1041: Apr 15 + 5½ months is Sep 30).
    extension_day: int | None = None


@dataclass(frozen=True)
class Area:
    state: str
    counties: frozenset[str]


@dataclass(frozen=True)
class Postponement:
    notice_id: str
    areas: tuple[Area, ...]
    start: date
    end: date
    postponed_to: date


@dataclass(frozen=True)
class Place:
    state: str
    county: str | None = None


@dataclass(frozen=True)
class Dates:
    original_due_on: date
    original_rolled: bool
    extension_form: str | None
    extended_due_on: date | None
    extended_rolled: bool
    postponement_notice_id: str | None
    postponed_to: date | None = None


def add_months(start: date, months: int, day: int) -> date:
    """The `day` of the month `months` after `start`'s month, clamped to that month's end."""
    index = start.month - 1 + months
    year, month = start.year + index // 12, index % 12 + 1
    return date(year, month, min(day, calendar.monthrange(year, month)[1]))


def pick_rule(rules: Iterable[Rule], form: str, period_end: date) -> Rule | None:
    """The form's rule for this period end: a calendar- or fiscal-year rule before `any`."""
    year_end = (period_end.month, period_end.day) == (12, 31)
    fitting = [
        r
        for r in rules
        if r.form == form and (r.fye_rule == "any" or (r.fye_rule == "calendar_year") is year_end)
    ]
    fitting.sort(key=lambda r: r.fye_rule == "any")
    return fitting[0] if fitting else None


def covers(postponement: Postponement, day: date, place: Place) -> bool:
    if not postponement.start <= day <= postponement.end:
        return False
    return any(
        area.state == place.state
        and (not area.counties or (place.county is not None and place.county in area.counties))
        for area in postponement.areas
    )


def postpone(
    day: date, postponements: Sequence[Postponement], place: Place | None, event: date | None
) -> tuple[date, str | None]:
    """The latest postponed-to date of the notices covering `day` (or the `event` date, when
    the caller names the act's date) at `place`; `day` unchanged when none does."""
    if place is None:
        return day, None
    probe = event or day
    best: Postponement | None = None
    for notice in postponements:
        if (
            covers(notice, probe, place)
            and notice.postponed_to > day
            and (
                best is None
                or (notice.postponed_to, notice.notice_id) > (best.postponed_to, best.notice_id)
            )
        ):
            best = notice
    return (day, None) if best is None else (best.postponed_to, best.notice_id)


def due_dates(
    rule: Rule,
    period_end: date,
    holidays: frozenset[date],
    postponements: Sequence[Postponement] = (),
    place: Place | None = None,
    event: date | None = None,
) -> Dates:
    """The original and extended due dates of `rule` for a period end."""
    original = add_months(period_end, rule.original.months, rule.original.day)
    original_on, original_rolled = roll(original, holidays)
    extended_on: date | None = None
    extended_rolled = False
    if rule.extension_months is not None:
        day = rule.extension_day or original.day
        extended = add_months(original, rule.extension_months, day)
        extended_on, extended_rolled = roll(extended, holidays)
    # A postponement moves each date it covers; the notice named is the one that moved the
    # later date.
    original_on, original_notice = postpone(original_on, postponements, place, event)
    extended_notice: str | None = None
    if extended_on is not None:
        extended_on, extended_notice = postpone(extended_on, postponements, place, event)
    notice = extended_notice or original_notice
    postponed_to = extended_on if extended_notice else original_on if original_notice else None
    return Dates(
        original_due_on=original_on,
        original_rolled=original_rolled,
        extension_form=rule.extension_form,
        extended_due_on=extended_on,
        extended_rolled=extended_rolled,
        postponement_notice_id=notice,
        postponed_to=postponed_to,
    )


def _ordinal(n: int) -> str:
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def rule_text(rule: Rule, *, extended: bool) -> str:
    """The Due popover's rule ("15th day, 3rd month + 6 months"; an extension on its own day
    runs a half month short or long: a 1041's 7004 is "+ 5½ months", a 5558 "+ 2½ months")."""
    text = f"{_ordinal(rule.original.day)} day, {_ordinal(rule.original.months)} month"
    if not extended or rule.extension_months is None:
        return text
    months = rule.extension_months
    if rule.extension_day is not None and rule.extension_day != rule.original.day:
        whole = months if rule.extension_day > rule.original.day else months - 1
        return f"{text} + {whole}½ months"
    return f"{text} + {months} months"


def clock_due(kind: ClockKind, start: date) -> date:
    """A calendar-day clock's end: never rolled."""
    if kind == "form_8879_retention":
        year = start.year + FORM_8879_RETENTION_YEARS
        return date(year, start.month, min(start.day, calendar.monthrange(year, start.month)[1]))
    return start + timedelta(days=CLOCK_DAYS[kind])


def inputs_hash(inputs: Mapping[str, object]) -> str:
    """sha256 over the canonical JSON of the inputs (dates as ISO strings)."""
    raw = json.dumps(inputs, sort_keys=True, separators=(",", ":"), default=str).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()
