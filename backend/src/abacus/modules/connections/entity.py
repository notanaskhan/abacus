"""Entity-scoped connections: POR-16's service (A-02-T16; TASK-1416; SPEC-333 AC-35 to AC-42;
C20 v1; ADR-040, ADR-108; DEC-514).

A client connects, reconnects, retries and disconnects the systems of one client entity; the
firm reads them. Every action is authorised on an engagement of the entity (`connection.read`,
`.create`, `.retry`, `.disconnect` are engagement actions, never firm-wide: DEC-316): the first
of the entity's engagements on which the person may act. Where none admits them and every
refusal was one that hides the engagement (another firm, a wall, another client's scope, no
relationship), the entity answers 404 (INV-4); any other refusal (a role, fresh MFA,
independence) is the 403 it is.

- **Start** writes the consent exactly as shown (catalogue key and version, will and won't, the
  authorization sentence, the person, a SHA-256 of the tenant and their address) and a
  hashed, single-use state bound to the person, the entity, that consent and (for a reconnect)
  the connection; then answers the provider's sign-in URL. Sign-in happens on the provider's
  site; the portal never sees a password.
- **Complete** spends the state first, in its own unit of work (reused, expired or someone
  else's: `invalid_state`, nothing created), exchanges the code, and either re-authorises the
  named connection in place (`connection.reauthorized`, open reconnect requests fulfilled) or
  creates one (`connection.created`; one live ledger per entity). The consent's link to the
  connection is written once.
- **Retry** runs one retry of the connection's newest failed run; while a run is live, the same
  run is answered. **Disconnect** crypto-erases the secret and revokes the connection; received
  snapshots and evidence stay (ADR-004).
- Every event a client causes carries `client_actor=1`, so the activity reads
  "Connected by Tess Moreno (client)" (INV-5). Provider text is never kept: codes only (ADR-052).
"""

from __future__ import annotations

import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel import request_context
from abacus.kernel._flags import CONNECTIONS_PORTAL_V2
from abacus.kernel.clock import system_now
from abacus.kernel.crypto import seal
from abacus.kernel.db import tenant_session
from abacus.kernel.egress import check_sign_in_url
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork, audit_of_targets, uow
from abacus.modules.connections.connect import (
    STATE_TTL,
    ConnectionFailed,
    InvalidState,
    LedgerAlreadyConnected,
    code_ref,
    finish_legacy,
    hash_state,
    oauth_providers,
    open_verifier,
    pkce_pair,
    redirect_uri,
    seal_verifier,
    spend,
    unsaved_connection,
)
from abacus.modules.connections.connector import ConnectorError
from abacus.modules.connections.events import (
    ConnectionCreated,
    ConnectionReauthorized,
    ConnectionRevoked,
)
from abacus.modules.connections.grants import abandon_grant, failure_code, retire_grant
from abacus.modules.connections.models import Connection, ConnectionState, SyncRun
from abacus.modules.connections.repository import (
    LIVE,
    fulfil_reconnect_requests,
    get_connection,
    insert_consent,
    insert_consent_link,
    insert_entity_connection,
    insert_retry_run,
    insert_secret,
    insert_state,
    last_failures,
    last_success_on,
    latest_failed_run,
    live_connections_of,
    lock_connection,
    open_reconnect_requests,
    recent_runs,
    running_run_of,
    set_connection,
)
from abacus.modules.connections.retrievals import ensure_workflow
from abacus.modules.connections.service import connector_for
from abacus.modules.engagements.api import (
    EngagementRef,
    engagements_of_entity,
    gate_client_data,
    get_ref,
    lock_ref,
)
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    allowed_actions,
    authorise,
    names_of,
)
from abacus.modules.requests.api import ItemNotFulfillable, item_ref

# Reasons a connection needs its client to sign in again (A-02 §3.11); any other failure is
# `needs_attention` that a retry may clear.
REAUTH_REASONS: Final = frozenset({"token_expired", "invalid_grant"})
RECENT_RUNS: Final = 5
# Refusals that must not confirm the entity exists for this person (INV-3, INV-4).
_HIDDEN: Final = frozenset({"tenancy", "wall", "client_scope", "relationship"})
# The activity's verbs (ADM-07 grammar, INV-5).
VERBS: Final = {
    "connection.created": "Connected",
    "connection.reauthorized": "Reconnected",
    "connection.revoked": "Disconnected",
}
ACTIVITY_LIMIT: Final = 50


