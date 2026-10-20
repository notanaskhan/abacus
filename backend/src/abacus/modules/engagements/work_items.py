"""Work items (F-03-T05; migration 0068): the units of work inside an engagement.

Every engagement holds one `assurance` work item and one primary entity from its creation (the
`engagement_work_item_defaults` trigger). Other kinds (returns, closes, notices, advisory
projects) register with their modules as they arrive.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.models import AssuranceWorkItem, WorkItem
from abacus.modules.engagements.service import get_ref
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
