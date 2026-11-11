"""A-07 in shadow (Q-04-T136; DEC-3305): what the dark A-07 code computes for one engagement,
read-only, so a firm still releasing and archiving in its own tool (`assurance_release_mode =
external`) can compare it with what that tool did ahead of M16. Nothing here writes, flips a
flag or moves a phase; the gates are their providers' own answers.

The comparison itself is the operator's (`abacus_tools.a07_shadow`), against a file of the firm
tool's dates. Code computes; a person reads the differences (ADR-050).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from uuid import UUID

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.assurance.archive_gate import archive_state
from abacus.modules.assurance.external_models import external_archive_of, external_release_of
from abacus.modules.assurance.release import DOCUMENTATION_DAYS, release_mode, released, snapshot


@dataclass(frozen=True)
class ShadowFacts:
    work_item_id: UUID
    engagement_id: UUID
    release_mode: str
    gates: tuple[tuple[str, bool], ...]  # G5 to G7, met or not
    also_required: tuple[tuple[str, bool], ...]
    report_approved: bool
    report_date: date | None
    released_on: date | None  # in-app (G8) or the recorded external release
    released_how: str | None  # "in_app" | "recorded" | None
    documentation_completion_date: date | None
    archive_checklist: tuple[int, int] | None  # done, total, once an archive is open
    archived_on: date | None  # in-app lock or the recorded external archive
    archived_how: str | None


async def shadow_facts(tenant: TenantContext, work_item_id: UUID) -> ShadowFacts:
    snap = await snapshot(tenant, work_item_id)
    mode = await release_mode(tenant)
    done = await released(tenant, work_item_id)
    async with tenant_session(tenant) as session:
        external = await external_release_of(session, snap.engagement_id)
        recorded_archive = await external_archive_of(session, snap.engagement_id)
    released_on: date | None = None
    how: str | None = None
    if done is not None:
        released_on = done.released_at.astimezone(clock.FIRM_ZONE).date()
        how = "in_app"
    elif external is not None:
        released_on = external.report_released_on
        how = "recorded"
    state = await archive_state(tenant, work_item_id)
    archive = state.archive
    archived_on: date | None = None
    archived_how: str | None = None
    if archive is not None and archive.locked_at is not None:
        archived_on = archive.locked_at.astimezone(clock.FIRM_ZONE).date()
        archived_how = "in_app"
    elif recorded_archive is not None:
        archived_on = recorded_archive.recorded_at.astimezone(clock.FIRM_ZONE).date()
        archived_how = "recorded"
    return ShadowFacts(
        work_item_id=work_item_id,
        engagement_id=snap.engagement_id,
        release_mode=mode,
        gates=tuple((g.gate, g.met) for g in snap.gates),
        also_required=tuple((a.key, a.met) for a in snap.also_required),
        report_approved=snap.report_approved,
        report_date=snap.report_date,
        released_on=released_on,
        released_how=how,
        documentation_completion_date=(
            None if released_on is None else released_on + timedelta(days=DOCUMENTATION_DAYS)
        ),
        archive_checklist=(
            None if archive is None else (sum(i.done for i in state.items), len(state.items))
        ),
        archived_on=archived_on,
        archived_how=archived_how,
    )
