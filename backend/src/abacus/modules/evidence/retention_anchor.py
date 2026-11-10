"""The stored objects an anchor event extends (A-07-T36; P-14; ADR-004). An engagement's evidence
versions that hold an object of their own (not a virtual page range of another), for a caller in
the platform's own context after a release: identifiers only."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


async def engagement_stored_versions(
    tenant: TenantContext, engagement_id: UUID
) -> list[tuple[str, str]]:
    """`(storage_key, storage_version_id)` of each stored version of the engagement."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT storage_key, storage_version_id FROM evidence_versions "
                    "WHERE engagement_id = :e AND parent_version_id IS NULL "
                    "ORDER BY created_at, id"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [(r.storage_key, r.storage_version_id) for r in rows]
