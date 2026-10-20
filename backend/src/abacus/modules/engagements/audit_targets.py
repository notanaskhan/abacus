"""Which engagements an audit event's target belongs to, and which of them a reader may see
(SPEC-304; SPEC-002 AC-5; DEC-121). Follow-up: an `engagement_id` on audit events makes the
resolution exact and cheap."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.models import Engagement
from abacus.modules.identity.api import AuthContext, visible

AUDIT_KINDS = frozenset({"engagement", "client", "client_entity"})


async def audit_engagements(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, frozenset[UUID]]:
    """For `kind` targets named by an audit event: the engagements each belongs to (an engagement
    is its own; a client or client entity has all of theirs). Unknown ids are left out."""
    found: dict[UUID, set[UUID]] = {}
    async with tenant_session(tenant) as session:
        if kind == "engagement":
            rows = await session.execute(
                select(Engagement.id, Engagement.id).where(Engagement.id.in_(list(ids)))
            )
        elif kind == "client":
            rows = await session.execute(
                select(Engagement.client_id, Engagement.id).where(
                    Engagement.client_id.in_(list(ids))
                )
            )
        else:
            rows = await session.execute(
                select(Engagement.client_entity_id, Engagement.id).where(
                    Engagement.client_entity_id.in_(list(ids))
                )
            )
        for target, engagement in rows:
            found.setdefault(target, set()).add(engagement)
    return {target: frozenset(engagements) for target, engagements in found.items()}


async def visible_among(ctx: AuthContext, ids: Sequence[UUID]) -> set[UUID]:
    """Of these engagements, the ones the reader may see (walls and roles apply, as in the
    engagement list)."""
    if not ids:
        return set()
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(Engagement.id).where(
                Engagement.id.in_(list(ids)),
                visible(ctx, "engagement.read_metadata", Engagement.id),
            )
        )
        return {engagement for (engagement,) in rows}
