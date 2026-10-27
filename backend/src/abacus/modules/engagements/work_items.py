"""Work items (F-03-T05; migration 0068): the units of work inside an engagement.

Every engagement holds one `assurance` work item and one primary entity from its creation (the
`engagement_work_item_defaults` trigger). Other kinds (returns, closes, notices, advisory
projects) register with their modules as they arrive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final, cast
from uuid import UUID

from sqlalchemy import ColumnElement, func, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.listing import (
    ListPage,
    capped_total,
    clamp_limit,
    decode_cursor,
    envelope,
    keyset,
    page_of,
    query_hash,
    status_counts,
)
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.models import AssuranceWorkItem, Engagement, WorkItem
from abacus.modules.engagements.record import GateUnmet
from abacus.modules.engagements.service import client_of, get_ref, lock_ref
from abacus.modules.engagements.setup import g2_blocks
from abacus.modules.engagements.slots import NewWorkItem, work_item_provider
from abacus.modules.identity.api import (
    AuthContext,
    assert_assignable,
    authorise,
    team_standing,
    visible,
    visible_scope,
)
from abacus.modules.organisations.api import client_name_column


@dataclass(frozen=True)
class WorkItemView:
    id: UUID
    kind: str
    name: str
    status: str
    period_start: date | None
    period_end: date | None
    due_on: date | None
    phase: str | None  # assurance only


async def work_items_of(ctx: AuthContext, engagement_id: UUID) -> list[WorkItemView]:
    """AC (C1): an engagement's work items, oldest first, through `visible()`."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "work_item.read_metadata", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(WorkItem, AssuranceWorkItem.phase)
                .outerjoin(AssuranceWorkItem, AssuranceWorkItem.work_item_id == WorkItem.id)
                .where(
                    WorkItem.engagement_id == engagement_id,
                    visible(ctx, "work_item.read_metadata", WorkItem.engagement_id),
                )
                .order_by(WorkItem.created_at)
            )
        ).all()
    return [
        WorkItemView(w.id, w.kind, w.name, w.status, w.period_start, w.period_end, w.due_on, phase)
        for w, phase in rows
    ]


@dataclass(frozen=True)
class PortalWorkItem:
    id: UUID
    engagement_id: UUID
    kind: str
    name: str
    due_on: date | None
    phase: str | None  # assurance only: the C2 `audit_engagement` code
    assurance_type: str | None
    client_name: str


# The work item column a portal grant's scope id names (F-03-T26 scope kinds that cover work).
_GRANT_COLUMN: Final[dict[str, QueryableAttribute[UUID]]] = {
    "client": WorkItem.client_id,
    # Compared only with a grant's scope id: a work item without an entity never matches.
    "client_entity": cast("QueryableAttribute[UUID]", WorkItem.client_entity_id),
    "engagement": WorkItem.engagement_id,
    "work_item": WorkItem.id,
}


async def portal_work_items(
    ctx: AuthContext, grant_kind: str, scope_id: UUID
) -> list[PortalWorkItem]:
    """P-08-T13 (POR-02): the live work items one of the person's portal grants covers, oldest
    first, through `visible_scope(..., "portal_scope")`. The caller still authorises
    `portal_home.read` per target (`scope_only`); a grant on another kind of scope covers none."""
    column = _GRANT_COLUMN.get(grant_kind)
    if column is None:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = (
            await session.execute(
                select(
                    WorkItem,
                    AssuranceWorkItem.phase,
                    AssuranceWorkItem.assurance_type,
                    client_name_column(WorkItem.client_id),
                )
                .outerjoin(AssuranceWorkItem, AssuranceWorkItem.work_item_id == WorkItem.id)
                .where(
                    column == scope_id,
                    WorkItem.status == "active",
                    visible_scope(
                        ctx, "portal_home.read", "portal_scope", column, grant_kind=grant_kind
                    ),
                )
                .order_by(WorkItem.created_at, WorkItem.id)
            )
        ).all()
    return [
        PortalWorkItem(w.id, w.engagement_id, w.kind, w.name, w.due_on, phase, kind, name)
        for w, phase, kind, name in rows
    ]


