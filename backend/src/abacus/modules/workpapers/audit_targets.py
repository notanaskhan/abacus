"""Which engagement owns the rows an audit event can point at (SPEC-304; DEC-121). The audit
explorer drops events about engagements the reader may not see, so each module says, for the
kinds of target it owns, the engagement of each id. Follow-up: an `engagement_id` on audit events
makes this exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.workpapers.tie_models import TieOutCheck

_OWNERS: dict[str, tuple[QueryableAttribute[UUID], QueryableAttribute[UUID | None]]] = {
    "tie_out_check": (TieOutCheck.id, TieOutCheck.engagement_id),  # SPEC-310
}
AUDIT_KINDS = frozenset(_OWNERS)


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """For `kind` rows named by an audit event (the caller has authorised the read of the trail):
    their id -> the owning engagement. Unknown ids are left out."""
    key, owner = _OWNERS[kind]
    async with tenant_session(tenant) as session:
        rows = await session.execute(select(key, owner).where(key.in_(list(ids))))
        return {found: owned for found, owned in rows if owned is not None}
