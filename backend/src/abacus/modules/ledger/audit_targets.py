"""Who owns the ledger rows an audit event can point at (SPEC-304; DEC-121). Snapshots belong to a
client entity, not an engagement: the audit explorer asks the engagements module which
engagements an entity has. A trial balance (SPEC-309) belongs to one engagement."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.ledger.models import GlSnapshot, LedgerSnapshot, MappingSet, TrialBalance

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID]]] = {
    "ledger_snapshot": (LedgerSnapshot.id, LedgerSnapshot.client_entity_id),
    "gl_snapshot": (GlSnapshot.id, GlSnapshot.client_entity_id),
}
ENTITY_KINDS = frozenset(_OWNERS)
ENGAGEMENT_KINDS = frozenset({"trial_balance", "mapping_set"})
# A mapping set (SPEC-316) maps one engagement's trial balance.
_ENGAGEMENT_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID]]] = {
    "trial_balance": (TrialBalance.id, TrialBalance.engagement_id),
    "mapping_set": (MappingSet.id, MappingSet.engagement_id),
}


async def audit_entities(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event: their id -> the owning client entity."""
    key, owner = _OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows}


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    if kind not in ENGAGEMENT_KINDS:
        return {}
    key, owner = _ENGAGEMENT_OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows}
