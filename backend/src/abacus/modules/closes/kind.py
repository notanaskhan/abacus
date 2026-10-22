"""The `close` work-item kind (F-03-T22): a monthly close: its `YYYY-MM` period, one per engagement
and period. Registered with engagements' kind slot; engagements creates the work item and calls
`create` in the same unit of work."""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import UnitOfWork
from abacus.modules.closes.repository import insert_closes
from abacus.modules.engagements.api import NewWorkItem


class CloseKind:
    async def status(self, tenant: TenantContext, work_item_id: UUID) -> str:
        return "active"  # the subtype carries no lifecycle of its own yet

    async def create(self, tx: UnitOfWork, item: NewWorkItem) -> None:
        await insert_closes(
            tx.session,
            {
                "tenant_id": item.tenant_id,
                "work_item_id": item.work_item_id,
                "engagement_id": item.engagement_id,
                "period": item.details.get("period"),
            },
        )
