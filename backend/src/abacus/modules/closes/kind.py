"""The `close` work-item kind (F-03-T22; C-01-T14): a monthly close: its `YYYY-MM` period, one per
engagement and period, with BD1 and its due date. Registered with engagements' kind slot;
engagements creates the work item and calls `create` in the same unit of work. `status` answers
the close's own lifecycle word (DF-23)."""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import UnitOfWork
from abacus.modules.closes.events import CloseCreated
from abacus.modules.closes.repository import close_row, insert_closes
from abacus.modules.engagements.api import NewWorkItem


class CloseKind:
    async def status(self, tenant: TenantContext, work_item_id: UUID) -> str:
        async with tenant_session(tenant) as session:
            close = await close_row(session, work_item_id)
        return close.status if close is not None else "not_started"

    async def create(self, tx: UnitOfWork, item: NewWorkItem) -> None:
        await insert_closes(
            tx.session,
            {
                "tenant_id": item.tenant_id,
                "work_item_id": item.work_item_id,
                "engagement_id": item.engagement_id,
                "period": item.details.get("period"),
                "client_entity_id": item.client_entity_id,
                "requests_publish_on": item.details.get("requests_publish_on"),
                "due_on": item.details.get("due_on"),
            },
        )
        period = item.details.get("period")
        tx.emit(CloseCreated(close_id=item.work_item_id, period=str(period)))
