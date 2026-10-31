"""Which engagement owns the sampling rows an audit event can point at (SPEC-304; DEC-121,
DEC-1387). The audit explorer drops events about engagements the reader may not see."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_OWNERS: Final = {
    "population": text("SELECT id, engagement_id FROM sample_populations WHERE id = ANY(:ids)"),
    "sample_set": text("SELECT id, engagement_id FROM sample_sets WHERE id = ANY(:ids)"),
    "sample_set_version": text(
        "SELECT v.id, s.engagement_id FROM sample_set_versions v JOIN sample_sets s "
        "ON s.tenant_id = v.tenant_id AND s.id = v.sample_set_id WHERE v.id = ANY(:ids)"
    ),
}
AUDIT_KINDS: Final = frozenset(_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    async with tenant_session(tenant) as session:
        rows = await session.execute(_OWNERS[kind], {"ids": list(ids)})
        return {row[0]: row[1] for row in rows}
