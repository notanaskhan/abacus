"""C21 part A, the service: due dates and clocks (K-02-T07; K-02 §3 F2, §4.5).

Reads the published reference sets through `platform.api` and hands their rows to the pure
engine in `compute/calendar.py`. Which version answers (C21 `as_of`, DEC-1255):

- Due-date rules on the period end; a set whose version names the return's tax year comes before
  one that doesn't, then the latest effective.
- Legal holidays and disaster postponements on the later of today (business time) and a fortnight
  past the latest unrolled due date, so the year's holiday list is in effect when a date rolls
  and a postponement published mid-season reaches every return it covers. A federal date counts
  every federal and DC holiday (IRC §7503; QK-5); a state's date counts the federal holidays and
  that state's own (T-08-T24, DEC-5919), and a version contributes only the rows it counted.

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
from abacus.modules.practice.due_dates_contract import (
    ClockDue,
    DueDates,
    InstallmentDue,
    InstallmentDueDates,
    Location,
)

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
            installments=tuple(
                (i.quarter, i.months_after_period_end, i.day) for i in row.installments
            ),
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


FEDERAL: Final = frozenset({"US", "DC"})


def counted(row_jurisdiction: str, jurisdiction: str) -> bool:
    """IRC §7503 for federal dates counts federal and DC holidays (QK-5); a state's date counts
    the federal holidays and that state's own (T-08-T24, DEC-5919). A state's holiday never
    rolls a federal date or another state's."""
    if jurisdiction in ("US", "federal"):
        return row_jurisdiction in FEDERAL
    return row_jurisdiction in ("US", jurisdiction.upper())


async def _holidays(as_of: date, jurisdiction: str = "US") -> tuple[frozenset[date], list[UUID]]:
    days: set[date] = set()
    ids: list[UUID] = []
    for found in await references_in_effect("legal_holidays", as_of):
        rows = [
            row for row in cast(LegalHolidaysPayload, found.payload).rows
            if counted(row.jurisdiction, jurisdiction)
        ]  # fmt: skip
        if rows:
            days.update(row.date for row in rows)
            ids.append(found.version_id)
    return frozenset(days), ids


async def federal_holidays(as_of: date) -> frozenset[date]:
    """T-08-T44: the federal and DC holidays in effect on `as_of` (an internal target never falls
    on one)."""
    days, _ids = await _holidays(as_of, "US")
    return days


async def _roll_as_of(latest: date) -> date:
    return max(await today(), latest + _ROLL_MARGIN)


async def due_dates_for(
    form: str,
    tax_year: int,
    period_end: date,
    jurisdiction: str = "US",
    location: Location | None = None,
    event_date: date | None = None,
    *,
    tenant_id: UUID | None = None,
    client_id: UUID | None = None,
) -> DueDates:
    """The original and extended due dates for a form and period end, from the rules in effect
    on the period end (C21 `as_of` rule). Unknown form: `LookupError`. With `tenant_id`, the
    firm's DF-10 overrides on top (T-08-T44): the internal target for the form and, with
    `client_id`, the client's relief applications, each version pinned."""
    rule, rules = await _rule_for(form, tax_year, period_end)
    found = await _dates_under(
        rule, rules, form, tax_year, period_end, jurisdiction, location, event_date
    )
    return found if tenant_id is None else await _with_overrides(found, tenant_id, client_id)


async def _with_overrides(found: DueDates, tenant_id: UUID, client_id: UUID | None) -> DueDates:
    from dataclasses import replace

    from abacus.kernel.db import TenantContext
    from abacus.modules.practice import deadline_overrides as df10

    as_of = await today()
    overrides = await df10.overrides_in_effect(tenant_id, as_of)
    pins = list(found.reference_set_version_ids)
    due = found.original_due_on
    notice_id, postponed_to, postponed_from = (
        found.postponement_notice_id, found.postponed_to, None,
    )  # fmt: skip
    if client_id is not None:
        tenant = TenantContext(tenant_id, "system", "practice:due_dates_overrides")
        best: tuple[date, df10.Application] | None = None
        for app in (await df10.applications(tenant, as_of, client_id)).get(client_id, []):
            to = df10.postponed(found.original_due_on, postponed_to or due, app.notice)
            if to is not None and (best is None or to > best[0]):
                best = (to, app)
        if best is not None:
            postponed_from = postponed_to or due
            postponed_to, notice_id = best[0], best[1].notice.notice_id
            pins.append(best[1].notice.version_id)
    target = None
    if overrides is not None and found.form in overrides.offsets:
        target = df10.internal_target(
            postponed_to or due, overrides.offsets[found.form], overrides.closures,
            await federal_holidays(as_of),
        )  # fmt: skip
        pins.append(overrides.version_id)
    pinned = tuple(dict.fromkeys(pins))
    return replace(
        found,
        postponement_notice_id=notice_id,
        postponed_to=postponed_to,
        postponed_from=postponed_from,
        internal_target_on=target,
        reference_set_version_ids=pinned,
        inputs_hash=calendar.inputs_hash(
            {"base": found.inputs_hash, "client": None if client_id is None else str(client_id),
             "reference_set_version_ids": [str(v) for v in pinned]}
        ),
    )  # fmt: skip


