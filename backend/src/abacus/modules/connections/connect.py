"""The client connection flow, health, access log and revoke (SPEC-020; TASK-036). PROTECTED.

A client admin starts a flow (`connection.create`, fresh MFA): a random state is kept only as
its hash, bound to them, the engagement and its client entity, for ten minutes. The provider
sends the browser back to the SPA, which completes the flow with the same person's token (D1).
Credentials are sealed with the tenant's key (ADR-035) and deleted on revoke. Provider text is
never kept or shown: only codes (ADR-052).

A-02-T33 (DEC-3902): the provider returns every firm's flow to one registered host
(`connections_redirect_base_url`, `connect.<domain>`), where no session is valid (a portal
session is pinned to its firm's host, ADR-163 §5). So the state also keeps the host the flow
began on, and `handoff_origin` (the one unauthenticated step, `POST /v1/connections/handoff`,
pre-session) answers that host for a live state, for the page to send the browser on to it.
It never spends the state: completion stays here, with the person's own token.
"""

from __future__ import annotations

import base64
import hashlib
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Final
from uuid import UUID

from abacus.kernel._flags import CONNECTIONS_PORTAL_V2
from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, platform_transaction, tenant_session
from abacus.kernel.egress import check_sign_in_url
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.connections.connector import ConnectorError
from abacus.modules.connections.events import ConnectionCreated, ConnectionRevoked
from abacus.modules.connections.grants import abandon_grant, failure_code, retire_grant
from abacus.modules.connections.models import Connection, ConnectionState, SyncRun
from abacus.modules.connections.repository import (
    has_consent_link,
    insert_connection,
    insert_secret,
    insert_state,
    last_success,
    list_access_log,
    live_connection_for,
    lock_state,
    secret_of,
    set_connection,
    spend_state,
    state_origin,
)
from abacus.modules.connections.service import connector_for
from abacus.modules.engagements.api import gate_client_data, get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, authorise

STATE_TTL: Final = timedelta(minutes=10)
LOG_PAGE: Final = 50
CALLBACK_PATH: Final = "/client/connect/callback"
# Providers by environment (SPEC-020 Q1): the demo ledger only where the fake connector may run.
PROVIDER_NAMES: Final = {"fake": "Demo ledger"}
# A host name of one label or more, as 0790's CHECK has it; no port, no trailing dot.
_HOST_NAME: Final = re.compile(
    r"[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?(\.[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?)*"
)
_HANDOFF_ACTOR: Final = "connections:handoff"


class UnknownProvider(DomainInvalid):
    code = "unknown_provider"


class InvalidState(DomainConflict):
    """The state is unknown, someone else's, already used or expired: nothing is created."""

    code = "invalid_state"


class ConnectionFailed(DomainConflict):
    """The provider refused or failed the exchange (its code, never its text, is logged)."""

    code = "connection_failed"


class NoLiveConnection(DomainConflict):
    code = "no_connection"


class ConnectionFlowMoved(DomainConflict):
    """POR-16 is on for the firm: a client connects from Connections, with the consent sheet
    (A-02-T16 review M2). The engagement page no longer starts a flow."""

    code = "connection_flow_moved"


class LedgerAlreadyConnected(DomainConflict):
    """The entity has a live ledger connection already (one per entity, ADR-045); a ledger the
    client connected with a consent is never replaced by a flow without one."""

    code = "ledger_already_connected"


@dataclass(frozen=True)
class ProviderView:
    provider: str
    name: str
    datasets: tuple[str, ...]


@dataclass(frozen=True)
class Started:
    authorise_url: str


@dataclass(frozen=True)
class ConnectionView:
    id: UUID
    provider: str
    status: str
    scopes: tuple[str, ...]
    created_by: str
    created_at: datetime
    expires_at: datetime | None
    last_checked_at: datetime | None
    last_check_ok: bool | None
    last_pull_at: datetime | None


@dataclass(frozen=True)
class LogEntry:
    id: UUID
    dataset: str
    period_start: str
    period_end: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    started_by: str


def _redirect_uri() -> str:
    """The OAuth callback: the one registered redirect host (A-02-T33), else the app's own."""
    config = settings()
    return f"{config.connections_redirect_base_url or config.app_base_url}{CALLBACK_PATH}"