class AuthorizationRequired(DomainInvalid):
    """The consent sheet's authorization toggle was not on (AC-36)."""

    code = "authorization_required"


class ConsentVersionStale(DomainConflict):
    """The consent copy shown is older than the catalogue's: read the cards again."""

    code = "consent_version_stale"


class ConnectorNotAvailable(DomainConflict):
    """No adapter for this system is registered here (catalogue honesty, AC-49)."""

    code = "connector_not_available"


class ConnectionNeedsReauth(DomainConflict):
    """The client must sign in again before anything is pulled."""

    code = "connection_needs_reauth"


class StaleConnection(DomainConflict):
    """The connection changed since it was read (`seen_version`)."""

    code = "stale_version"


class NoFailedSync(DomainConflict):
    """There is no failed sync to try again."""

    code = "no_failed_sync"


class RetryUnavailable(DomainConflict):
    """Only a run a request item asked for can be retried until on-demand runs land (A-02-T30)."""

    code = "retry_unavailable"


@dataclass(frozen=True)
class ConsentShown:
    """What the client saw on the sheet, from the catalogue (content, not code)."""

    catalog_key: str
    version: int
    will: tuple[str, ...]
    wont: tuple[str, ...]
    authorization: str


@dataclass(frozen=True)
class ConnectTarget:
    """The system to connect: its connector provider code and catalogue category."""

    provider: str
    category: str


@dataclass(frozen=True)
class EntityConnectionView:
    id: UUID
    provider: str
    category: str
    status: str  # active | needs_attention | revoked (the bridge to C2 words is the caller's)
    status_reason: str | None
    display_label: str | None
    connected_by_user_id: UUID | None
    connected_by_name: str | None
    connected_at: datetime | None
    reconnected: bool
    last_sync_at: datetime | None
    last_failed_at: datetime | None
    reauth_requested_at: datetime | None
    version: int


@dataclass(frozen=True)
class EntityConnections:
    engagement_id: UUID  # the engagement the read was authorised on
    client_entity_id: UUID
    is_client: bool
    connections: list[EntityConnectionView]


@dataclass(frozen=True)
class Started:
    consent_id: UUID
    authorise_url: str
    expires_at: datetime


@dataclass(frozen=True)
class Completed:
    engagement_id: UUID
    client_entity_id: UUID
    connection_id: UUID | None
    reconnected: bool


@dataclass(frozen=True)
class RunSummary:
    id: UUID
    trigger: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    failure_code: str | None


@dataclass(frozen=True)
class ActivityLine:
    action: str
    text: str  # "Connected by Tess Moreno (client)"
    at: datetime


@dataclass(frozen=True)
class ConnectionDetail:
    connection: EntityConnectionView
    engagement_id: UUID
    is_client: bool
    recent: list[RunSummary]
    activity: list[ActivityLine]


@dataclass(frozen=True)
class RunRef:
    id: UUID
    status: str


# --- authorisation -------------------------------------------------------------------------------


async def authorised_engagement(ctx: AuthContext, entity_id: UUID, action: str) -> EngagementRef:
    """The newest engagement of the entity on which `ctx` may take `action`; 404 when every
    refusal hides the engagement, else the first other refusal (403)."""
    shown: Forbidden | None = None
    for engagement_id in await engagements_of_entity(ctx.tenant, entity_id):
        ref = await get_ref(ctx, engagement_id)
        if ref.client_entity_id != entity_id:
            continue
        try:
            await authorise(ctx, action, ref.resource())
        except Forbidden as refused:
            if refused.layer not in _HIDDEN and shown is None:
                shown = refused
            continue
        return ref
    if shown is not None:
        raise shown
    raise NotFound("client_entity")


async def _relock(tx: UnitOfWork, ctx: AuthContext, ref: EngagementRef, action: str) -> None:
    """Authorise again on the locked row, so the check and the write see the same engagement."""
    locked = await lock_ref(tx, ref.id)
    await authorise(ctx, action, locked.resource())


def _client_actor(ctx: AuthContext) -> dict[str, int]:
    return {"client_actor": 1} if ctx.client else {}


def _ip_sha256(ctx: AuthContext) -> str:
    """A SHA-256 of the tenant and the caller's address; the address itself is never kept."""
    found = request_context.current()
    address = (found.ip if found is not None else None) or "unknown"
    return hashlib.sha256(f"{ctx.tenant_id}:{address}".encode()).hexdigest()


# --- reads ---------------------------------------------------------------------------------------