async def assurance_item_id(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The engagement's assurance work item (one per attest engagement, migration 0068). For a
    caller that has authorised on the engagement."""
    async with tenant_session(tenant) as session:
        return await session.scalar(
            select(WorkItem.id).where(
                WorkItem.engagement_id == engagement_id, WorkItem.kind == "assurance"
            )
        )


# --- A-01-T05 (0134): the assurance subtype's profile facts and phase projection ----------------
# The phase moves only through an `assurance_phase_events` row: the app role holds no UPDATE on
# `phase`, and the event's insert trigger moves the projection (DEC-262). The assurance module's
# phase service writes the events; nothing here sets a phase.


@dataclass(frozen=True)
class AssuranceItem:
    """An assurance work item's subtype row, for the assurance module's phase service."""

    work_item_id: UUID
    engagement_id: UUID
    assurance_type: str
    phase: str
    phase_source: str
    ebp_plan_kind: str | None
    limited_scope_103a3c: bool
    standards_set_id: UUID | None
    version: int


def _assurance_item(row: AssuranceWorkItem) -> AssuranceItem:
    return AssuranceItem(
        row.work_item_id,
        row.engagement_id,
        row.assurance_type,
        row.phase,
        row.phase_source,
        row.ebp_plan_kind,
        row.limited_scope_103a3c,
        row.standards_set_id,
        row.version,
    )


async def assurance_item(tenant: TenantContext, work_item_id: UUID) -> AssuranceItem:
    """The work item's assurance row; 404 when the tenant holds none (another tenant's id, or a
    work item of another kind). The caller authorises on the engagement before using it."""
    async with tenant_session(tenant) as session:
        row = await session.get(AssuranceWorkItem, work_item_id)
    if row is None:
        raise NotFound("work_item")
    return _assurance_item(row)


async def lock_assurance_item(tx: UnitOfWork, work_item_id: UUID) -> AssuranceItem:
    """The same row, locked for the caller's unit (one phase move or profile edit at a time)."""
    row = await tx.session.scalar(
        select(AssuranceWorkItem)
        .where(AssuranceWorkItem.work_item_id == work_item_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise NotFound("work_item")
    return _assurance_item(row)


async def set_assurance_profile(
    tx: UnitOfWork, work_item_id: UUID, values: Mapping[str, str | bool | UUID | None]
) -> int:
    """The EBP profile facts (`ebp_plan_kind`, `limited_scope_103a3c`, `standards_set_id`), in
    the caller's unit; the new version is returned."""
    allowed = {"ebp_plan_kind", "limited_scope_103a3c", "standards_set_id"}
    if not set(values) <= allowed:
        raise ValueError(f"not a profile fact: {sorted(set(values) - allowed)}")
    version = await tx.session.scalar(
        update(AssuranceWorkItem)
        .where(AssuranceWorkItem.work_item_id == work_item_id)
        .values(**values, version=AssuranceWorkItem.version + 1)
        .returning(AssuranceWorkItem.version)
    )
    if version is None:
        raise NotFound("work_item")
    return version


async def lock_engagement(tx: UnitOfWork, engagement_id: UUID, at: datetime) -> None:
    """SPEC-314 (G9): the archive is locked: the engagement becomes archived (read-only through
    `authorise`, AUTHZ-003) and its work items record when."""
    await tx.session.execute(
        update(WorkItem)
        .where(WorkItem.engagement_id == engagement_id)
        .values(archive_locked_at=at, archived_at=at)
    )
    await tx.session.execute(
        update(Engagement).where(Engagement.id == engagement_id).values(status="archived")
    )


async def archive_work_item(tx: UnitOfWork, work_item_id: UUID, at: datetime) -> bool:
    """A-01-T23 (C1's archived transition, record mode): the work item records `archived_at`
    (never `archive_locked_at`: this is not A-07's seal, P-43), and its engagement becomes
    archived, read-only through `authorise`, once every one of its work items is. Returns whether
    the engagement is now archived. In the caller's unit, which has locked the engagement."""
    engagement_id = await tx.session.scalar(
        update(WorkItem)
        .where(WorkItem.id == work_item_id, WorkItem.archived_at.is_(None))
        .values(archived_at=at)
        .returning(WorkItem.engagement_id)
    )
    if engagement_id is None:
        raise NotFound("work_item")
    open_items = await tx.session.scalar(
        select(func.count())
        .select_from(WorkItem)
        .where(WorkItem.engagement_id == engagement_id, WorkItem.archived_at.is_(None))
    )
    if open_items:
        return False
    await tx.session.execute(
        update(Engagement).where(Engagement.id == engagement_id).values(status="archived")
    )
    return True


# --- F-03-T22: creating work items of every kind ------------------------------------------------

_UNIQUE_VIOLATION: Final = "23505"


class WorkItemExists(DomainConflict):
    """The kind allows no second one here: another assurance item on the engagement, another close
    for the same period (409)."""

    code = "work_item_exists"


async def create_work_item(
    ctx: AuthContext,
    engagement_id: UUID,
    kind: str,
    *,
    name: str,
    client_entity_id: UUID | None = None,
    due_on: date | None = None,
    details: Mapping[str, str | int | date | None] | None = None,
) -> UUID:
    """A new work item of `kind` on the engagement, with its kind's subtype row, in one unit of
    work. The kind's owner registered it (an unregistered kind is 409 unknown_work_item_kind);
    its cardinality rule (one assurance item per engagement, one close per period) answers 409
    `work_item_exists`."""
    provider = work_item_provider(kind)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "work_item.create", ref.resource())
        try:
            async with tx.session.begin_nested():
                created = await tx.session.execute(
                    insert(WorkItem)
                    .values(
                        tenant_id=ctx.tenant_id,
                        engagement_id=engagement_id,
                        client_id=ref.client_id,
                        client_entity_id=client_entity_id,
                        kind=kind,
                        name=name,
                        due_on=due_on,
                        created_by=ctx.user_id,
                    )
                    .returning(WorkItem.id)
                )
                work_item_id = created.scalar_one()
                await provider.create(
                    tx,
                    NewWorkItem(
                        ctx.tenant_id, work_item_id, engagement_id, client_entity_id, details or {}
                    ),
                )
        except IntegrityError as exc:
            if getattr(exc.orig, "sqlstate", None) == _UNIQUE_VIOLATION:
                raise WorkItemExists(facts={"kind": kind}) from None
            raise
        tx.record("work_item.created", target=Target("engagement", engagement_id))
    return work_item_id


# --- P-07-T24: assigning a function on a work item, behind G2 v2 (ADR-164 item 2) -------------


# Migration 0068's CHECK on `work_item_assignments.function` (the matrix's `function_in` codes).
WORK_ITEM_FUNCTIONS: Final = frozenset(
    {
        "preparer",
        "first_level_reviewer",
        "detail_reviewer",
        "manager_reviewer",
        "signer",
        "eqr",
        "close_preparer",
        "close_reviewer",
        "project_lead",
        "specialist",
    }
)
_ASSIGN = text(
    "INSERT INTO work_item_assignments "
    "(tenant_id, work_item_id, engagement_id, user_id, function, assigned_by) "
    "VALUES (:tenant_id, :work_item_id, :engagement_id, :user_id, :function, :assigned_by)"
)


# G-01-T09 (AC8.5): a person's current assignments on a client's engagements (an assignment row
# no later removal row undoes), and their ending by the `wall.created` consumer.
_CURRENT_ON_CLIENT = text(
    "SELECT a.work_item_id, a.engagement_id, a.function FROM work_item_assignments a "
    "JOIN engagements e ON e.id = a.engagement_id "
    "WHERE a.user_id = :user_id AND e.client_id = :client_id AND a.removed_at IS NULL "
    "AND NOT EXISTS (SELECT 1 FROM work_item_assignments r "
    "WHERE r.work_item_id = a.work_item_id AND r.user_id = a.user_id "
    "AND r.function = a.function AND r.removed_at IS NOT NULL "
    "AND r.assigned_at >= a.assigned_at) "
    "ORDER BY a.engagement_id, a.work_item_id, a.function"
)
_UNASSIGN = text(
    "INSERT INTO work_item_assignments "
    "(tenant_id, work_item_id, engagement_id, user_id, function, assigned_by, removed_at) "
    "VALUES (:tenant_id, :work_item_id, :engagement_id, :user_id, :function, :assigned_by, "
    "abacus_now())"
)


async def wall_assignment_count(tenant: TenantContext, user_id: UUID, client_id: UUID) -> int:
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            _CURRENT_ON_CLIENT, {"user_id": user_id, "client_id": client_id}
        )
        return len(rows.all())