def origin_host(host: str | None) -> str | None:
    """The request's viewer host (`kernel.viewer_host`, DEC-3990) as a host name: lower case,
    without its port or a trailing dot; None for anything that is not a host name (never handed
    on)."""
    name = (host or "").strip().lower()
    if name.count(":") == 1:
        name = name.split(":", 1)[0]
    name = name.rstrip(".")
    return name if len(name) <= 253 and _HOST_NAME.fullmatch(name) else None


def app_host() -> str:
    """The firm app's host, from configuration: a staff sign-in's flow begins there."""
    authority = settings().app_base_url.split("://", 1)[-1].split("/", 1)[0]
    return origin_host(authority.rsplit("@", 1)[-1]) or ""


async def handoff_origin(state: str) -> str:
    """A-02-T33: the host a live state's flow began on, for the connect host's page to send the
    provider's answer back to. `NotFound` (one answer) for a state that is unknown, used or
    expired, or whose host is not the app host or an active portal host of its own firm. No
    tenant is named or needed, and the state is not spent."""
    async with platform_transaction(_HANDOFF_ACTOR) as conn:
        found = await state_origin(conn, _hash(state), app_host())
    if found is None:
        raise NotFound("connection_state")
    return found


def _hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def _available() -> tuple[str, ...]:
    return ("fake",) if settings().fake_connector_dir is not None else ()


async def providers(ctx: AuthContext, engagement_id: UUID) -> list[ProviderView]:
    """What this client may connect, here (a client admin's view; `connection.create`'s roles)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "connection.read_log", ref.resource())
    return [ProviderView(p, PROVIDER_NAMES[p], ("trial_balance",)) for p in _available()]


def pkce_pair() -> tuple[str, str]:
    """A PKCE verifier and its S256 challenge (RFC 7636; review L6)."""
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _verifier_binding(state_hash: str) -> str:
    return f"connection_state:{state_hash}"


async def seal_verifier(tenant_id: UUID, state_hash: str, verifier: str) -> bytes:
    return await seal(tenant_id, verifier.encode("ascii"), _verifier_binding(state_hash))


async def open_verifier(tenant_id: UUID, found: ConnectionState) -> str | None:
    if found.verifier_sealed is None:
        return None
    opened = await open_sealed(
        tenant_id, found.verifier_sealed, _verifier_binding(found.state_hash)
    )
    return opened.decode("ascii")


async def start(
    ctx: AuthContext, engagement_id: UUID, provider: str, *, host: str | None = None
) -> Started:
    """AC-2, AC-3: authorise (fresh MFA), keep the hashed state, return the provider's URL.
    A-02-T16 review M2: refused once POR-16 is on for the firm (the consent sheet is there).
    A-02-T33: `host` is the request's own `Host`, kept for the connect host's hand-off."""
    if provider not in _available():
        raise UnknownProvider
    await gate_client_data(ctx, engagement_id, "connection.create")  # SPEC-025 AC-7
    state = secrets.token_urlsafe(32)
    verifier, challenge = pkce_pair()
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "connection.create", ref.resource())
        if await flag_enabled(ctx.tenant, CONNECTIONS_PORTAL_V2):
            raise ConnectionFlowMoved(str(engagement_id))
        state_id = await insert_state(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            client_entity_id=ref.client_entity_id,
            user_id=ctx.user_id,
            provider=provider,
            state_hash=_hash(state),
            expires_at=system_now() + STATE_TTL,
            verifier_sealed=await seal_verifier(ctx.tenant_id, _hash(state), verifier),
            origin_host=origin_host(host),
        )
        tx.record(
            "connection.started",
            target=Target("connection_state", state_id),
            after=Ref(engagement_id=engagement_id),
        )
    connector = connector_for(_unsaved(provider, ref.client_entity_id, ctx))
    url = await connector.authorise_url(state, _redirect_uri(), code_challenge=challenge)
    return Started(check_sign_in_url(url, provider))


def _unsaved(provider: str, client_entity_id: UUID, ctx: AuthContext) -> Connection:
    """A connection not yet stored, for the provider's authorise and exchange calls."""
    return Connection(
        id=UUID(int=0),
        tenant_id=ctx.tenant_id,
        client_entity_id=client_entity_id,
        provider=provider,
        status="active",
        scopes=[],
        created_by=str(ctx.user_id),
    )


