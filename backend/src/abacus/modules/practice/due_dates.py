"""C21 part A, the service: due dates and clocks (K-02-T07; K-02 §3 F2, §4.5).

Reads the published reference sets through `platform.api` and hands their rows to the pure
engine in `compute/calendar.py`. Which version answers (C21 `as_of`, DEC-1255):

- Due-date rules on the period end; a set whose version names the return's tax year comes before
  one that doesn't, then the latest effective.
- Legal holidays and disaster postponements on the later of today (business time) and a fortnight
  past the latest unrolled due date, so the year's holiday list is in effect when a date rolls
  and a postponement published mid-season reaches every return it covers. Every holiday set
  counts, federal and DC (IRC §7503; QK-5).

Every result names the versions it read and hashes its inputs with them (INV-2), so the same
inputs and the same published rules always give the same answer and the same hash.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Final, cast
from uuid import UUID

from abacus.kernel.clock import today
from abacus.modules.platform.api import (
    DisasterPostponementsPayload,
    DueDateRulesPayload,
    LegalHolidaysPayload,
    ResolvedReference,
    references_in_effect,
)
from abacus.modules.practice.compute import calendar
from abacus.modules.practice.compute.calendar import ClockKind
from abacus.modules.practice.due_dates_contract import ClockDue, DueDates, Location

# Past the latest unrolled date, so the holiday list a date rolls through is in effect.
_ROLL_MARGIN: Final = timedelta(days=14)


def _rules(payload: DueDateRulesPayload) -> list[calendar.Rule]:
    return [
        calendar.Rule(
            form=row.form,
            fye_rule=row.fye_rule,
            original=calendar.Offset(row.original.months_after_period_end, row.original.day),
            extension_form=row.extension.form if row.extension else None,
            extension_months=row.extension.months if row.extension else None,
            extension_day=row.extension.day if row.extension else None,
        )
        for row in payload.rows
    ]


def _postponements(payload: DisasterPostponementsPayload) -> list[calendar.Postponement]:
    return [
        calendar.Postponement(
            notice_id=row.notice_id,
            areas=tuple(
                calendar.Area(area.state_code, frozenset(area.counties)) for area in row.areas
            ),
            start=row.window.start,
            end=row.window.end,
            postponed_to=row.postponed_to,
        )
        for row in payload.rows
    ]


async def _rule_for(
    form: str, tax_year: int, period_end: date
) -> tuple[calendar.Rule, ResolvedReference]:
    sets = await references_in_effect("due_date_rules", period_end)
    # A stable sort keeps latest-effective-first inside each group.
    sets.sort(key=lambda r: r.tax_year != tax_year)
    for found in sets:
        rule = calendar.pick_rule(
            _rules(cast(DueDateRulesPayload, found.payload)), form, period_end
        )
        if rule is not None:
            return rule, found
    raise LookupError(f"due_date_rules:{form}")


async def _holidays(as_of: date) -> tuple[frozenset[date], list[UUID]]:
    days: set[date] = set()
    ids: list[UUID] = []
    for found in await references_in_effect("legal_holidays", as_of):
        days.update(row.date for row in cast(LegalHolidaysPayload, found.payload).rows)
        ids.append(found.version_id)
    return frozenset(days), ids


async def _roll_as_of(latest: date) -> date:
    return max(await today(), latest + _ROLL_MARGIN)


async def due_dates_for(
    form: str,
    tax_year: int,
    period_end: date,
    jurisdiction: str = "US",
    location: Location | None = None,
    event_date: date | None = None,
) -> DueDates:
    """The original and extended due dates for a form and period end, from the rules in effect
    on the period end (C21 `as_of` rule). Unknown form: `LookupError`."""
    rule, rules = await _rule_for(form, tax_year, period_end)
    unrolled = calendar.due_dates(rule, period_end, frozenset())
    as_of = await _roll_as_of(unrolled.extended_due_on or unrolled.original_due_on)
    holidays, holiday_ids = await _holidays(as_of)
    postponements: list[calendar.Postponement] = []
    postponement_ids: list[UUID] = []
    place: calendar.Place | None = None
    if location is not None:
        place = calendar.Place(location.state, location.county)
        for found in await references_in_effect("disaster_postponements", as_of):
            postponements += _postponements(cast(DisasterPostponementsPayload, found.payload))
            postponement_ids.append(found.version_id)
    dates = calendar.due_dates(rule, period_end, holidays, postponements, place, event_date)
    version_ids = (rules.version_id, *sorted(holiday_ids), *sorted(postponement_ids))
    return DueDates(
        form=form,
        tax_year=tax_year,
        period_end=period_end,
        jurisdiction=jurisdiction,
        original_due_on=dates.original_due_on,
        original_rolled=dates.original_rolled,
        extension_form=dates.extension_form,
        extended_due_on=dates.extended_due_on,
        extended_rolled=dates.extended_rolled,
        postponement_notice_id=dates.postponement_notice_id,
        reference_set_version_ids=version_ids,
        postponed_to=dates.postponed_to,
        inputs_hash=calendar.inputs_hash(
            {
                "form": form,
                "tax_year": tax_year,
                "period_end": period_end,
                "jurisdiction": jurisdiction,
                "location": None if place is None else [place.state, place.county],
                "event_date": event_date,
                "reference_set_version_ids": [str(v) for v in version_ids],
            }
        ),
    )


async def add_business_days(start: date, n: int, jurisdiction: str = "US") -> date:
    """`start` plus `n` business days, skipping weekends and the legal holidays in effect
    (federal and DC; `jurisdiction` is kept for state holidays, T-08)."""
    # Two calendar days per business day covers every weekend and holiday run.
    holidays, _ = await _holidays(await _roll_as_of(start + timedelta(days=2 * max(n, 0))))
    return calendar.add_business_days(start, n, holidays)


def clock_due(kind: ClockKind, start: date) -> ClockDue:
    """A calendar-day clock: +60 (AU-C 230, 265), +30 (FTC), 3 years (8879 retention, from the
    later of the due date and the IRS received date); never rolled."""
    return ClockDue(kind=kind, start=start, due_on=calendar.clock_due(kind, start))
