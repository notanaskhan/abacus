"""HOME-01's your-work band and deadlines (I-01-T10; I-01 AC4.1, AC4.2): the live work items a
person is assigned to (C1 work-item assignments, not removed), in engagements they may read
(`visible()`, so a wall leaves the client out, INV-3), narrowed to an office when one is given
(DEC-30: a filter, never a boundary). Codes and identifiers; the client's name is resolved by the
caller through organisations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import column, select, table

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.models import WorkItem
from abacus.modules.identity.api import AuthContext, visible

_assignments = table(
    "work_item_assignments",
    column("work_item_id"),
    column("user_id"),
    column("function"),
    column("removed_at"),
)


@dataclass(frozen=True)
class AssignedWork:
    work_item_id: UUID
    name: str
    client_id: UUID
    kind: str
    status: str
    function: str | None
    due_on: date | None
    office_id: UUID | None


async def assigned_work(ctx: AuthContext, *, office_id: UUID | None = None) -> list[AssignedWork]:
    """The person's live assigned work items, one row per item (their first function by name)."""
    stmt = (
        select(WorkItem, _assignments.c.function)
        .join(_assignments, _assignments.c.work_item_id == WorkItem.id)
        .where(
            _assignments.c.user_id == ctx.user_id,
            _assignments.c.removed_at.is_(None),
            WorkItem.archived_at.is_(None),
            visible(ctx, "work_item.read_metadata", WorkItem.engagement_id),
        )
        .order_by(WorkItem.due_on.asc().nulls_last(), WorkItem.name, WorkItem.id)
    )
    if office_id is not None:
        stmt = stmt.where(WorkItem.office_id == office_id)
    async with tenant_session(ctx.tenant) as session:
        rows = (await session.execute(stmt)).all()
    found: dict[UUID, AssignedWork] = {}
    for item, function in rows:
        held = found.get(item.id)
        if held is None or (function or "") < (held.function or ""):
            found[item.id] = AssignedWork(
                item.id,
                item.name,
                item.client_id,
                item.kind,
                item.status,
                function,
                item.due_on,
                item.office_id,
            )
    return list(found.values())


__all__ = ["AssignedWork", "assigned_work"]