def _view(
    c: Connection,
    names: dict[UUID, str],
    failures: dict[UUID, datetime],
    requests: dict[UUID, datetime],
    pulled: datetime | None,
) -> EntityConnectionView:
    who = c.connected_by_user_id
    return EntityConnectionView(
        id=c.id,
        provider=c.provider,
        category=c.category,
        status=c.status,
        status_reason=c.status_reason_code,
        display_label=c.display_label,
        connected_by_user_id=who,
        connected_by_name=names.get(who) if who is not None else None,
        connected_at=c.connected_at,
        reconnected=c.connected_at is not None and c.connected_at > c.created_at,
        last_sync_at=c.last_sync_at or pulled,
        last_failed_at=failures.get(c.id),
        reauth_requested_at=requests.get(c.id),
        version=c.version,
    )


async def readable_engagements(
    ctx: AuthContext, entity_id: UUID, action: str = "connection.read"
) -> list[UUID]:
    """The entity's engagements whose runs the person may read (`connection.read` on each,
    probed without recording or logging a denial): a wall on one engagement of the entity hides
    its runs while another engagement's stay readable (review L7)."""
    out: list[UUID] = []
    for engagement_id in await engagements_of_entity(ctx.tenant, entity_id):
        ref = await get_ref(ctx, engagement_id)
        if action in await allowed_actions(ctx, ref.resource(), [action]):
            out.append(engagement_id)
    return out


async def _views(ctx: AuthContext, rows: Sequence[Connection]) -> list[EntityConnectionView]:
    ids = [c.id for c in rows]
    entities = {c.client_entity_id for c in rows}
    readable = [
        e for entity in sorted(entities, key=str) for e in await readable_engagements(ctx, entity)
    ]
    async with tenant_session(ctx.tenant) as session:
        failures = await last_failures(session, ids, readable)
        requests = await open_reconnect_requests(session, ids)
        pulled = {c.id: await last_success_on(session, c.id, readable) for c in rows}
    people = sorted({c.connected_by_user_id for c in rows if c.connected_by_user_id}, key=str)
    names = await names_of(people) if people else {}
    return [_view(c, names, failures, requests, pulled[c.id]) for c in rows]


async def entity_connections(ctx: AuthContext, entity_id: UUID) -> EntityConnections:
    """POR-16 a's facts (AC-35): the entity's live connections, as `connection.read` allows."""
    ref = await authorised_engagement(ctx, entity_id, "connection.read")
    async with tenant_session(ctx.tenant) as session:
        rows = await live_connections_of(session, entity_id)
    return EntityConnections(ref.id, entity_id, ctx.client, await _views(ctx, rows))


async def _connection(ctx: AuthContext, connection_id: UUID) -> Connection:
    async with tenant_session(ctx.tenant) as session:
        found = await get_connection(session, connection_id)
    if found is None:
        raise NotFound("connection")
    return found


async def _activity(ctx: AuthContext, connection_id: UUID) -> list[ActivityLine]:
    async with tenant_session(ctx.tenant) as session:
        events = await audit_of_targets(
            session, [("connection", connection_id)], None, ACTIVITY_LIMIT
        )
    shown = [e for e in events if e.action in VERBS]
    people = sorted(
        {UUID(e.actor_id) for e in shown if e.actor_kind in ("human", "support")}, key=str
    )
    names = await names_of(people) if people else {}
    lines: list[ActivityLine] = []
    for e in shown:
        name = names.get(UUID(e.actor_id)) if e.actor_kind in ("human", "support") else None
        client = (e.after_ref or {}).get("client_actor") == 1
        who = f"{name or 'Former member'}{' (client)' if client else ''}"
        if e.actor_kind not in ("human", "support"):
            who = "the platform"
        lines.append(ActivityLine(e.action, f"{VERBS[e.action]} by {who}", e.at))
    return lines


async def entity_of_connection(ctx: AuthContext, connection_id: UUID) -> UUID:
    """The connection's client entity, for a caller about to authorise on it (`NotFound`
    otherwise); never shown to the caller before that."""
    return (await _connection(ctx, connection_id)).client_entity_id


