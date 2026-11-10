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


async def engagement_documents(
    tenant: TenantContext, engagement_id: UUID
) -> list[tuple[UUID, UUID, str, str, int, bool]]:
    """T-04-T17: each evidence version of the engagement as TAX-04's review tree lists it:
    `(version id, item id, item title, folder kind, version number, is the item's latest)`."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT v.id, v.evidence_item_id, i.title, i.folder_kind, v.version_no, "
                    "v.version_no = max(v.version_no) OVER (PARTITION BY v.evidence_item_id) "
                    "AS latest FROM evidence_versions v JOIN evidence_items i "
                    "ON i.id = v.evidence_item_id WHERE v.engagement_id = :e "
                    "ORDER BY i.folder_kind, i.title, v.version_no"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [
        (r.id, r.evidence_item_id, r.title, r.folder_kind, r.version_no, bool(r.latest))
        for r in rows
    ]
