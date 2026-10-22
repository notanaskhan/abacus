"""The `tax_return` work-item kind (F-03-T22): a tax return: its entity, form (1040, 1041, 1065,
1120s, 1120, 990, 706, 709) and tax year. Registered with engagements' kind slot; engagements
creates the work item and calls `create` in the same unit of work."""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import UnitOfWork
from abacus.modules.engagements.api import NewWorkItem
from abacus.modules.tax.repository import insert_tax_returns


class TaxReturnKind:
    async def status(self, tenant: TenantContext, work_item_id: UUID) -> str:
        return "active"  # the subtype carries no lifecycle of its own yet

    async def create(self, tx: UnitOfWork, item: NewWorkItem) -> None:
        await insert_tax_returns(
            tx.session,
            {
                "tenant_id": item.tenant_id,
                "work_item_id": item.work_item_id,
                "engagement_id": item.engagement_id,
                "client_entity_id": item.client_entity_id,
                "form": item.details.get("form"),
                "tax_year": item.details.get("tax_year"),
            },
        )
