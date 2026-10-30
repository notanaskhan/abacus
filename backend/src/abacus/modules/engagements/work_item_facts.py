"""Work items as their kinds' owners read them (T-02-T09; ADR-008: engagements owns `work_items`
and their assignments; the tax practice board composes on this).

- `work_item_facts(ctx, kind)`: the viewer's live work items of one kind, `visible()`-filtered
  (walls included), with the client's name, the office and the people on each function. A walled
  or unseen item is simply absent: there is no count of what was left out (INV-3, DEC-43).
- `work_item_offices(tenant, ids)`: each item's office, for firm-level counts by office (ADM-03a's
  office facts) that never name a client.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import column, select, table

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.models import WorkItem
from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.organisations.api import client_name_column

_assignments = table(
    "work_item_assignments",
    column("work_item_id"),
    column("user_id"),
    column("function"),
    column("removed_at"),
)


@dataclass(frozen=True)
class WorkItemFacts:
    work_item_id: UUID
    engagement_id: UUID
    client_id: UUID
    client_name: str
    office_id: UUID | None
    # function -> the people holding it now (P-07-T30's functions).
    assignees: Mapping[str, tuple[UUID, ...]]


async def work_item_facts(
    ctx: AuthContext, kind: str, action: str = "work_item.read_metadata"
) -> list[WorkItemFacts]:
    """The visible work items of `kind`. A module whose own read action names who may see its
    items (T-02-T13: `tax_return.read_metadata` lets a security admin see a return's metadata)
    filters by that action instead; it must be a read without conditions (`visible()`)."""
    stmt = select(
        WorkItem.id,
        WorkItem.engagement_id,
        WorkItem.client_id,
        client_name_column(WorkItem.client_id),
        WorkItem.office_id,
    ).where(
        WorkItem.kind == kind,
        WorkItem.archived_at.is_(None),
        visible(ctx, action, WorkItem.engagement_id),
    )
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(stmt)).all()
        ids = [row[0] for row in rows]
        held: dict[UUID, dict[str, list[UUID]]] = {}
        if ids:
            assigned = await session.execute(
                select(
                    _assignments.c.work_item_id, _assignments.c.function, _assignments.c.user_id
                )
                .where(_assignments.c.work_item_id.in_(ids), _assignments.c.removed_at.is_(None))
                .order_by(_assignments.c.user_id)
            )
            for item, function, user in assigned.all():
                held.setdefault(item, {}).setdefault(function, []).append(user)
    return [
        WorkItemFacts(
            work_item_id=item,
            engagement_id=engagement,
            client_id=client,
            client_name=name or "",
            office_id=office,
            assignees={f: tuple(people) for f, people in held.get(item, {}).items()},
        )
        for item, engagement, client, name, office in rows
    ]


async def work_item_offices(
    tenant: TenantContext, work_item_ids: Sequence[UUID]
) -> dict[UUID, UUID | None]:
    if not work_item_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            select(WorkItem.id, WorkItem.office_id).where(
                WorkItem.id.in_(list(work_item_ids)), WorkItem.archived_at.is_(None)
            )
        )
        return {item: office for item, office in rows.all()}


__all__ = ["WorkItemFacts", "work_item_facts", "work_item_offices"]
