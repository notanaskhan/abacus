"""`PUT /v1/connections/{id}/coverage` (A-09-T18; A-09-T02 matrix row
`connection.manage_coverage`; SPEC-658): which subsidiaries one OneWorld ledger connection
covers. A person (Manager or EP) on an engagement of the connection's own entity and of every
entity named; an entity another live ledger covers answers 409 (the partial unique index).
Firm side only; nothing here reaches a client system (CONN-001)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.connections.coverage import cover_entities
from abacus.modules.connections.entity import authorised_engagement
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

ACTION = "connection.manage_coverage"
Ctx = Annotated[AuthContext, Depends(current_context)]
router = AbacusRouter(prefix="/v1", tags=["connections"])


class CoverageIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_entity_ids: Annotated[
        list[UUID], Field(min_length=1, max_length=100), classified("internal")
    ]


class CoverageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    connection_id: Annotated[UUID, classified("internal")]
    added: Annotated[int, Field(ge=0), classified("internal")]


@router.put(
    "/connections/{connection_id}/coverage",
    action=ACTION,
    response_model=CoverageOut,
    errors=(409,),
)
async def put_coverage(connection_id: UUID, body: CoverageIn, ctx: Ctx) -> CoverageOut:
    if ctx.tenant.actor_kind != "human" or ctx.client or ctx.is_support:
        raise Forbidden(ACTION, "role")
    async with tenant_session(ctx.tenant) as session:
        entity = await session.scalar(
            text("SELECT client_entity_id FROM connections WHERE id = :c"), {"c": connection_id}
        )
    if not isinstance(entity, UUID):
        raise NotFound("connection")
    for target in {entity, *body.client_entity_ids}:
        await authorised_engagement(ctx, target, ACTION)
    added = await cover_entities(ctx.tenant, connection_id, body.client_entity_ids)
    return CoverageOut(connection_id=connection_id, added=added)