async def connection_detail(ctx: AuthContext, connection_id: UUID) -> ConnectionDetail:
    """The details drawer: who connected it and when, the last 5 sync runs, the activity."""
    found = await _connection(ctx, connection_id)
    ref = await authorised_engagement(ctx, found.client_entity_id, "connection.read")
    async with tenant_session(ctx.tenant) as session:
        runs = await recent_runs(
            session,
            connection_id,
            await readable_engagements(ctx, found.client_entity_id),
            RECENT_RUNS,
        )
    view = (await _views(ctx, [found]))[0]
    return ConnectionDetail(
        view,
        ref.id,
        ctx.client,
        [
            RunSummary(r.id, r.trigger, r.status, r.started_at, r.finished_at, r.failure_code)
            for r in runs
        ],
        await _activity(ctx, connection_id),
    )


# --- start and complete ---------------------------------------------------------------------


def _reconnect_target(
    live: Sequence[Connection], target: ConnectTarget, connection_id: UUID | None
) -> Connection | None:
    """The connection a start re-authorises: the one named, else the only one of this system
    needing attention; a ledger already live otherwise refuses a second (ADR-045)."""
    same = [c for c in live if c.provider == target.provider]
    if connection_id is not None:
        named = next((c for c in same if c.id == connection_id), None)
        if named is None:
            raise NotFound("connection")
        return named
    waiting = [c for c in same if c.status == "needs_attention"]
    if len(waiting) == 1:
        return waiting[0]
    if target.category == "ledger" and any(c.category == "ledger" for c in live):
        raise LedgerAlreadyConnected(target.provider)
    return None


async def start_entity(
    ctx: AuthContext,
    entity_id: UUID,
    target: ConnectTarget,
    consent: ConsentShown,
    *,
    authorized: bool,
    connection_id: UUID | None = None,
) -> Started:
    """AC-36, AC-37: authorise (`connection.create`, fresh MFA), refuse without the toggle,
    record the consent as shown and a single-use state, answer the provider's sign-in URL."""
    ref = await authorised_engagement(ctx, entity_id, "connection.create")
    if not authorized:
        raise AuthorizationRequired(consent.catalog_key)
    if target.provider not in oauth_providers():
        raise ConnectorNotAvailable(consent.catalog_key)
    await gate_client_data(ctx, ref.id, "connection.create")  # SPEC-025 AC-7
    state = secrets.token_urlsafe(32)
    verifier, challenge = pkce_pair()
    expires_at = system_now() + STATE_TTL
    async with uow(ctx.tenant) as tx:
        await _relock(tx, ctx, ref, "connection.create")
        live = await live_connections_of(tx.session, entity_id)
        reconnect = _reconnect_target(live, target, connection_id)
        consent_id = await insert_consent(
            tx.session,
            tenant_id=ctx.tenant_id,
            client_entity_id=entity_id,
            catalog_key=consent.catalog_key,
            consent_version=consent.version,
            will=list(consent.will),
            wont=list(consent.wont),
            authorization_text=consent.authorization,
            authorised_by_user_id=ctx.user_id,
            ip_sha256=_ip_sha256(ctx),
        )
        state_id = await insert_state(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=ref.id,
            client_entity_id=entity_id,
            user_id=ctx.user_id,
            provider=target.provider,
            state_hash=hash_state(state),
            expires_at=expires_at,
            consent_id=consent_id,
            connection_id=reconnect.id if reconnect is not None else None,
            category=target.category,
            verifier_sealed=await seal_verifier(ctx.tenant_id, hash_state(state), verifier),
        )
        tx.record(
            "connection.consent_recorded",
            target=Target("connection_state", state_id),
            after=Ref(
                consent_id=consent_id, consent_version=consent.version, **_client_actor(ctx)
            ),
        )
        tx.record(
            "connection.started",
            target=Target("connection_state", state_id),
            after=Ref(engagement_id=ref.id, **_client_actor(ctx)),
        )
    connector = connector_for(unsaved_connection(target.provider, entity_id, ctx))
    url = await connector.authorise_url(state, redirect_uri(), code_challenge=challenge)
    return Started(consent_id, check_sign_in_url(url, target.provider), expires_at)


async def complete_any(ctx: AuthContext, state: str, code: str) -> Completed:
    """`POST /v1/connections/complete` for both flows: the state is spent first (single use,
    this person's, unexpired); a legacy state finishes as SPEC-020 does, a POR-16 one here."""
    found = await spend(ctx, state)
    if found is None:
        raise InvalidState
    if found.consent_id is None:
        engagement_id = await finish_legacy(ctx, found, code)
        return Completed(engagement_id, found.client_entity_id, None, False)
    return await _complete_entity(ctx, found, code)


