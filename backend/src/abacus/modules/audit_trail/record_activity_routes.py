"""CLI-02's and ENG-02's Activity lines over the audit trail (P-07-T57; DEC-718; SPEC-349 §5).

`GET /v1/clients/{client_id}/activity` and `GET /v1/engagements/{engagement_id}/record-activity`
(the engagement's `/activity` is the agent feed's, SPEC-027). Each checks the principal (a client
principal 404s), the record family's flag, then the record itself (404 for a walled or unknown
one, DEC-43), and `explorer.record_events` narrows every event. Rows are the explorer's
`AuditEventRow`: action code, category, mark, actor grammar and identifier facts; the SPA words
them (P-07-T61)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Query

from abacus.kernel._flags import CLIENTS_V2, ENGAGEMENTS_V2
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.audit_trail import explorer
from abacus.modules.audit_trail.audit_log_contract import AuditEventRow, Ctx
from abacus.modules.engagements import api as engagements
from abacus.modules.identity.api import AbacusRouter, authorise
from abacus.modules.organisations.api import readable_client

clients_router = AbacusRouter(prefix="/v1/clients", tags=["activity"])
engagements_router = AbacusRouter(prefix="/v1/engagements", tags=["activity"])

Cursor = Annotated[str | None, Query(max_length=512)]
Limit = Annotated[int, Query(ge=1, le=100)]


@clients_router.get(
    "/{client_id}/activity", action=explorer.RECORD_READ, response_model=ListPage[AuditEventRow]
)
async def client_activity_route(
    client_id: UUID, ctx: Ctx, cursor: Cursor = None, limit: Limit = 50
) -> ListPage[AuditEventRow]:
    """The client's own events and its engagements' events the reader may see."""
    if ctx.client or not await flag_enabled(ctx.tenant, CLIENTS_V2):
        raise NotFound("client")
    await readable_client(ctx, client_id)
    return await explorer.record_events(ctx, client_id=client_id, cursor=cursor, limit=limit)


@engagements_router.get(
    "/{engagement_id}/record-activity",
    action=explorer.RECORD_READ,
    response_model=ListPage[AuditEventRow],
)
async def engagement_activity_route(
    engagement_id: UUID, ctx: Ctx, cursor: Cursor = None, limit: Limit = 50
) -> ListPage[AuditEventRow]:
    """The engagement's events (its scope, or the engagement as target)."""
    if ctx.client or not await flag_enabled(ctx.tenant, ENGAGEMENTS_V2):
        raise NotFound("engagement")
    ref = await engagements.get_ref(ctx, engagement_id)
    await authorise(ctx, explorer.RECORD_READ, ref.resource())
    return await explorer.record_events(
        ctx, engagement_id=engagement_id, cursor=cursor, limit=limit
    )