async def complete(ctx: AuthContext, state: str, code: str) -> UUID:
    """AC-2: finish the flow the same person started. The state is spent whatever happens;
    a reused, expired or mismatched one is refused and nothing is created. Returns the
    engagement, for the SPA to return to. A-02-T16: a state POR-16 started (it names a consent)
    finishes through `entity.complete_entity`; this one finishes the legacy engagement flow."""
    found = await spend(ctx, state)
    if found is None or found.consent_id is not None:
        raise InvalidState
    return await finish_legacy(ctx, found, code)


async def finish_legacy(ctx: AuthContext, found: ConnectionState, code: str) -> UUID:
    """The SPEC-020 completion of a spent legacy state: the entity's live ledger is replaced."""
    engagement_id, client_entity_id, provider = (
        found.engagement_id,
        found.client_entity_id,
        found.provider,
    )
    await gate_client_data(ctx, engagement_id, "connection.create")  # SPEC-025 AC-7
    connector = connector_for(_unsaved(provider, client_entity_id, ctx))
    verifier = await open_verifier(ctx.tenant_id, found)
    try:
        credentials = await connector.exchange_code(code, _redirect_uri(), code_verifier=verifier)
    except ConnectorError as exc:
        async with uow(ctx.tenant) as tx:
            tx.record(
                "connection.failed",
                target=Target("engagement", engagement_id),
                after=Ref(code=_code_ref(exc.code)),
            )
        raise ConnectionFailed from None
    try:
        return await _record_legacy(ctx, found, credentials)
    except Exception as exc:  # review round 2 L2: the fresh grant is queued for revocation
        await abandon_grant(ctx, found, credentials, exc, _code_ref(failure_code(exc)))
        raise


async def _record_legacy(
    ctx: AuthContext, found: ConnectionState, credentials: bytes | None
) -> UUID:
    engagement_id, client_entity_id, provider = (
        found.engagement_id,
        found.client_entity_id,
        found.provider,
    )
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "connection.create", ref.resource())
        old = await live_connection_for(tx.session, client_entity_id, lock=True)
        if old is not None and await has_consent_link(tx.session, old.id):
            raise LedgerAlreadyConnected(provider)  # review M2: a consented ledger stays
        if old is not None:
            await _revoke(tx, ctx, old, engagement_id)
        connection = await insert_connection(
            tx.session,
            tenant_id=ctx.tenant_id,
            client_entity_id=client_entity_id,
            provider=provider,
            created_by=str(ctx.user_id),
        )
        if credentials is not None:
            sealed = await seal(ctx.tenant_id, credentials, str(connection.id))
            await insert_secret(
                tx.session, tenant_id=ctx.tenant_id, connection_id=connection.id, sealed=sealed
            )
        tx.record(
            "connection.created",
            target=Target("connection", connection.id),
            after=Ref(engagement_id=engagement_id, client_entity_id=client_entity_id),
        )
        tx.emit(
            ConnectionCreated(
                connection_id=connection.id, engagement_id=engagement_id, by=ctx.user_id
            )
        )
    return engagement_id


def _code_ref(code: str) -> str:
    """A provider's error code as an audit reference (fingerprints only, never text)."""
    return hashlib.sha256(code.encode()).hexdigest()


async def spend(ctx: AuthContext, state: str) -> ConnectionState | None:
    """Mark the state used (in its own unit of work, so it stays spent if anything later fails)
    and return it, if it was this person's, unused and unexpired (A-02-T16: single use, bound to
    the tenant by row-level security, to the person, and to its entity and consent)."""
    async with uow(ctx.tenant) as tx:
        row = await lock_state(tx.session, _hash(state))
        if row is None:
            tx.record("connection.state_refused", target=Target("user", ctx.user_id))
            return None
        valid = (
            row.used_at is None and row.user_id == ctx.user_id and row.expires_at > system_now()
        )
        if row.used_at is None:
            await spend_state(tx.session, row.id)
        tx.record(
            "connection.state_used" if valid else "connection.state_refused",
            target=Target("connection_state", row.id),
        )
        return row if valid else None


async def _live(tx: UnitOfWork, client_entity_id: UUID) -> Connection:
    connection = await live_connection_for(tx.session, client_entity_id, lock=True)
    if connection is None:
        raise NoLiveConnection
    return connection