async def _exchange(ctx: AuthContext, found: ConnectionState, code: str) -> bytes | None:
    await gate_client_data(ctx, found.engagement_id, "connection.create")  # SPEC-025 AC-7
    connector = connector_for(unsaved_connection(found.provider, found.client_entity_id, ctx))
    verifier = await open_verifier(ctx.tenant_id, found)
    try:
        return await connector.exchange_code(code, redirect_uri(), code_verifier=verifier)
    except ConnectorError as exc:
        async with uow(ctx.tenant) as tx:
            tx.record(
                "connection.failed",
                target=Target("connection_state", found.id),
                after=Ref(code=code_ref(exc.code), **_client_actor(ctx)),
            )
        raise ConnectionFailed from None


async def _store_secret(
    tx: UnitOfWork, ctx: AuthContext, connection_id: UUID, credentials: bytes | None
) -> None:
    # The old grant's, on a reconnect: revoked at the provider after commit (review M1).
    await retire_grant(tx, ctx.tenant_id, connection_id, "replaced")
    if credentials is not None:
        sealed = await seal(ctx.tenant_id, credentials, str(connection_id))
        await insert_secret(
            tx.session, tenant_id=ctx.tenant_id, connection_id=connection_id, sealed=sealed
        )


async def _complete_entity(ctx: AuthContext, found: ConnectionState, code: str) -> Completed:
    """Review L9: the flag holds here too (the state was spent first, so a replay is refused)."""
    if not await flag_enabled(ctx.tenant, CONNECTIONS_PORTAL_V2):
        raise NotFound(CONNECTIONS_PORTAL_V2.name)
    credentials = await _exchange(ctx, found, code)
    try:
        return await _record_entity(ctx, found, credentials)
    except Exception as exc:  # review L5, round 2 L3: the fresh grant is queued for revocation
        await abandon_grant(ctx, found, credentials, exc, code_ref(failure_code(exc)))
        raise


async def _record_entity(
    ctx: AuthContext, found: ConnectionState, credentials: bytes | None
) -> Completed:
    entity_id = found.client_entity_id
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, found.engagement_id)
        await authorise(ctx, "connection.create", ref.resource())
        if ref.client_entity_id != entity_id or found.consent_id is None:
            raise InvalidState
        now = system_now()
        if found.connection_id is not None:
            connection = await lock_connection(tx.session, found.connection_id)
            if (
                connection is None
                or connection.status not in LIVE
                or connection.client_entity_id != entity_id
                or connection.provider != found.provider
            ):
                raise InvalidState  # disconnected meanwhile: start again
            await set_connection(
                tx.session,
                connection.id,
                status="active",
                status_reason_code=None,
                reauth_due_at=None,
                connected_by_user_id=ctx.user_id,
                connected_at=now,
            )
            await _store_secret(tx, ctx, connection.id, credentials)
            await fulfil_reconnect_requests(tx.session, connection.id)
            tx.record(
                "connection.reauthorized",
                target=Target("connection", connection.id),
                after=Ref(engagement_id=ref.id, consent_id=found.consent_id, **_client_actor(ctx)),
            )
            tx.emit(
                ConnectionReauthorized(
                    connection_id=connection.id, engagement_id=ref.id, by=ctx.user_id
                )
            )
            reconnected = True
            connection_id = connection.id
        else:
            category = found.category or "ledger"
            live = await live_connections_of(tx.session, entity_id)
            if category == "ledger" and any(c.category == "ledger" for c in live):
                raise LedgerAlreadyConnected(found.provider)
            created = await insert_entity_connection(
                tx.session,
                tenant_id=ctx.tenant_id,
                client_entity_id=entity_id,
                provider=found.provider,
                category=category,
                created_by=str(ctx.user_id),
                connected_by_user_id=ctx.user_id,
                connected_at=now,
            )
            await _store_secret(tx, ctx, created.id, credentials)
            tx.record(
                "connection.created",
                target=Target("connection", created.id),
                after=Ref(
                    engagement_id=ref.id,
                    client_entity_id=entity_id,
                    consent_id=found.consent_id,
                    **_client_actor(ctx),
                ),
            )
            tx.emit(
                ConnectionCreated(connection_id=created.id, engagement_id=ref.id, by=ctx.user_id)
            )
            reconnected = False
            connection_id = created.id
        await insert_consent_link(
            tx.session,
            consent_id=found.consent_id,
            tenant_id=ctx.tenant_id,
            client_entity_id=entity_id,
            connection_id=connection_id,
        )
    return Completed(ref.id, entity_id, connection_id, reconnected)


# --- retry and disconnect -------------------------------------------------------------------