async def end_wall_assignments(
    tx: UnitOfWork, tenant_id: UUID, user_id: UUID, client_id: UUID, on_behalf_of: UUID
) -> int:
    """In the consumer's unit of work (the system, on behalf of the wall's creator): one removal
    row and one `work_item.unassigned` audit row per current assignment. Idempotent."""
    rows = (
        await tx.session.execute(_CURRENT_ON_CLIENT, {"user_id": user_id, "client_id": client_id})
    ).all()
    for work_item_id, engagement_id, function in rows:
        await tx.session.execute(
            _UNASSIGN,
            {
                "tenant_id": tenant_id,
                "work_item_id": work_item_id,
                "engagement_id": engagement_id,
                "user_id": user_id,
                "function": function,
                "assigned_by": on_behalf_of,
            },
        )
        tx.record(
            "work_item.unassigned",
            target=Target("engagement", engagement_id),
            after=Ref(user_id=user_id, work_item_id=work_item_id),
        )
    return len(rows)


async def assign_work_item(
    ctx: AuthContext, work_item_id: UUID, user_id: UUID, function: str
) -> None:
    """Assign `user_id` the `function` on the work item, in one unit of work with its audit event.
    The assignee must be a staff member of the engagement's team and not walled from its client:
    otherwise 404, the same answer for both so a wall is never revealed (P-07-T30, ED-042). The
    `eqr` function goes to the engagement's EQR only, and the EQR takes no other (422).
    Refused 409 `gate_unmet` (`gate` G2, `user_id`) when the engagement's client is an attest
    client and that person is not cleared on the engagement (`setup.g2_blocks`); a non-attest
    client's engagement is never gated. An unknown function is 422; an unknown or walled work
    item is 404. ENG-05's routes (P-07-T30) call it."""
    if function not in WORK_ITEM_FUNCTIONS:
        raise DomainInvalid(facts={"field": "function"})
    async with tenant_session(ctx.tenant) as session:
        engagement_id = await session.scalar(
            select(WorkItem.engagement_id).where(WorkItem.id == work_item_id)
        )
    if engagement_id is None:
        raise NotFound
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "work_item.assign", ref.resource())
        standing = await team_standing(ctx.tenant, engagement_id, user_id)
        if standing in ("none", "client"):
            raise NotFound("team_member")
        client_id = await client_of(ctx.tenant, engagement_id)
        if client_id is None:
            raise NotFound
        # G-01-T09 (AC9.3): walled people aren't assignable (404); offshore without consent 409.
        await assert_assignable(ctx.tenant, user_id, client_id)
        # The `eqr` function is the EQR's, and the EQR's only function (security review, DEC-327).
        if (standing == "eqr") != (function == "eqr"):
            raise DomainInvalid(facts={"field": "function"})
        if await g2_blocks(ctx.tenant, engagement_id, user_id):
            raise GateUnmet(facts={"gate": "G2", "user_id": str(user_id)})
        await tx.session.execute(
            _ASSIGN,
            {
                "tenant_id": ctx.tenant_id,
                "work_item_id": work_item_id,
                "engagement_id": engagement_id,
                "user_id": user_id,
                "function": function,
                "assigned_by": ctx.user_id,
            },
        )
        tx.record("work_item.assigned", target=Target("engagement", engagement_id))


