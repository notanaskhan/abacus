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

from sqlalchemy import ColumnElement, insert, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel._flags import ENGAGEMENTS_WORK_ITEMS_API
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
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
from abacus.kernel.uow import Target, UnitOfWork, uow
from abacus.modules.engagements.models import AssuranceWorkItem, Engagement, WorkItem
from abacus.modules.engagements.record import GateUnmet
from abacus.modules.engagements.service import get_ref, lock_ref
from abacus.modules.engagements.setup import g2_blocks
from abacus.modules.engagements.slots import NewWorkItem, work_item_provider
from abacus.modules.identity.api import (
    AuthContext,
    authorise,
    is_synthetic_firm,
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


async def set_assurance_phase(tx: UnitOfWork, engagement_id: UUID, phase: str) -> None:
    """SPEC-314: the assurance work item's phase (released, archived), in the caller's unit."""
    item = await tx.session.scalar(
        select(WorkItem.id).where(
            WorkItem.engagement_id == engagement_id, WorkItem.kind == "assurance"
        )
    )
    if item is not None:
        await tx.session.execute(
            update(AssuranceWorkItem)
            .where(AssuranceWorkItem.work_item_id == item)
            .values(phase=phase)
        )


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


async def assign_work_item(
    ctx: AuthContext, work_item_id: UUID, user_id: UUID, function: str
) -> None:
    """Assign `user_id` the `function` on the work item, in one unit of work with its audit event.
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


async def work_items_api_on(tenant: TenantContext) -> bool:
    """The C1 list's flag: on locally and in tests, for synthetic firms, or where it's set."""
    if settings().environment in ("local", "test"):
        return True
    if await is_synthetic_firm(tenant):
        return True
    return await flag_enabled(tenant, ENGAGEMENTS_WORK_ITEMS_API)


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
    (the status filter left out of them). `NotFound` while the flag is off."""
    if not await work_items_api_on(ctx.tenant):
        raise NotFound("work_items")
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
