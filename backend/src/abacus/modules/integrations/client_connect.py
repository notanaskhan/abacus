"""POR-16's cards and actions, composed from the honest catalogue and the entity's connections
(A-02-T16; TASK-1416; SPEC-333 AC-35 to AC-43; C20 v1; ADR-040, ADR-108; DEC-514).

Every route authorises first, through `connections` (an engagement of the entity: walls and
other clients' entities answer 404, INV-3/INV-4), then reads the flag `connections.portal_v2`
(404 off), then acts. The catalogue decides what may be listed (a row whose adapter is not
registered here is never `available`, AC-49); `connections` holds what the client connected.

- Cards: one per listed catalogue row, or one per live connection of that row's system. Status
  words are C2's `integration` codes: `connected`, `needs_reauth` (token expired or grant
  revoked), `needs_attention` (any other failure), `available` ("Not connected"),
  `coming_soon`, `disconnected`. Every ledger card offers *Export instead* (ADR-108); a ledger
  with no adapter here offers only that. Scopes are the catalogue's read scopes; no write scope
  or copy exists (DF-19).
- Start checks the authorization toggle (`authorization_required`), the catalogue's honesty
  (`connector_not_available`) and its consent version (`consent_version_stale`), then hands the
  consent as shown to `connections.start_entity`.
- Client actions (connect, reconnect, disconnect) are offered to a client only; the firm reads
  details and may retry where the matrix allows.

Copy is catalogue content (the consent sheet's title, lists, toggle sentence and button); the
names and labels a client system sent are rendered as text by the screen (ADR-052).
"""

from __future__ import annotations

from typing import cast
from uuid import UUID

from abacus.kernel._flags import CONNECTIONS_PORTAL_V2
from abacus.kernel._statuses import IntegrationStatus
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.connections.api import (
    AuthorizationRequired,
    ConnectionDetail,
    ConnectorNotAvailable,
    ConnectTarget,
    ConsentShown,
    ConsentVersionStale,
    EntityConnectionView,
    authorised_engagement,
    connection_detail,
    disconnect,
    entity_connections,
    entity_of_connection,
    retry,
    start_entity,
)
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, allowed_actions, firm_name
from abacus.modules.integrations.catalog import CatalogEntry, CatalogRow, client_catalog
from abacus.modules.integrations.catalog_load import ConsentCopyIn
from abacus.modules.integrations.contract import (
    CardAction,
    ConnectionActivityOut,
    ConnectionPersonOut,
    ConnectionScopeOut,
    ConnectionStartIn,
    ConnectionStartOut,
    ConsentCopyOut,
    ExportInsteadOut,
    PortalConnectionCardOut,
    PortalConnectionDetailOut,
    PortalConnectionsOut,
    PortalEntityOut,
    StatusReason,
    SyncRunRefOut,
    SyncRunSummaryOut,
    SyncStatus,
    SyncTrigger,
    Tone,
)
from abacus.modules.organisations.api import entity_display_name

REAUTH = frozenset({"token_expired", "invalid_grant"})


async def _flag(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, CONNECTIONS_PORTAL_V2):
        raise NotFound(CONNECTIONS_PORTAL_V2.name)


def _status(c: EntityConnectionView | None, entry: CatalogEntry) -> IntegrationStatus:
    if c is None:
        return (
            IntegrationStatus.AVAILABLE
            if entry.listing == "available"
            else IntegrationStatus.COMING_SOON
        )
    if c.status == "revoked":
        return IntegrationStatus.DISCONNECTED
    if c.status == "needs_attention":
        return (
            IntegrationStatus.NEEDS_REAUTH
            if c.status_reason in REAUTH
            else IntegrationStatus.NEEDS_ATTENTION
        )
    return IntegrationStatus.CONNECTED


def _consent(row: CatalogRow) -> ConsentCopyOut | None:
    copy = row.consent_copy
    if copy is None or row.consent_version is None:
        return None
    shown = ConsentCopyIn.model_validate(copy)  # the load's schema: content, not code
    return ConsentCopyOut(
        version=row.consent_version,
        title=shown.title,
        will=list(shown.will),
        wont=list(shown.wont),
        authorization=shown.authorization,
        continue_label=shown.continue_label,
        helper=shown.helper,
    )