class AssuranceKind:
    """The `assurance` kind: its subtype row (one per engagement; the trigger makes the first)."""

    async def status(self, tenant: TenantContext, work_item_id: UUID) -> str:
        return "active"

    async def create(self, tx: UnitOfWork, item: NewWorkItem) -> None:
        await tx.session.execute(
            insert(AssuranceWorkItem).values(
                work_item_id=item.work_item_id,
                tenant_id=item.tenant_id,
                engagement_id=item.engagement_id,
                assurance_type=item.details.get("assurance_type") or "fs_audit",
            )
        )


_ADVISORY = text(
    "INSERT INTO advisory_projects (tenant_id, work_item_id, engagement_id, name) "
    "VALUES (:tenant_id, :work_item_id, :engagement_id, :name)"
)


class AdvisoryProjectKind:
    """The `advisory_project` kind: a project's name (F-03-T22)."""

    async def status(self, tenant: TenantContext, work_item_id: UUID) -> str:
        return "active"

    async def create(self, tx: UnitOfWork, item: NewWorkItem) -> None:
        await tx.session.execute(
            _ADVISORY,
            {
                "tenant_id": item.tenant_id,
                "work_item_id": item.work_item_id,
                "engagement_id": item.engagement_id,
                "name": item.details.get("name") or "Advisory project",
            },
        )


