"""The work-item facts another module's list filters, groups and shows (P-06-T11; BND-01).

A binder hangs on a work item (DEC-31), so the binders index reads its service (the work item's
kind), season, office, preparer, client and name from here rather than from engagements' tables.
It is a subquery the list joins on `id`: it reads under the caller's session (RLS), and the
joining list applies `visible()` to its own rows (LIST-001), so it can show nothing that list
would hide.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Final
from uuid import UUID

from sqlalchemy import ColumnElement, Integer, Subquery, case, cast, column, func, select, table

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.models import (
    AssuranceWorkItem,
    Engagement,
    EngagementLetter,
    WorkItem,
)
from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.organisations.api import (
    client_name_column,
    entity_name_column,
    office_name_column,
)

_assignments = table(
    "work_item_assignments",
    column("tenant_id"),
    column("work_item_id"),
    column("user_id"),
    column("function"),
    column("assigned_at"),
    column("removed_at"),
)
PREPARER_FUNCTIONS: Final = ("preparer", "close_preparer")
_TAX_RETURN: Final = "tax_return"


def _preparer(work_item_id: ColumnElement[UUID]) -> ColumnElement[UUID]:
    """The person holding a preparer function now: the newest assignment that no later removal
    row undoes (assignments are insert-only; a removal is a new row with `removed_at`)."""
    added, removed = _assignments.alias("added"), _assignments.alias("removed")
    undone = (
        select(removed.c.user_id)
        .where(
            removed.c.work_item_id == added.c.work_item_id,
            removed.c.user_id == added.c.user_id,
            removed.c.function == added.c.function,
            removed.c.removed_at.is_not(None),
            removed.c.assigned_at >= added.c.assigned_at,
        )
        .exists()
    )
    return (
        select(added.c.user_id)
        .where(
            added.c.work_item_id == work_item_id,
            added.c.function.in_(PREPARER_FUNCTIONS),
            added.c.removed_at.is_(None),
            ~undone,
        )
        .order_by(added.c.assigned_at.desc())
        .limit(1)
        .correlate_except(added, removed)
        .scalar_subquery()
    )


def _season() -> ColumnElement[str | None]:
    """The season a list groups work by. A return's tax year is the year its period begins (a
    fiscal-year 990 for Jul 2025 to Jun 2026 is TY2025); other work reads its fiscal year end
    (FY2026). No period, no season."""
    start = cast(func.extract("year", WorkItem.period_start), Integer)
    end = cast(func.extract("year", WorkItem.period_end), Integer)
    return case(
        (
            (WorkItem.kind == _TAX_RETURN) & WorkItem.period_start.is_not(None),
            func.concat("TY", start),
        ),
        (
            (WorkItem.kind != _TAX_RETURN) & WorkItem.period_end.is_not(None),
            func.concat("FY", end),
        ),
        else_=None,
    )


def work_item_index() -> Subquery:
    """Per work item: `id`, `engagement_id`, `kind`, `name`, `client_id`, `client_name`,
    `office_id`, `office_name`, `season` and `preparer_user_id`."""
    return select(
        WorkItem.id.label("id"),
        WorkItem.engagement_id.label("engagement_id"),
        WorkItem.kind.label("kind"),
        WorkItem.name.label("name"),
        WorkItem.client_id.label("client_id"),
        client_name_column(WorkItem.client_id).label("client_name"),
        WorkItem.office_id.label("office_id"),
        office_name_column(WorkItem.office_id).label("office_name"),
        _season().label("season"),
        _preparer(WorkItem.id.expression).label("preparer_user_id"),
    ).subquery("work_item_index")


# --- A-01-T08: the AUD-01 audits index (docs/contracts/audits-cockpit.md §3) --------------------

# Engagements an audits row never shows: not yet engaged, or declined.
_NOT_ENGAGED: Final = ("prospect", "declined")


def assurance_index() -> Subquery:
    """Per assurance work item: `work_item_id`, `engagement_id`, `title` (the work item's
    name), `client_id`, `client_name`,
    `name` (the engagement's entity: "Northwind Robotics 401(k) Plan"), `type`, `status` (the
    engagement's), `period_label`, `period_end`, `methodology_version_id`, `phase`, `phase_source`,
    `phase_changed_at`, `ebp_plan_kind`, `limited_scope_103a3c`, `is_group_audit`,
    `standards_set_id`, `office_id`, `office_name`, `due_on`, `work_item_status`, `archived_at` and
    `archive_locked_at`, for engaged work only. Reads under the caller's session (RLS); the
    joining list applies `visible()` on `engagement_id` (LIST-001)."""
    return (
        select(
            WorkItem.id.label("work_item_id"),
            WorkItem.engagement_id.label("engagement_id"),
            WorkItem.name.label("title"),
            Engagement.client_id.label("client_id"),
            client_name_column(Engagement.client_id).label("client_name"),
            entity_name_column(Engagement.client_entity_id).label("name"),
            Engagement.type.label("type"),
            Engagement.status.label("status"),
            Engagement.period_label.label("period_label"),
            Engagement.fiscal_period_end.label("period_end"),
            Engagement.methodology_version_id.label("methodology_version_id"),
            AssuranceWorkItem.phase.label("phase"),
            AssuranceWorkItem.phase_source.label("phase_source"),
            AssuranceWorkItem.phase_changed_at.label("phase_changed_at"),
            AssuranceWorkItem.ebp_plan_kind.label("ebp_plan_kind"),
            AssuranceWorkItem.limited_scope_103a3c.label("limited_scope_103a3c"),
            AssuranceWorkItem.is_group_audit.label("is_group_audit"),
            AssuranceWorkItem.standards_set_id.label("standards_set_id"),
            func.coalesce(WorkItem.office_id, Engagement.office_id).label("office_id"),
            office_name_column(func.coalesce(WorkItem.office_id, Engagement.office_id)).label(
                "office_name"
            ),
            WorkItem.due_on.label("due_on"),
            WorkItem.status.label("work_item_status"),
            WorkItem.archived_at.label("archived_at"),
            WorkItem.archive_locked_at.label("archive_locked_at"),
        )
        .join(Engagement, Engagement.id == WorkItem.engagement_id)
        .join(AssuranceWorkItem, AssuranceWorkItem.work_item_id == WorkItem.id)
        .where(WorkItem.kind == "assurance", Engagement.status.not_in(_NOT_ENGAGED))
        .subquery("assurance_index")
    )


async def letters_sent(tenant: TenantContext, engagement_ids: Sequence[UUID]) -> dict[UUID, date]:
    """The engagements whose recorded letter is out and not yet signed (G3 unmet), with the date
    it went out ("Letter sent Sep 8"): the letter's date, else the day it was recorded. For a
    caller that read these engagements under `visible()`."""
    if not engagement_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(
                EngagementLetter.engagement_id,
                EngagementLetter.letter_date,
                EngagementLetter.recorded_at,
            ).where(
                EngagementLetter.engagement_id.in_(list(engagement_ids)),
                EngagementLetter.status == "sent",
            )
        )
    return {eid: on or at.date() for eid, on, at in rows.all()}


async def gate_offices(
    tenant: TenantContext, keys: Sequence[tuple[UUID, UUID | None]]
) -> dict[tuple[UUID, UUID | None], UUID]:
    """The office a human gate files under (I-01-T04; DEC-30: a filter, never a boundary): the
    work item's office, else the engagement's. Keyed by (engagement, work item or None); a key
    with no office is absent. For the gate projector, under its tenant session (RLS)."""
    wanted = {k for k in keys}
    if not wanted:
        return {}
    engagement_ids = sorted({e for e, _ in wanted}, key=str)
    item_ids = sorted({w for _, w in wanted if w is not None}, key=str)
    found: dict[tuple[UUID, UUID | None], UUID] = {}
    async with tenant_session(tenant) as session:
        by_engagement = dict(
            (
                await session.execute(
                    select(Engagement.id, Engagement.office_id).where(
                        Engagement.id.in_(engagement_ids)
                    )
                )
            ).all()
        )
        by_item: dict[UUID, tuple[UUID, UUID | None]] = {}
        if item_ids:
            for item, engagement, office in await session.execute(
                select(WorkItem.id, WorkItem.engagement_id, WorkItem.office_id).where(
                    WorkItem.id.in_(item_ids)
                )
            ):
                by_item[item] = (engagement, office)
    for engagement, item in wanted:
        office = None
        if item is not None and item in by_item and by_item[item][0] == engagement:
            office = by_item[item][1]
        office = office or by_engagement.get(engagement)
        if office is not None:
            found[(engagement, item)] = office
    return found


async def methodology_usage(ctx: AuthContext, version_ids: Sequence[UUID]) -> dict[UUID, int]:
    """KNW-01's "Used by n engagements" (K-01-T03; AC1.3, AC1.9): the engagements pinned to each
    methodology version that the reader may see (`visible()`, so a walled engagement is never
    counted). Registered as methodology's usage counter for `methodology_version`."""
    if not version_ids:
        return {}
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(Engagement.methodology_version_id, func.count())
            .where(
                Engagement.methodology_version_id.in_(list(version_ids)),
                visible(ctx, "engagement.read_metadata", Engagement.id),
            )
            .group_by(Engagement.methodology_version_id)
        )
    return {version: int(n) for version, n in rows.all() if version is not None}