def _actions(
    status: IntegrationStatus, entry: CatalogEntry, *, client: bool, may_retry: bool
) -> list[CardAction]:
    ledger = entry.row.category == "ledger"
    available = entry.listing == "available"
    out: list[CardAction] = []
    if (
        client
        and available
        and status in (IntegrationStatus.AVAILABLE, IntegrationStatus.DISCONNECTED)
    ):
        out.append("connect")
    if client and available and status == IntegrationStatus.NEEDS_REAUTH:
        out.append("reconnect")
    if status == IntegrationStatus.NEEDS_ATTENTION and may_retry:
        out.append("retry")
    if status in (
        IntegrationStatus.CONNECTED,
        IntegrationStatus.NEEDS_REAUTH,
        IntegrationStatus.NEEDS_ATTENTION,
    ):
        out.append("details")
    if client and status in (IntegrationStatus.CONNECTED, IntegrationStatus.NEEDS_ATTENTION):
        out.append("disconnect")
    if ledger:
        out.append("export_instead")  # ADR-108: beside every ledger Connect, and alone without
    return out


def _card(
    entry: CatalogEntry,
    c: EntityConnectionView | None,
    *,
    client: bool,
    may_retry: bool,
) -> PortalConnectionCardOut:
    row = entry.row
    status = _status(c, entry)
    person = (
        ConnectionPersonOut(
            user_id=c.connected_by_user_id,
            display_name=c.connected_by_name or "",
            kind="client",  # only the client's Owner holds connection.create
        )
        if c is not None and c.connected_by_user_id is not None
        else None
    )
    live = c is not None and c.status != "revoked"
    return PortalConnectionCardOut(
        catalog_key=row.key,
        name=row.name,
        category=row.category,  # pyright: ignore[reportArgumentType] -- the catalogue's CHECK
        icon=row.icon,
        tone=cast(Tone, row.tone),
        status=status,
        status_reason=cast(StatusReason | None, c.status_reason if live and c else None),
        connection_id=c.id if live and c else None,
        display_label=c.display_label if c else None,
        connected_by=person if live else None,
        connected_at=c.connected_at if live and c else None,
        reconnected=bool(live and c and c.reconnected),
        last_sync_at=c.last_sync_at if live and c else None,
        last_failed_at=c.last_failed_at if live and c else None,
        reauth_requested_at=c.reauth_requested_at if live and c else None,
        helper=None,
        scopes=[ConnectionScopeOut(code=code, label=label) for code, label in row.read_scopes],
        consent=_consent(row),
        export_instead=ExportInsteadOut() if row.category == "ledger" else None,
        version=c.version if c else 0,
        allowed_actions=_actions(status, entry, client=client, may_retry=may_retry),
    )


async def _may_retry(ctx: AuthContext, engagement_id: UUID) -> bool:
    ref = await get_ref(ctx, engagement_id)
    return "connection.retry" in await allowed_actions(ctx, ref.resource(), ["connection.retry"])


async def portal_cards(ctx: AuthContext, entity_id: UUID) -> PortalConnectionsOut:
    """POR-16 a (AC-35, AC-43)."""
    facts = await entity_connections(ctx, entity_id)  # authorises `connection.read`
    await _flag(ctx)
    may_retry = await _may_retry(ctx, facts.engagement_id)
    items: list[PortalConnectionCardOut] = []
    for entry in await client_catalog(ctx.tenant):
        mine = [c for c in facts.connections if c.provider == entry.row.connector_provider]
        if not mine:
            items.append(_card(entry, None, client=facts.is_client, may_retry=may_retry))
        for c in mine:
            items.append(_card(entry, c, client=facts.is_client, may_retry=may_retry))
    return PortalConnectionsOut(
        entity=PortalEntityOut(
            client_entity_id=entity_id,
            display_name=await entity_display_name(ctx.tenant, entity_id) or "",
        ),
        firm_display_name=await firm_name(ctx.tenant_id),
        items=items[:50],
    )


async def _entry(
    ctx: AuthContext, *, key: str | None = None, provider: str | None = None
) -> CatalogEntry | None:
    for entry in await client_catalog(ctx.tenant):
        if (key is not None and entry.row.key == key) or (
            provider is not None and entry.row.connector_provider == provider
        ):
            return entry
    return None


