"""Starting retrievals, resuming their system context, and the connector registry
(TASK-010 design §1, §3, §7; revision 1). PROTECTED."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.connector import Connector, ConnectorError, Period
from abacus.modules.connections.fake import FakeConnector
from abacus.modules.connections.models import Connection, SyncRun
from abacus.modules.connections.repository import (
    active_connection_for,
    active_run,
    get_run,
    insert_run,
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


def _fake(connection: Connection) -> Connector:
    directory = settings().fake_connector_dir
    if directory is None:  # refused outside local/test by settings validation
        raise ConnectorError("connector_unavailable")
    return FakeConnector(connection.id, Path(directory))


CONNECTORS: dict[str, Callable[[Connection], Connector]] = {"fake": _fake}


def connector_for(connection: Connection) -> Connector:
    factory = CONNECTORS.get(connection.provider)
    if factory is None:
        raise ConnectorError("unknown_provider")
    return factory(connection)


async def start_retrieval(
    ctx: AuthContext, *, engagement_id: UUID, request_item_id: UUID, period: Period
) -> StartedRun:
    """Authorise the human (`evidence.upload`), check the engagement, item and connection, and
    record the run (`sync_run.started`). Idempotent: while a run for this item and period is
    running or has succeeded, triggering again returns that run (`created=False`, §12)."""
    async with uow(ctx.tenant) as tx:
        engagement = await lock_ref(tx, engagement_id)
        # An archived engagement is read-only: authorise denies the upload (403, archived_write).
        await authorise(ctx, "evidence.upload", engagement.resource())
        item = await item_ref(tx, request_item_id)
        if item.engagement_id != engagement_id:
            raise NotFound("request_item")
        if item.status not in ("open", "received"):
            raise ItemNotFulfillable(item.status)
        existing = await active_run(tx.session, request_item_id, period.start, period.end)
        if existing is not None:
            tx.record(
                "sync_run.requested_again",
                target=Target("sync_run", existing.id),
                after=Ref(user_id=ctx.user_id),
            )
            return StartedRun(existing.id, created=False)
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


def _view(run: SyncRun) -> RetrievalView:
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
