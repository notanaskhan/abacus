"""Work items (F-03-T05; migration 0068): the units of work inside an engagement.

Every engagement holds one `assurance` work item and one primary entity from its creation (the
`engagement_work_item_defaults` trigger). Other kinds (returns, closes, notices, advisory
projects) register with their modules as they arrive.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from typing import Final
from uuid import UUID

from sqlalchemy import insert, select, text, update
from sqlalchemy.exc import IntegrityError

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict
from abacus.kernel.uow import Target, UnitOfWork, uow
from abacus.modules.engagements.models import AssuranceWorkItem, Engagement, WorkItem
from abacus.modules.engagements.service import get_ref, lock_ref
from abacus.modules.engagements.slots import NewWorkItem, work_item_provider
from abacus.modules.identity.api import AuthContext, authorise, visible


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
