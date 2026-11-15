"""C-01-T14 (AC-7): what the close record reads about a close's binders, by their owner so closes
never queries `request_lists`, `request_items` or `fulfilments` (OWN-001).

- **Documents in Binder** (CLS-02 rail, "58"): the evidence versions fulfilling the work item's
  binder items, a withdrawn fulfilment not counted (P-06-T19, ADR-162).
- **Requests pending** (the rail's Client Portal block, "2 pending"): the items
  still open on those binders (open or sent back for revision).

For a caller already authorised on the close, or filtering the work items by `visible()`.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_DOCUMENTS: Final = text(
    "SELECT l.work_item_id, count(DISTINCT f.evidence_version_id) "
    "FROM request_lists l "
    "JOIN request_items i ON i.request_list_id = l.id "
    "JOIN fulfilments f ON f.request_item_id = i.id "
    "WHERE l.work_item_id = ANY(:ids) "
    "AND NOT EXISTS (SELECT 1 FROM fulfilment_withdrawals w WHERE w.fulfilment_id = f.id) "
    "GROUP BY l.work_item_id"
)
_PENDING: Final = text(
    "SELECT l.work_item_id, count(*) FROM request_lists l "
    "JOIN request_items i ON i.request_list_id = l.id "
    "WHERE l.work_item_id = ANY(:ids) AND i.status IN ('open', 'needs_revision') "
    "GROUP BY l.work_item_id"
)


async def binder_document_counts(
    tenant: TenantContext, work_item_ids: list[UUID]
) -> dict[UUID, int]:
    if not work_item_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(_DOCUMENTS, {"ids": work_item_ids})
        return {item: int(n) for item, n in rows.all()}


async def pending_request_counts(
    tenant: TenantContext, work_item_ids: list[UUID]
) -> dict[UUID, int]:
    if not work_item_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = await session.execute(_PENDING, {"ids": work_item_ids})
        return {item: int(n) for item, n in rows.all()}
