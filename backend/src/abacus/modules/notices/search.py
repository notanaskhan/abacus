"""The notice's C15 search document (N-04-T06; INV-3): metadata only, never an amount or a TIN.
The client's name comes with the work item, as for a tax return."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.platform.api import SearchDocument

KIND = "notice"


async def notice_search_document(tenant: TenantContext, notice_id: UUID) -> SearchDocument | None:
    async with tenant_session(tenant) as session:
        row = (
            await session.execute(
                text(
                    "SELECT engagement_id, notice_code, tax_year FROM notices "
                    "WHERE work_item_id = :w"
                ),
                {"w": notice_id},
            )
        ).first()
    if row is None:
        return None
    year = "" if row.tax_year is None else f" · TY{row.tax_year}"
    return SearchDocument(
        object_type=KIND,
        object_id=notice_id,
        engagement_id=row.engagement_id,
        title=f"{row.notice_code}{year}",
        body="notice",
    )