# --- F-03-T31: the firm-wide work-item list (C1 live) -------------------------------------------


@dataclass(frozen=True)
class WorkItemRow:
    id: UUID
    engagement_id: UUID
    kind: str
    name: str
    status: str
    period_start: date | None
    period_end: date | None
    due_on: date | None
    created_at: datetime


async def list_work_items(
    ctx: AuthContext,
    *,
    engagement_id: UUID | None = None,
    kind: str | None = None,
    status: str | None = None,
    cursor: str | None = None,
    limit: int | None = None,
) -> ListPage[WorkItemRow]:
    """Work items the person may read, newest first, on the list envelope with per-status counts
    (the status filter left out of them). Live for every firm (P-07-T15 retired
    `engagements.work_items_api`)."""
    size = clamp_limit(limit)
    query = query_hash(engagement_id=engagement_id, kind=kind, status=status)
    after = (
        decode_cursor(cursor, tenant_id=ctx.tenant_id, resource="work_items", query=query)
        if cursor
        else None
    )
    base = select(WorkItem).where(
        visible_scope(ctx, "work_item.read_metadata", "work_item", WorkItem.engagement_id)
    )
    if engagement_id is not None:
        base = base.where(WorkItem.engagement_id == engagement_id)
    if kind is not None:
        base = base.where(WorkItem.kind == kind)
    filtered = base if status is None else base.where(WorkItem.status == status)
    async with tenant_session(ctx.tenant) as session:
        counts = await status_counts(session, base, WorkItem.status.expression)
        total = await capped_total(session, filtered)
        fetched = (
            (
                await session.execute(
                    keyset(
                        filtered,
                        sort=cast(ColumnElement[object], WorkItem.created_at.expression),
                        id_column=cast(ColumnElement[object], WorkItem.id.expression),
                        after=after,
                        descending=True,
                        limit=size,
                    )
                )
            )
            .scalars()
            .all()
        )
    page, next_position = page_of(
        fetched, limit=size, key=lambda w: w.created_at, id_of=lambda w: w.id
    )
    rows = [
        WorkItemRow(
            w.id,
            w.engagement_id,
            w.kind,
            w.name,
            w.status,
            w.period_start,
            w.period_end,
            w.due_on,
            w.created_at,
        )
        for w in page
    ]
    return envelope(
        rows,
        next_position=next_position,
        tenant_id=ctx.tenant_id,
        resource="work_items",
        query=query,
        total=total,
        counts=counts,
    )


async def holds_tax_return(tenant: TenantContext, engagement_id: UUID) -> bool:
    """For the gateway (P-06-T20 security review; DEC-324): whether the engagement holds a
    `tax_return` work item, whose content is tax-return information (§7216)."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            select(WorkItem.id)
            .where(WorkItem.engagement_id == engagement_id, WorkItem.kind == "tax_return")
            .limit(1)
        )
    return found is not None