def _summary(run: SyncRun) -> RunRef:
    return RunRef(run.id, run.status)


async def retry(ctx: AuthContext, connection_id: UUID) -> RunRef:
    """AC-40: one retry of the newest failed run (its workflow started); while a run is live it
    is answered again."""
    run, created = await _record_retry(ctx, connection_id)
    if run.status == "running":
        await ensure_workflow(ctx, run.id, created=created)
    return run


async def _record_retry(ctx: AuthContext, connection_id: UUID) -> tuple[RunRef, bool]:
    found = await _connection(ctx, connection_id)
    ref = await authorised_engagement(ctx, found.client_entity_id, "connection.retry")
    if found.status not in LIVE:
        raise NotFound("connection")
    if found.status_reason_code in REAUTH_REASONS:
        raise ConnectionNeedsReauth(str(connection_id))
    retryable = await readable_engagements(ctx, found.client_entity_id, "connection.retry")
    async with uow(ctx.tenant) as tx:
        await _relock(tx, ctx, ref, "connection.retry")
        locked = await lock_connection(tx.session, connection_id)
        if locked is None or locked.status not in LIVE:
            raise NotFound("connection")
        running = await running_run_of(tx.session, connection_id, retryable)
        if running is not None:
            tx.record(
                "connection.retry_requested",
                target=Target("connection", connection_id),
                after=Ref(sync_run_id=running.id, **_client_actor(ctx)),
            )
            return _summary(running), False
        failed = await latest_failed_run(tx.session, connection_id, retryable)
        if failed is None:
            raise NoFailedSync(str(connection_id))
        if failed.trigger != "request_item" or failed.request_item_id is None:
            raise RetryUnavailable(failed.trigger)
        # The run is the failed one's engagement's: the person must be allowed there too.
        await _relock(tx, ctx, await get_ref(ctx, failed.engagement_id), "connection.retry")
        item = await item_ref(tx, failed.request_item_id)
        if item.status not in ("draft", "requested", "uploaded"):
            raise ItemNotFulfillable(item.status)
        run = await insert_retry_run(
            tx.session,
            tenant_id=ctx.tenant_id,
            client_entity_id=found.client_entity_id,
            connection_id=connection_id,
            engagement_id=failed.engagement_id,
            request_item_id=failed.request_item_id,
            trigger="request_item",
            dataset=failed.dataset,
            period_start=failed.period_start,
            period_end=failed.period_end,
            started_by=str(ctx.user_id),
        )
        if run is None:  # a concurrent click won the unique index: answer that run
            raced = await running_run_of(tx.session, connection_id, retryable)
            if raced is None:
                raise NotFound("sync_run")
            return _summary(raced), False
        tx.record(
            "connection.retry_requested",
            target=Target("connection", connection_id),
            after=Ref(sync_run_id=run.id, **_client_actor(ctx)),
        )
        tx.record(
            "sync_run.started",
            target=Target("sync_run", run.id),
            after=Ref(user_id=ctx.user_id, request_item_id=failed.request_item_id),
        )
    return _summary(run), True


async def disconnect(
    ctx: AuthContext, connection_id: UUID, seen_version: int
) -> EntityConnectionView:
    """AC-39: the client Owner disconnects (`connection.disconnect`, fresh MFA): the secret is
    crypto-erased, the status reads Disconnected, and everything received stays."""
    found = await _connection(ctx, connection_id)
    ref = await authorised_engagement(ctx, found.client_entity_id, "connection.disconnect")
    async with uow(ctx.tenant) as tx:
        await _relock(tx, ctx, ref, "connection.disconnect")
        locked = await lock_connection(tx.session, connection_id)
        if locked is None or locked.status not in LIVE:
            raise NotFound("connection")
        if locked.version != seen_version:
            raise StaleConnection(str(connection_id))
        await set_connection(
            tx.session,
            connection_id,
            status="revoked",
            revoked_at=system_now(),
            revoked_by=str(ctx.user_id),
        )
        # The secret goes now; the provider revokes the grant after commit (review M1).
        await retire_grant(tx, ctx.tenant_id, connection_id, "disconnected")
        tx.record(
            "connection.revoked",
            target=Target("connection", connection_id),
            after=Ref(engagement_id=ref.id, **_client_actor(ctx)),
        )
        tx.emit(
            ConnectionRevoked(connection_id=connection_id, engagement_id=ref.id, by=ctx.user_id)
        )
    return (await _views(ctx, [await _connection(ctx, connection_id)]))[0]
