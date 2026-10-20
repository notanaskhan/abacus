"""What identity owns that an audit event can point at (SPEC-304; DEC-121): which engagement a
client invitation belongs to, and which ethical walls a reader must not learn of. Follow-up: an
`engagement_id` on audit events makes the first exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import (
    ethical_walls,
    invitation_engagements,
    walled_clients,
)

AUDIT_KINDS = frozenset({"client_invitation"})


async def audit_owners(tenant: TenantContext, kind: str, ids: Sequence[UUID]) -> dict[UUID, UUID]:
    """Invitation id -> its engagement."""
    async with tenant_session(tenant) as session:
        return await invitation_engagements(session, ids)


async def audit_hidden_walls(ctx: AuthContext, ids: Sequence[UUID]) -> set[UUID]:
    """Of these walls, the ones the reader must not learn of: walls on the reader themself, and
    walls from a client the reader is walled off from (events name the client and the person)."""
    walled = await walled_clients(ctx.tenant, ctx.user_id)
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(ethical_walls.c.id, ethical_walls.c.user_id, ethical_walls.c.client_id).where(
                ethical_walls.c.id.in_(list(ids))
            )
        )
        return {wall for wall, user, client in rows if user == ctx.user_id or client in walled}
