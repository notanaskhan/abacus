"""C13 source for a close plan waiting on its publication (C-01-T15; QC-8; CLS-09 b).

A Senior's "Request publish…" leaves the draft with `publish_requested_at`; until a Manager or
Partner publishes or discards it, one HOME-02 gate waits on them. The read action is
`close_plan.publish`, so only the people the matrix lets publish see the row (need to know);
the row links to CLS-09, where the person publishes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements.api import client_of, engagement_type_of, engagements_of_entity
from abacus.modules.identity.api import AuthContext
from abacus.modules.review.api import (
    GateFacts,
    GateSource,
    GateView,
    OpenGate,
    register_gate_presenter,
    register_gate_source,
)

SUBJECT: Final = "close_plan_publish"
_EVENTS: Final = frozenset({"close_plan.publish_requested", "close_plan.published"})
_DUE = text(
    "SELECT v.id, v.version, p.client_entity_id FROM close_plan_versions v "
    "JOIN close_plans p ON p.id = v.plan_id "
    "WHERE v.status = 'draft' AND v.publish_requested_at IS NOT NULL"
)
_FACTS = text(
    "SELECT v.id, v.version, p.client_entity_id FROM close_plan_versions v "
    "JOIN close_plans p ON p.id = v.plan_id WHERE v.id = ANY(:ids)"
)


async def _monthly_close_of(tenant: TenantContext, entity: UUID) -> UUID | None:
    """The entity's newest Monthly close engagement (DEC-5021), through engagements' API."""
    for engagement_id in await engagements_of_entity(tenant, entity):
        if await engagement_type_of(tenant, engagement_id) == "cas_monthly_close":
            return engagement_id
    return None


async def publications_due(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_DUE)).all()
    out: list[OpenGate] = []
    for r in rows:
        engagement = await _monthly_close_of(tenant, r.client_entity_id)
        if engagement is None or (engagement_id is not None and engagement != engagement_id):
            continue
        out.append(OpenGate(r.id, engagement, client_id=await client_of(tenant, engagement)))
    return out


async def present(ctx: AuthContext, rows: Sequence[GateView]) -> Mapping[UUID, GateFacts]:
    async with tenant_session(ctx.tenant) as session:
        found = {
            r.id: r
            for r in (
                await session.execute(_FACTS, {"ids": [row.subject_id for row in rows]})
            ).all()
        }
    out: dict[UUID, GateFacts] = {}
    for row in rows:
        hit = found.get(row.subject_id)
        if hit is None or row.client_id is None:
            continue
        out[row.id] = GateFacts(
            title=f"Publish close plan v{hit.version}",
            subject_route=f"CLS-09?clientId={row.client_id}&version={hit.version}",
        )
    return out


def register_close_gates() -> None:
    register_gate_source(
        GateSource(SUBJECT, "final_approval", "close_plan.publish", _EVENTS, publications_due)
    )
    register_gate_presenter(SUBJECT, present)
