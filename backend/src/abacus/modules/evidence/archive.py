"""The engagement's source documents for the archive's section F (A-07-T31; DEC-3108): evidence
counts its own versions; the archive itself is assurance's (`assurance/archive_records.py`)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


async def source_document_count(tenant: TenantContext, engagement_id: UUID) -> int:
    """Section F: the engagement's evidence documents, superseded versions kept (one per object,
    every object that ever had a version on the engagement)."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text(
                "SELECT count(DISTINCT evidence_item_id) FROM evidence_versions "
                "WHERE engagement_id = :e"
            ),
            {"e": engagement_id},
        )
    return int(found or 0)