async def _revoke(
    tx: UnitOfWork, ctx: AuthContext, connection: Connection, engagement_id: UUID
) -> None:
    await set_connection(
        tx.session,
        connection.id,
        status="revoked",
        revoked_at=system_now(),
        revoked_by=str(ctx.user_id),
    )
    await retire_grant(tx, ctx.tenant_id, connection.id, "disconnected")  # review M1
    tx.record(
        "connection.revoked",
        target=Target("connection", connection.id),
        after=Ref(engagement_id=engagement_id),
    )
    tx.emit(
        ConnectionRevoked(connection_id=connection.id, engagement_id=engagement_id, by=ctx.user_id)
    )


async def revoke(ctx: AuthContext, engagement_id: UUID) -> None:
    """AC-6: pulls stop at once (`pull_raw` refuses a non-active connection), the credentials
    are destroyed, and the firm's leads are notified."""
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "connection.revoke", ref.resource())
        await _revoke(tx, ctx, await _live(tx, ref.client_entity_id), engagement_id)


async def credentials_of(tenant: TenantContext, connection: Connection) -> bytes | None:
    """The connection's opened credentials, for a caller that authorised a pull or a check."""
    async with tenant_session(tenant) as session:
        sealed = await secret_of(session, connection.id)
    if sealed is None:
        return None
    return await open_sealed(tenant.tenant_id, sealed, str(connection.id))


async def check(ctx: AuthContext, engagement_id: UUID) -> ConnectionView:
    """AC-4: refresh, then ask the provider; a failure marks the connection as needing
    attention, and a later success restores it."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "connection.check", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        connection = await live_connection_for(session, ref.client_entity_id)
    if connection is None:
        raise NoLiveConnection
    connector = connector_for(connection, await credentials_of(ctx.tenant, connection))
    try:
        await connector.refresh()
        ok = await connector.health()
    except ConnectorError:
        ok = False
    async with uow(ctx.tenant) as tx:
        locked_ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "connection.check", locked_ref.resource())
        current = await _live(tx, ref.client_entity_id)
        if current.id != connection.id:
            raise NoLiveConnection  # replaced meanwhile: check the new one
        status = "active" if ok else "needs_attention"
        await set_connection(
            tx.session,
            current.id,
            status=status,
            last_checked_at=system_now(),
            last_check_ok=ok,
        )
        tx.record(
            "connection.checked",
            target=Target("connection", current.id),
            before=Ref(ok=int(current.last_check_ok))
            if current.last_check_ok is not None
            else None,
            after=Ref(ok=int(ok)),
        )
    view = await connection_of(ctx, engagement_id)
    if view is None:
        raise NoLiveConnection
    return view


async def connection_of(ctx: AuthContext, engagement_id: UUID) -> ConnectionView | None:
    """AC-4: the entity's live connection, or None."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "connection.read_log", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        connection = await live_connection_for(session, ref.client_entity_id)
        if connection is None:
            return None
        pulled = await last_success(session, connection.id)
    return ConnectionView(
        connection.id,
        connection.provider,
        connection.status,
        tuple(connection.scopes),
        connection.created_by,
        connection.created_at,
        connection.expires_at,
        connection.last_checked_at,
        connection.last_check_ok,
        pulled,
    )


async def access_log(ctx: AuthContext, engagement_id: UUID, page: int) -> list[LogEntry]:
    """AC-5: every pull for the engagement, newest first, 50 a page."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "connection.read_log", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        runs = await list_access_log(
            session, ctx, engagement_id, limit=LOG_PAGE, offset=page * LOG_PAGE
        )
    return [_entry(run) for run in runs]


def _entry(run: SyncRun) -> LogEntry:
    return LogEntry(
        run.id,
        run.dataset,
        run.period_start.isoformat(),
        run.period_end.isoformat(),
        run.status,
        run.started_at,
        run.finished_at,
        run.started_by,
    )


# A-02-T16: the entity-scoped flow (`entity.py`) shares the legacy flow's state, redirect and
# provider rules; these are its names for them.
hash_state = _hash
redirect_uri = _redirect_uri
unsaved_connection = _unsaved
oauth_providers = _available
code_ref = _code_ref
