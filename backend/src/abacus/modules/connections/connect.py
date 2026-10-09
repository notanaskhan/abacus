"""The client connection flow, health, access log and revoke (SPEC-020; TASK-036). PROTECTED.

A client admin starts a flow (`connection.create`, fresh MFA): a random state is kept only as
its hash, bound to them, the engagement and its client entity, for ten minutes. The provider
sends the browser back to the SPA, which completes the flow with the same person's token (D1),
so no API route is unauthenticated. Credentials are sealed with the tenant's key (ADR-035) and
deleted on revoke. Provider text is never kept or shown: only codes (ADR-052).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Final
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.crypto import open_sealed, seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.connections.connector import ConnectorError
from abacus.modules.connections.events import ConnectionCreated, ConnectionRevoked
from abacus.modules.connections.models import Connection, SyncRun
from abacus.modules.connections.repository import (
    destroy_secret,
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
)
from abacus.modules.connections.service import connector_for
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, authorise

STATE_TTL: Final = timedelta(minutes=10)
LOG_PAGE: Final = 50
CALLBACK_PATH: Final = "/client/connect/callback"
# Providers by environment (SPEC-020 Q1): the demo ledger only where the fake connector may run.
PROVIDER_NAMES: Final = {"fake": "Demo ledger"}


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
    return f"{settings().app_base_url}{CALLBACK_PATH}"


def _hash(state: str) -> str:
    return hashlib.sha256(state.encode()).hexdigest()


def _available() -> tuple[str, ...]:
    return ("fake",) if settings().fake_connector_dir is not None else ()


async def providers(ctx: AuthContext, engagement_id: UUID) -> list[ProviderView]:
    """What this client may connect, here (a client admin's view; `connection.create`'s roles)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "connection.read_log", ref.resource())
    return [ProviderView(p, PROVIDER_NAMES[p], ("trial_balance",)) for p in _available()]


async def start(ctx: AuthContext, engagement_id: UUID, provider: str) -> Started:
    """AC-2, AC-3: authorise (fresh MFA), keep the hashed state, return the provider's URL."""
    if provider not in _available():
        raise UnknownProvider
    state = secrets.token_urlsafe(32)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "connection.create", ref.resource())
        state_id = await insert_state(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            client_entity_id=ref.client_entity_id,
            user_id=ctx.user_id,
            provider=provider,
            state_hash=_hash(state),
            expires_at=datetime.now(UTC) + STATE_TTL,
        )
        tx.record(
            "connection.started",
            target=Target("connection_state", state_id),
            after=Ref(engagement_id=engagement_id),
        )
    connector = connector_for(_unsaved(provider, ref.client_entity_id, ctx))
    return Started(await connector.authorise_url(state, _redirect_uri()))


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
    engagement, for the SPA to return to."""
    found = await _spend(ctx, state)
    if found is None:
        raise InvalidState
    engagement_id, client_entity_id, provider = found
    connector = connector_for(_unsaved(provider, client_entity_id, ctx))
    try:
        credentials = await connector.exchange_code(code, _redirect_uri())
    except ConnectorError as exc:
        async with uow(ctx.tenant) as tx:
            tx.record(
                "connection.failed",
                target=Target("engagement", engagement_id),
                after=Ref(code=_code_ref(exc.code)),
            )
        raise ConnectionFailed from None
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "connection.create", ref.resource())
        old = await live_connection_for(tx.session, client_entity_id, lock=True)
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


async def _spend(ctx: AuthContext, state: str) -> tuple[UUID, UUID, str] | None:
    """Mark the state used (in its own unit of work, so it stays spent if anything later fails)
    and return what it was for, if it was this person's, unused and unexpired."""
    async with uow(ctx.tenant) as tx:
        row = await lock_state(tx.session, _hash(state))
        if row is None:
            tx.record("connection.state_refused", target=Target("user", ctx.user_id))
            return None
        valid = (
            row.used_at is None
            and row.user_id == ctx.user_id
            and row.expires_at > datetime.now(UTC)
        )
        if row.used_at is None:
            await spend_state(tx.session, row.id)
        tx.record(
            "connection.state_used" if valid else "connection.state_refused",
            target=Target("connection_state", row.id),
        )
        return (row.engagement_id, row.client_entity_id, row.provider) if valid else None


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
        revoked_at=datetime.now(UTC),
        revoked_by=str(ctx.user_id),
    )
    await destroy_secret(tx.session, connection.id)
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
            last_checked_at=datetime.now(UTC),
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