async def due_dates_for_extension(
    extension_form: str, tax_year: int, period_end: date, jurisdiction: str
) -> DueDates:
    """The dates of the rule that extends with this form (T-03 §4.2: a state line's form must be
    one the published rules name, and those rules give its dates). None names it: `LookupError`."""
    sets = await references_in_effect("due_date_rules", period_end)
    sets.sort(key=lambda r: r.tax_year != tax_year)
    for found in sets:
        rule = calendar.pick_extension_rule(
            _rules(cast(DueDateRulesPayload, found.payload)), extension_form, period_end
        )
        if rule is not None:
            return await _dates_under(
                rule, found, rule.form, tax_year, period_end, jurisdiction, None, None
            )
    raise LookupError(f"due_date_rules:{extension_form}")


async def _dates_under(
    rule: calendar.Rule,
    rules: ResolvedReference,
    form: str,
    tax_year: int,
    period_end: date,
    jurisdiction: str,
    location: Location | None,
    event_date: date | None,
) -> DueDates:
    unrolled = calendar.due_dates(rule, period_end, frozenset())
    as_of = await _roll_as_of(unrolled.extended_due_on or unrolled.original_due_on)
    holidays, holiday_ids = await _holidays(as_of, jurisdiction)
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
        rule_text=calendar.rule_text(rule, extended=False),
        extended_rule_text=calendar.rule_text(rule, extended=True),
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


async def installments_for(
    form: str, tax_year: int, jurisdiction: str = "US", period_end: date | None = None
) -> InstallmentDueDates:
    """C21 additive (T-03-T04): an estimate form's installment due dates for a tax year, from the
    rules in effect on the period end (Dec 31 of the tax year unless given), rolled with the
    holidays in effect. A form with no installments in effect: `LookupError`."""
    end = period_end or date(tax_year, 12, 31)
    rule, rules = await _rule_for(form, tax_year, end)
    if not rule.installments:
        raise LookupError(f"installments:{form}")
    unrolled = calendar.installment_dates(rule, end, frozenset())
    holidays, holiday_ids = await _holidays(
        await _roll_as_of(max(i.due_on for i in unrolled)), jurisdiction
    )
    found = calendar.installment_dates(rule, end, holidays)
    version_ids = (rules.version_id, *sorted(holiday_ids))
    return InstallmentDueDates(
        form=form,
        tax_year=tax_year,
        jurisdiction=jurisdiction,
        period_end=end,
        installments=tuple(InstallmentDue(i.quarter, i.due_on, i.rolled) for i in found),
        reference_set_version_ids=version_ids,
        inputs_hash=calendar.inputs_hash(
            {
                "form": form,
                "tax_year": tax_year,
                "period_end": end,
                "jurisdiction": jurisdiction,
                "reference_set_version_ids": [str(v) for v in version_ids],
            }
        ),
    )


async def add_business_days(start: date, n: int, jurisdiction: str = "US") -> date:
    """`start` plus `n` business days, skipping weekends and the legal holidays in effect
    (federal and DC; a state's own as well for its `jurisdiction`, T-08-T24)."""
    # Two calendar days per business day covers every weekend and holiday run.
    holidays, _ = await _holidays(
        await _roll_as_of(start + timedelta(days=2 * max(n, 0))), jurisdiction
    )
    return calendar.add_business_days(start, n, holidays)


async def business_days_between(start: date, end: date, jurisdiction: str = "US") -> int:
    """C-01-T14 (AC-3, QC-7): the business days after `start` up to and including `end`, by
    the same calendar as `add_business_days` (0 when `end` is not after `start`). A close due
    Thu Sep 10 is 2 business days past due on Mon Sep 14 by the calendar; the close engine counts
    past due this way."""
    if end <= start:
        return 0
    holidays, _ = await _holidays(await _roll_as_of(end), jurisdiction)
    return sum(
        calendar.is_business_day(start + timedelta(days=d), holidays)
        for d in range(1, (end - start).days + 1)
    )


def clock_due(kind: ClockKind, start: date) -> ClockDue:
    """A calendar-day clock: +60 (AU-C 230, 265), +30 (FTC), 3 years (8879 retention, from the
    later of the due date and the IRS received date); never rolled."""
    return ClockDue(kind=kind, start=start, due_on=calendar.clock_due(kind, start))
