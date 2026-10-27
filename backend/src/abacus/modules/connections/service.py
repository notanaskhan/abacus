"""Starting retrievals, resuming their system context, and the connector registry
(TASK-010 design §1, §3, §7; revision 1). PROTECTED."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from abacus.kernel.clock import system_now
from abacus.kernel.config import settings
from abacus.kernel.crypto import seal
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.egress import EgressClient
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.connector import Connector, ConnectorError, Credentials, Period
from abacus.modules.connections.connectors.import_file import ImportConnector
from abacus.modules.connections.connectors.quickbooks_online import PROVIDER as QBO_PROVIDER
from abacus.modules.connections.connectors.quickbooks_online import (
    QboApp,
    QuickBooksOnlineConnector,
)
from abacus.modules.connections.fake import FakeConnector
from abacus.modules.connections.models import Connection, SyncRun
from abacus.modules.connections.repository import (
    active_connection_for,
    active_run,
    destroy_secret,
    get_gl_import,
    get_run,
    insert_run,
    insert_secret,
    runs_since,
)
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import (
    AuthContext,
    SystemContext,
    authorise,
    system_context_for_run,
)
from abacus.modules.requests.api import ItemNotFulfillable, item_ref


class NoConnection(DomainConflict):
    """The engagement's client entity has no active connection."""

    code = "no_connection"


class ActionCapReached(DomainConflict):
    """The engagement reached its daily cap for this action (SPEC-007 AC-4)."""

    code = "action_cap"


def today_start() -> datetime:
    return system_now().replace(hour=0, minute=0, second=0, microsecond=0)


class RunNotRunning(Exception):
    """The run has finished: there is nothing left for the platform to do on it."""

    def __init__(self, status: str, failure_code: str | None) -> None:
        super().__init__(status)
        self.status = status
        self.failure_code = failure_code


@dataclass(frozen=True)
class StartedRun:
    run_id: UUID
    created: bool  # False: an existing running or succeeded run for this item and period


@dataclass(frozen=True)
class RetrievalView:
    sync_run_id: UUID
    request_item_id: UUID
    status: str
    failure_code: str | None
    evidence_version_id: UUID | None
    started_at: datetime
    finished_at: datetime | None
    # Waiting for a work slot (SPEC-003 AC-13): `status` stays `running`; the API says queued.
    queued_reason: str | None = None
    estimated_start_at: datetime | None = None

    @property
    def reported_status(self) -> str:
        """What callers are told: a run waiting for a work slot is `queued`, never `running`
        (SPEC-003 AC-13). `status` stays the stored one, for the service's own checks."""
        return "queued" if self.status == "running" and self.queued_reason else self.status


def _fake(connection: Connection, credentials: Credentials | None) -> Connector:
    directory = settings().fake_connector_dir
    if directory is None:  # refused outside local/test by settings validation
        raise ConnectorError("connector_unavailable")
    return FakeConnector(connection.id, Path(directory), credentials)


def _import(connection: Connection, credentials: Credentials | None) -> Connector:
    """SPEC-028 (TASK-052): the entity's uploaded exports (ADR-107)."""
    return ImportConnector(connection.tenant_id, connection.client_entity_id)


_egress: EgressClient | None = None


def _egress_client() -> EgressClient:
    """One shared outbound client for live connectors (the kernel's allowlisted reads)."""
    global _egress
    if _egress is None:
        _egress = EgressClient()
    return _egress


def qbo_app() -> QboApp | None:
    """The QuickBooks Online app registration, if this environment has one (A-02-T26)."""
    config = settings()
    if config.qbo_client_id is None or config.qbo_client_secret is None:
        return None
    return QboApp(
        config.qbo_client_id, config.qbo_client_secret.get_secret_value(), config.qbo_environment
    )


