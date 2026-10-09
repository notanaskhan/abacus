"""Automatic fulfilment of retrievable items (SPEC-022 AC-4; TASK-038).

When a connection becomes active, or an item becomes tier A with a dataset, the platform starts
the retrieval itself, as the client admin who connected (their standing consent, ADR-040;
`identity.member_context`, D3). Behind the `retrieval.auto` flag. Caps, work slots and
idempotency are `trigger_retrieval`'s own: nothing here bypasses them.
"""

from __future__ import annotations

from uuid import UUID

from abacus.kernel import _flags
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound, ServiceUnavailable
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.connections.connector import ConnectorError, Period
from abacus.modules.connections.models import Connection
from abacus.modules.connections.repository import live_connection_for
from abacus.modules.connections.retrievals import trigger_retrieval
from abacus.modules.connections.service import connector_for
from abacus.modules.engagements.api import engagement_metadata, entity_of
from abacus.modules.identity.api import AuthContext, Forbidden, autonomy_level, member_context
from abacus.modules.requests.api import RequestItemView, request_items_for

_log = get_logger(__name__)
_SYSTEM = "connections.auto_retrieval"


async def available_datasets(tenant: TenantContext, client_entity_id: UUID) -> frozenset[str]:
    """What the entity's active connection can deliver (registered into requests, D2)."""
    async with tenant_session(tenant) as session:
        connection = await live_connection_for(session, client_entity_id)
    if connection is None or connection.status != "active":
        return frozenset()
    try:
        return frozenset(connector_for(connection).capabilities().datasets)
    except ConnectorError:
        return frozenset()


async def _enabled(tenant_id: UUID) -> bool:
    return await flag_enabled(TenantContext(tenant_id, "system", _SYSTEM), _flags.RETRIEVAL_AUTO)


async def _consenting(tenant_id: UUID, connection: Connection) -> AuthContext | None:
    try:
        user_id = UUID(connection.created_by)
    except ValueError:
        return None  # created by tooling: no person's consent to act on
    return await member_context(tenant_id, user_id)


async def _retrieve(ctx: AuthContext, engagement_id: UUID, items: list[RequestItemView]) -> None:
    metadata = await engagement_metadata(ctx, engagement_id)
    period = Period(metadata.engagement.fiscal_period_start, metadata.engagement.fiscal_period_end)
    for item in items:
        try:
            view = await trigger_retrieval(
                ctx, engagement_id=engagement_id, request_item_id=item.id, period=period
            )
            _log.info(
                "auto_retrieval.started",
                request_item_id=str(item.id),
                sync_run_id=str(view.sync_run_id),
            )
        except (DomainConflict, ServiceUnavailable, Forbidden, NotFound) as exc:
            # A cap reached, an item no longer open, no connection: logged, never retried here.
            _log.info(
                "auto_retrieval.refused", request_item_id=str(item.id), error=type(exc).__name__
            )


async def _run(tenant_id: UUID, engagement_id: UUID, only: UUID | None) -> None:
    if not await _enabled(tenant_id):
        return
    # SPEC-024 Q4: at Advise (autonomy level 0) the platform starts nothing on its own.
    if await autonomy_level(tenant_id) < 1:
        _log.info("auto_retrieval.skipped", engagement_id=str(engagement_id), reason="advise")
        return
    system = TenantContext(tenant_id, "system", _SYSTEM)
    entity = await entity_of(system, engagement_id)
    if entity is None:
        return
    async with tenant_session(system) as session:
        connection = await live_connection_for(session, entity)
    if connection is None or connection.status != "active":
        return
    ctx = await _consenting(tenant_id, connection)
    if ctx is None:
        _log.info("auto_retrieval.no_consenting_member", engagement_id=str(engagement_id))
        return
    datasets = frozenset(connector_for(connection).capabilities().datasets)
    items = [
        i
        for i in await request_items_for(ctx, engagement_id)
        if i.status == "open"
        and i.retrievability_tier == "A"
        and i.dataset in datasets
        and (only is None or i.id == only)
    ]
    if items:
        await _retrieve(ctx, engagement_id, items)


async def on_connection_created(event: OutboxEvent) -> None:
    """Every open, available A item of the engagement the client connected from."""
    await _run(event.tenant_id, UUID(str(event.payload["engagement_id"])), None)


async def on_item_classified(event: OutboxEvent) -> None:
    """One item that became A with a dataset."""
    await _run(
        event.tenant_id,
        UUID(str(event.payload["engagement_id"])),
        UUID(str(event.payload["request_item_id"])),
    )
