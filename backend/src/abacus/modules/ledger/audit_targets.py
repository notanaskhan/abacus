"""Which client entity owns the ledger snapshots an audit event can point at (SPEC-304; DEC-121).
Snapshots belong to an entity, not an engagement: the audit explorer asks the engagements module
which engagements an entity has."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.ledger.models import GlSnapshot, LedgerSnapshot

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID]]] = {
    "ledger_snapshot": (LedgerSnapshot.id, LedgerSnapshot.client_entity_id),
    "gl_snapshot": (GlSnapshot.id, GlSnapshot.client_entity_id),
}
AUDIT_KINDS = frozenset(_OWNERS)


async def audit_entities(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event: their id -> the owning client entity."""
    key, owner = _OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows}
