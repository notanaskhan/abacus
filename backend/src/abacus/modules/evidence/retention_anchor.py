"""The stored objects an anchor event extends (A-07-T36; P-14; ADR-004). An engagement's evidence
versions that hold an object of their own (not a virtual page range of another), for a caller in
the platform's own context after a release: identifiers only."""

from __future__ import annotations

from datetime import datetime
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


async def engagement_version_leaves(
    tenant: TenantContext, engagement_id: UUID
) -> list[tuple[UUID, str, str, str]]:
    """A-07-T37: `(version id, SHA-256 fingerprint, storage key, storage version id)` of every
    version of the engagement, superseded ones kept: the archive seal's evidence leaves."""
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, fingerprint, storage_key, storage_version_id "
                    "FROM evidence_versions WHERE engagement_id = :e ORDER BY id"
                ),
                {"e": engagement_id},
            )
        ).all()
    return [(r.id, r.fingerprint, r.storage_key, r.storage_version_id) for r in rows]


async def version_fingerprint(tenant: TenantContext, version_id: UUID) -> str | None:
    """A-07-T42: one evidence version's SHA-256 fingerprint (an archive addition names it)."""
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT fingerprint FROM evidence_versions WHERE id = :v"), {"v": version_id}
        )
    return str(found) if found is not None else None


async def extend_versions_until(
    tenant: TenantContext, objects: list[tuple[str, str]], until: datetime
) -> int:
    """A-07-T37: each stored object's GOVERNANCE retain-until extended to at least `until` (the
    archive's retention); audited `retention.extended` once. Governance mode only ever extends."""
    from abacus.kernel.uow import Ref, Target, uow
    from abacus.modules.evidence.storage import StoredObject, extend_retention

    for key, version_id in objects:
        await extend_retention(StoredObject(key, version_id, "", 0), until)
    async with uow(TenantContext(tenant.tenant_id, "system", "retention_clock")) as tx:
        tx.record(
            "retention.extended",
            target=Target("firm", tenant.tenant_id),
            after=Ref(objects=len(objects), until=int(until.strftime("%Y%m%d"))),
        )
    return len(objects)
