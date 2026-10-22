"""The `notice` work-item kind (F-03-T22): a notice: its code and when it was received. Registered
with engagements' kind slot; engagements creates the work item and calls `create` in the same
unit of work."""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import NewWorkItem
from abacus.modules.notices.repository import insert_notices


class NoticeKind:
    async def status(self, tenant: TenantContext, work_item_id: UUID) -> str:
        return "active"  # the subtype carries no lifecycle of its own yet

    async def create(self, tx: UnitOfWork, item: NewWorkItem) -> None:
        await insert_notices(
            tx.session,
            {
                "tenant_id": item.tenant_id,
                "work_item_id": item.work_item_id,
                "engagement_id": item.engagement_id,
                "notice_code": item.details.get("notice_code"),
                "received_on": item.details.get("received_on"),
            },
        )
