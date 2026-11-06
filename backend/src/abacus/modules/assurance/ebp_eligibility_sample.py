"""EBP-03's sample read (A-05-T23; A-05 §3 F4; DEC-2225, DEC-2328).

The eligibility test's rows in A-03's order: the census against the HR roster, code's entry date,
the row's result from the shared grid, and code's missed amounts on an exception. Code opens a date
of birth only to compute the entry date, and no row discloses one: `dob_masked` is a constant, and
`eligible_on` is shown only where hire + 3 months governs (the later of that and age 21), so it can
never be read back to a birthday. Nothing here is logged or written.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.crypto import open_sealed
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.assurance.compute.ebp import eligibility
from abacus.modules.assurance.ebp_contract import (
    EligibilityResult,
    EligibilitySampleOut,
    EligibilitySampleRowOut,
)
from abacus.modules.assurance.ebp_participants import binding
from abacus.modules.engagements.api import assurance_item, engagement_metadata, get_ref
from abacus.modules.identity.api import AuthContext, allowed_actions, names_of
from abacus.modules.review.api import sign_off_states
from abacus.modules.workpapers.api import ATTRIBUTE_TEST, grid, latest_test_of_variant

VARIANT: Final = "ebp_eligibility"
MASKED: Final = "••/••/••••"
_LATEST: Final = text(
    "SELECT p.id, p.participant_key, p.name, p.hire_on, p.dob_sealed, p.import_id, "
    "p.compensation, p.deferral_election_pct FROM ebp_participants p WHERE p.work_item_id = :w "
    "AND p.import_id = (SELECT i.id FROM ebp_source_imports i WHERE i.work_item_id = :w "
    "AND i.kind = :kind AND i.status = 'imported' ORDER BY i.created_at DESC LIMIT 1)"
)


@dataclass(frozen=True)
class _Person:
    id: UUID
    key: str
    name: str
    hire_on: date | None
    dob_sealed: bytes | None
    import_id: UUID
    compensation: Decimal | None
    election: Decimal | None


async def _people(tenant: TenantContext, work_item_id: UUID, kind: str) -> dict[str, _Person]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_LATEST, {"w": work_item_id, "kind": kind})).all()
    return {
        r.participant_key: _Person(
            r.id,
            r.participant_key,
            r.name,
            r.hire_on,
            None if r.dob_sealed is None else bytes(r.dob_sealed),
            r.import_id,
            r.compensation,
            r.deferral_election_pct,
        )
        for r in rows
    }


async def _dob(tenant: TenantContext, person: _Person) -> date | None:
    if person.dob_sealed is None:
        return None
    opened = await open_sealed(
        tenant.tenant_id, person.dob_sealed, binding(person.import_id, person.key, "dob")
    )
    return date.fromisoformat(opened.decode())


def eligible_shown(entry: eligibility.Entry, hire_on: date) -> date | None:
    """Only where hire + 3 months governs: otherwise the date is the 21st birthday (DEC-2225)."""
    return entry.eligible_on if entry.eligible_on == eligibility.add_months(hire_on, 3) else None


def rate_label(
    election: Decimal | None, entry_on: date | None, year: int, *, flagged: bool
) -> str:
    """ "8% elected", "6% default" (code's escalated rate), "0% — no opt-out" on an exception."""
    if election is None:
        if entry_on is None:
            return ""
        return f"{eligibility.escalation_rate(entry_on, year).normalize():f}% default"
    if election == 0:
        return "0% — no opt-out" if flagged else "0%"
    return f"{election.normalize():f}% elected"


def _iso(value: object) -> date | None:
    try:
        return None if value is None else date.fromisoformat(str(value))
    except ValueError:
        return None


def _cell_value(cells: Mapping[str, Mapping[str, object] | None], key: str, field: str) -> object:
    return (cells.get(key) or {}).get(field)


async def _row(
    tenant: TenantContext,
    position: int,
    item_id: UUID,
    record_key: str,
    state: str,
    cells: Mapping[str, Mapping[str, object] | None],
    census: _Person | None,
    hr: _Person | None,
    year: int,
) -> EligibilitySampleRowOut:
    hire = census.hire_on if census else None
    dob = await _dob(tenant, census) if census else None
    entry = None if dob is None or hire is None else eligibility.entry(dob, hire)
    flagged = state == "exception"
    gone = None if census else "Not on the census"
    review = (
        eligibility.review(dob, hire, hr.hire_on)
        if dob is not None and hire is not None and hr is not None and hr.hire_on is not None
        else None
    )
    missed = (
        eligibility.missed(census.compensation)
        if flagged and census is not None and census.election == 0 and census.compensation
        else None
    )
    version = _cell_value(cells, "hire_date", "hr_record_version_id")
    return EligibilitySampleRowOut(
        position=position,
        item_id=item_id,
        participant_id=census.id if census else item_id,
        record_key=record_key,
        census_name=census.name if census else record_key,
        hr_first_name=hr.name.split()[0] if hr and hr.name.split() else None,
        dob_masked=MASKED,
        census_hire=hire,
        hr_hire=hr.hire_on if hr else None,
        eligible_on=None if entry is None or hire is None else eligible_shown(entry, hire),
        entry_on=None if entry is None else entry.entry_on,
        recordkeeper_entry_on=_iso(_cell_value(cells, "entry_date", "recordkeeper_entry_on")),
        rate_label=rate_label(
            census.election if census else None,
            None if entry is None else entry.entry_on,
            year,
            flagged=flagged,
        ),
        result=cast(EligibilityResult, state),
        note=gone or (review.note if review else None),
        hr_record_version_id=None if version is None else UUID(str(version)),
        missed_deferral=None if missed is None else missed.deferral,
        missed_match=None if missed is None else missed.match,
    )


async def _can(ctx: AuthContext, engagement_id: UUID) -> list[str]:
    ref = await get_ref(ctx, engagement_id)
    return sorted(await allowed_actions(ctx, ref.resource(), ("test.mark", "finding.create")))


async def sample(ctx: AuthContext, work_item_id: UUID) -> EligibilitySampleOut:
    """The route authorised `ebp.read`. No test yet is no rows: EBP-03's empty state."""
    item = await assurance_item(ctx.tenant, work_item_id)
    found = await latest_test_of_variant(ctx.tenant, work_item_id, VARIANT)
    if found is None:
        return EligibilitySampleOut(
            test_id=None,
            version_no=1,
            rows=[],
            exceptions=0,
            needs_human=0,
            allowed_actions=await _can(ctx, item.engagement_id),
        )
    test_id, content_hash = found
    table = await grid(ctx, item.engagement_id, test_id)
    meta = await engagement_metadata(ctx, item.engagement_id)
    year = meta.engagement.fiscal_period_end.year
    census = await _people(ctx.tenant, work_item_id, "census")
    roster = await _people(ctx.tenant, work_item_id, "hr_roster")
    rows = [
        await _row(
            ctx.tenant,
            row.position,
            row.item_id,
            row.record_key,
            row.state,
            {c.attribute_key: c.value for c in row.cells},
            census.get(row.record_key),
            roster.get(row.record_key),
            year,
        )
        for row in table.rows
    ]
    states = (
        await sign_off_states(ctx.tenant, ATTRIBUTE_TEST, [test_id], {test_id: content_hash})
    )[test_id]
    signed = {s.level: s.signed_by for s in states if s.signed_by is not None and not s.stale}
    names = await names_of(list(signed.values()))

    def initials(level: int) -> str | None:
        by = signed.get(level)
        if by is None:
            return None
        return "".join(part[0] for part in names.get(by, "").split())[:4] or None

    return EligibilitySampleOut(
        test_id=test_id,
        version_no=table.version_no,
        rows=rows,
        exceptions=sum(1 for r in rows if r.result == "exception"),
        needs_human=sum(1 for r in rows if r.result == "needs_human"),
        prepared_by=initials(1),
        reviewed_by=initials(2),
        workpaper_id=table.workpaper_id,
        allowed_actions=await _can(ctx, item.engagement_id),
    )