async def start_card(
    ctx: AuthContext, entity_id: UUID, catalog_key: str, body: ConnectionStartIn
) -> ConnectionStartOut:
    """POR-16 b, e (AC-36, AC-37): authorise, flag, the toggle, the catalogue, then start."""
    await authorised_engagement(ctx, entity_id, "connection.create")
    await _flag(ctx)
    if not body.authorized:
        raise AuthorizationRequired(catalog_key)
    entry = await _entry(ctx, key=catalog_key)
    if entry is None:
        raise NotFound("catalog_key")
    row = entry.row
    consent = _consent(row)
    if entry.listing != "available" or row.connector_provider is None or consent is None:
        raise ConnectorNotAvailable(catalog_key)
    if body.consent_version != consent.version:
        raise ConsentVersionStale(catalog_key)
    started = await start_entity(
        ctx,
        entity_id,
        ConnectTarget(row.connector_provider, row.category),
        ConsentShown(
            row.key,
            consent.version,
            tuple(consent.will),
            tuple(consent.wont),
            consent.authorization,
        ),
        authorized=body.authorized,
        connection_id=body.connection_id,
    )
    return ConnectionStartOut(
        consent_id=started.consent_id,
        authorise_url=started.authorise_url,
        expires_at=started.expires_at,
    )


def _sync(trigger: str, status: str) -> tuple[SyncTrigger, SyncStatus]:
    return cast(SyncTrigger, trigger), cast(SyncStatus, status)


async def detail_of(ctx: AuthContext, connection_id: UUID) -> PortalConnectionDetailOut:
    """The details drawer: the card, the last 5 sync runs and the activity (AC-42)."""
    found: ConnectionDetail = await connection_detail(ctx, connection_id)  # authorises
    await _flag(ctx)
    entry = await _entry(ctx, provider=found.connection.provider)
    if entry is None:
        raise NotFound("connection")
    may_retry = await _may_retry(ctx, found.engagement_id)
    card = _card(entry, found.connection, client=found.is_client, may_retry=may_retry)
    return PortalConnectionDetailOut(
        card=card,
        recent_syncs=[
            SyncRunSummaryOut(
                sync_run_id=r.id,
                trigger=_sync(r.trigger, r.status)[0],
                status=_sync(r.trigger, r.status)[1],
                started_at=r.started_at,
                finished_at=r.finished_at,
                failure_code=r.failure_code,
            )
            for r in found.recent
        ],
        activity=[
            ConnectionActivityOut(action=a.action, text=a.text, at=a.at) for a in found.activity
        ],
    )


async def retry_card(
    ctx: AuthContext, connection_id: UUID, idempotency_key: str | None = None
) -> SyncRunRefOut:
    """POR-16 g *Try again* (AC-40); a repeated `Idempotency-Key` answers the first response."""
    entity_id = await entity_of_connection(ctx, connection_id)
    await authorised_engagement(ctx, entity_id, "connection.retry")
    await _flag(ctx)

    async def run() -> tuple[int, dict[str, object]]:
        found = await retry(ctx, connection_id)
        out = SyncRunRefOut(sync_run_id=found.id, status=cast(SyncStatus, found.status))
        return 202, out.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="connection.retry",
        key=idempotency_key,
        body={"connection_id": str(connection_id)},
        run=run,
    )
    return SyncRunRefOut.model_validate(stored.body)


async def disconnect_card(
    ctx: AuthContext, connection_id: UUID, seen_version: int, idempotency_key: str | None = None
) -> PortalConnectionCardOut:
    """POR-16 f (AC-39): the card after the disconnect, "Disconnected"; a repeated
    `Idempotency-Key` answers the first response."""
    entity_id = await entity_of_connection(ctx, connection_id)
    await authorised_engagement(ctx, entity_id, "connection.disconnect")
    await _flag(ctx)

    async def run() -> tuple[int, dict[str, object]]:
        view = await disconnect(ctx, connection_id, seen_version)
        entry = await _entry(ctx, provider=view.provider)
        if entry is None:
            raise NotFound("connection")
        card = _card(entry, view, client=ctx.client, may_retry=False)
        return 200, card.model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="connection.disconnect",
        key=idempotency_key,
        body={"connection_id": str(connection_id), "seen_version": seen_version},
        run=run,
    )
    return PortalConnectionCardOut.model_validate(stored.body)
