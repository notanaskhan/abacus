"""The financial statements' current-year amount per caption (A-05-T54 reads it for EBP-07).

From the work item's statement document at its current version (AUD-20): one amount per
`<statement_key>.<line_key>` caption, for the newest year on the version. Code's figures (linked
values, A-06); identifiers and amounts only. The caller has authorised on the work item.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_AMOUNTS = text(
    """
    SELECT l.statement_key || '.' || l.line_key AS caption, v.value
      FROM statement_documents d
      JOIN statement_versions sv ON sv.statement_document_id = d.id
                                AND sv.version_no = d.current_version_no
      JOIN line_items l ON l.statement_version_id = sv.id
      JOIN linked_values v ON v.line_item_id = l.id
     WHERE d.work_item_id = :w
       AND v.year = (SELECT max(v2.year) FROM linked_values v2
                       JOIN line_items l2 ON l2.id = v2.line_item_id
                      WHERE l2.statement_version_id = sv.id)
    """
)


async def statement_caption_amounts(
    tenant: TenantContext, work_item_id: UUID
) -> dict[str, Decimal]:
    """Empty when the work item has no statement version yet (EBP-07 then waits on AUD-20)."""
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_AMOUNTS, {"w": work_item_id})).all()
    return {str(r.caption): Decimal(r.value) for r in rows if r.value is not None}