def _resealer(connection: Connection) -> Callable[[Credentials], Awaitable[None]]:
    """A rotated refresh token replaces the sealed credentials, in one unit of work (ADR-035)."""

    async def reseal(credentials: Credentials) -> None:
        system = TenantContext(connection.tenant_id, "system", "connections:refresh")
        sealed = await seal(connection.tenant_id, credentials, str(connection.id))
        async with uow(system) as tx:
            await destroy_secret(tx.session, connection.id)
            await insert_secret(
                tx.session,
                tenant_id=connection.tenant_id,
                connection_id=connection.id,
                sealed=sealed,
            )
            tx.record("connection.credentials_rotated", target=Target("connection", connection.id))

    return reseal


def _quickbooks_online(connection: Connection, credentials: Credentials | None) -> Connector:
    """A-02-T26 (DEC-70, DEC-709): the first live ledger read."""
    app = qbo_app()
    if app is None:
        raise ConnectorError("connector_unavailable")
    return QuickBooksOnlineConnector(
        app, _egress_client(), credentials, on_rotate=_resealer(connection)
    )


CONNECTORS: dict[str, Callable[[Connection, Credentials | None], Connector]] = {
    "fake": _fake,
    "import": _import,
    QBO_PROVIDER: _quickbooks_online,
}
# Providers whose connector reaches no host (A-02-T16 review M3): the demo ledger reads local
# files, an import reads uploads. Every other provider must be a read connector the
# write-capability registry declares, with its hosts; the API and the worker refuse to start
# otherwise (`integrations.assert_egress_declared`).
NETWORKLESS_PROVIDERS: frozenset[str] = frozenset({"fake", "import"})
# A-02-T27: tooling's fakes (`abacus_tools.fakes.ledgers`) register under this prefix, only in
# synthetic environments, and reach no host either.
FAKE_PREFIX = "fake_"


def is_networkless(provider: str) -> bool:
    return provider in NETWORKLESS_PROVIDERS or provider.startswith(FAKE_PREFIX)


def connector_for(connection: Connection, credentials: Credentials | None = None) -> Connector:
    """The provider's connector, given the connection's opened credentials (if it has any)."""
    factory = CONNECTORS.get(connection.provider)
    if factory is None:
        raise ConnectorError("unknown_provider")
    return factory(connection, credentials)


async def start_retrieval(
    ctx: AuthContext, *, engagement_id: UUID, request_item_id: UUID, period: Period
) -> StartedRun:
    """Authorise the human (`evidence.upload`), check the engagement, item and connection, and
    record the run (`sync_run.started`). At the engagement's daily cap the refusal is audited
    and `ActionCapReached` raised (SPEC-007 AC-4). Idempotent: while a run for this item and
    period is running or has succeeded, triggering again returns that run (`created=False`,
    §12)."""
    cap = settings().retrieval_daily_cap
    run: SyncRun | None = None
    async with uow(ctx.tenant) as tx:
        engagement = await lock_ref(tx, engagement_id)
        # An archived engagement is read-only: authorise denies the upload (403, archived_write).
        await authorise(ctx, "evidence.upload", engagement.resource())
        item = await item_ref(tx, request_item_id)
        if item.engagement_id != engagement_id:
            raise NotFound("request_item")
        if item.status not in ("draft", "requested", "uploaded"):
            raise ItemNotFulfillable(item.status)
        existing = await active_run(tx.session, request_item_id, period.start, period.end)
        if existing is not None:
            tx.record(
                "sync_run.requested_again",
                target=Target("sync_run", existing.id),
                after=Ref(user_id=ctx.user_id),
            )
            return StartedRun(existing.id, created=False)
        capped = await runs_since(tx.session, engagement_id, today_start()) >= cap
        if capped:  # recorded (committed), then refused below: nothing is started
            tx.record(
                "action_cap.refused",
                target=Target("engagement", engagement_id),
                after=Ref(user_id=ctx.user_id, request_item_id=request_item_id),
            )
        else:
            connection = await active_connection_for(tx.session, engagement.client_entity_id)
            if connection is None:
                raise NoConnection("no active connection for the engagement's client entity")
            run = await insert_run(
                tx.session,
                tenant_id=ctx.tenant_id,
                client_entity_id=engagement.client_entity_id,
                connection_id=connection.id,
                engagement_id=engagement_id,
                request_item_id=request_item_id,
                period_start=period.start,
                period_end=period.end,
                started_by=str(ctx.user_id),
            )
            if run is None:  # a concurrent trigger won the unique index
                raced = await active_run(tx.session, request_item_id, period.start, period.end)
                if raced is None:
                    raise NotFound("sync_run")
                tx.record(
                    "sync_run.requested_again",
                    target=Target("sync_run", raced.id),
                    after=Ref(user_id=ctx.user_id),
                )
                return StartedRun(raced.id, created=False)
            tx.record(
                "sync_run.started",
                target=Target("sync_run", run.id),
                after=Ref(user_id=ctx.user_id, request_item_id=request_item_id),
            )
    if capped or run is None:
        raise ActionCapReached("retrieval")
    return StartedRun(run.id, created=True)


