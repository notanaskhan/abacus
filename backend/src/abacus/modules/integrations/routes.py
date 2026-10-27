"""POR-16's live routes (A-02-T16; C20 v1; SPEC-333 AC-35 to AC-42). Declared on C20's
`portal_router` (`contract.py` keeps the models and the two stubs still waiting: reconnect
requests, A-02-T23, and on-demand pulls, A-02-T30); `api.py` mounts it from here.

Each route authorises its one action through `connections` on an engagement of the entity
first (404 for walls and other clients' entities), then the flag (`connections.portal_v2`, 404
off), then acts (`client_connect`).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends

from abacus.modules.identity.api import AuthContext, current_context
from abacus.modules.integrations.client_connect import (
    detail_of,
    disconnect_card,
    portal_cards,
    retry_card,
    start_card,
)
from abacus.modules.integrations.contract import (
    CatalogKey,
    ConnectionDisconnectIn,
    ConnectionStartIn,
    ConnectionStartOut,
    IdempotencyKey,
    PortalConnectionCardOut,
    PortalConnectionDetailOut,
    PortalConnectionsOut,
    SyncRunRefOut,
    portal_router,
)

Ctx = Annotated[AuthContext, Depends(current_context)]


@portal_router.get(
    "/entities/{entity_id}/connections",
    action="connection.read",
    response_model=PortalConnectionsOut,
)
async def list_entity_connections_route(entity_id: UUID, ctx: Ctx) -> PortalConnectionsOut:
    """POR-16 a: cards for the catalogue rows listed here, with the entity's connections."""
    return await portal_cards(ctx, entity_id)


@portal_router.post(
    "/entities/{entity_id}/connections/{catalog_key}/start",
    action="connection.create",
    response_model=ConnectionStartOut,
    status_code=201,
    errors=(409,),
)
async def start_connection_route(
    entity_id: UUID,
    catalog_key: CatalogKey,
    body: ConnectionStartIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> ConnectionStartOut:
    """POR-16 b, e: one consent row as shown, then the provider's sign-in URL (fresh MFA). 422
    `authorization_required`; 409 `consent_version_stale`, `ledger_already_connected`,
    `connector_not_available`. Audited `connection.consent_recorded`, `connection.started`."""
    return await start_card(ctx, entity_id, catalog_key, body)


@portal_router.get(
    "/connections/{connection_id}",
    action="connection.read",
    response_model=PortalConnectionDetailOut,
)
async def connection_detail_route(connection_id: UUID, ctx: Ctx) -> PortalConnectionDetailOut:
    """The details drawer: scopes, who connected it and when, the last 5 syncs, the activity."""
    return await detail_of(ctx, connection_id)


@portal_router.post(
    "/connections/{connection_id}/retry",
    action="connection.retry",
    response_model=SyncRunRefOut,
    status_code=202,
    errors=(409,),
)
async def retry_connection_route(
    connection_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> SyncRunRefOut:
    """POR-16 g *Try again*: one run; while it runs the same run is returned; 409
    `connection_needs_reauth`, `no_failed_sync`, `retry_unavailable`. Audited
    `connection.retry_requested`."""
    return await retry_card(ctx, connection_id, idempotency_key)


@portal_router.post(
    "/connections/{connection_id}/disconnect",
    action="connection.disconnect",
    response_model=PortalConnectionCardOut,
    errors=(409,),
)
async def disconnect_connection_route(
    connection_id: UUID, body: ConnectionDisconnectIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> PortalConnectionCardOut:
    """POR-16 f: "Disconnected" (neutral); the secret is crypto-erased and received data stays.
    409 `stale_version` on an old `seen_version`. Audited `connection.revoked`."""
    return await disconnect_card(ctx, connection_id, body.seen_version, idempotency_key)