async def load_system_context(tenant_id: UUID, run_id: UUID) -> SystemContext:
    """The platform's context for a run, proven by the run row (never by the caller's input):
    the run must exist in the tenant (row-level security) and still be running. Engagement and
    the person on whose behalf it runs come from the row. Workers call this first in every
    activity (TASK-010b)."""
    reader = TenantContext(tenant_id, "system", f"run:{run_id}")
    async with tenant_session(reader) as session:
        run = await get_run(session, run_id)
    if run is None:
        raise NotFound("sync_run")
    if run.status != "running":
        raise RunNotRunning(run.status, run.failure_code)
    return system_context_for_run(
        tenant_id=tenant_id,
        run_id=run.id,
        engagement_id=run.engagement_id,
        on_behalf_of=UUID(run.started_by),
    )


async def load_gl_import_context(tenant_id: UUID, import_id: UUID) -> SystemContext:
    """SPEC-034 (TASK-070 D1): the platform's context for rendering and fulfilling a reconciled
    general ledger import, proven by its `gl_imports` row (never by the caller's input), acting on
    behalf of whoever uploaded it, as a retrieval acts for the person who started it."""
    reader = TenantContext(tenant_id, "system", f"gl_import:{import_id}")
    async with tenant_session(reader) as session:
        row = await get_gl_import(session, import_id)
    if row is None:
        raise NotFound("gl_import")
    if row.status != "reconciled" or row.gl_snapshot_id is None:
        raise RunNotRunning(row.status, row.failure_code)
    return system_context_for_run(
        tenant_id=tenant_id,
        run_id=row.id,
        engagement_id=row.engagement_id,
        on_behalf_of=row.uploaded_by,
    )


def _view(run: SyncRun) -> RetrievalView:
    # A run no request item asked for (0195: on demand, scheduled, an export) is not a
    # retrieval; A-02-T30 gives those runs their own view.
    if run.request_item_id is None:
        raise NotFound("sync_run")
    return RetrievalView(
        run.id,
        run.request_item_id,
        run.status,
        run.failure_code,
        run.evidence_version_id,
        run.started_at,
        run.finished_at,
        run.queued_reason,
        run.estimated_start_at,
    )


async def run_view(tenant: TenantContext, run_id: UUID) -> RetrievalView:
    async with tenant_session(tenant) as session:
        run = await get_run(session, run_id)
    if run is None:
        raise NotFound("sync_run")
    return _view(run)


async def retrieval_status(
    ctx: AuthContext, *, engagement_id: UUID, run_id: UUID
) -> RetrievalView:
    """A retrieval's state for anyone who may read the engagement's request items (Q4)."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, "request_item.read", engagement.resource())
    async with tenant_session(ctx.tenant) as session:
        run = await get_run(session, run_id)
    if run is None or run.engagement_id != engagement_id:
        raise NotFound("sync_run")
    return _view(run)


async def succeeded_version(tenant_id: UUID, run_id: UUID) -> UUID | None:
    """The evidence version a succeeded run produced (for an activity retried after success)."""
    reader = TenantContext(tenant_id, "system", f"run:{run_id}")
    async with tenant_session(reader) as session:
        run = await get_run(session, run_id)
    return run.evidence_version_id if run is not None and run.status == "succeeded" else None
