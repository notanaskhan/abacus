"""Starting a retrieval, and the connector registry (TASK-010 design §1, §3, §7). PROTECTED."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from abacus.kernel.config import settings
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.connector import Connector, ConnectorError, Period
from abacus.modules.connections.fake import FakeConnector
from abacus.modules.connections.models import Connection
from abacus.modules.connections.repository import active_connection_for, insert_run
from abacus.modules.engagements.api import lock_ref
from abacus.modules.identity.api import AuthContext, SystemContext, authorise, system_context


class NoConnection(Exception):
    """The engagement's client entity has no active connection."""


@dataclass(frozen=True)
class StartedRun:
    run_id: UUID
    system: SystemContext


def connector_for(connection: Connection) -> Connector:
    if connection.provider == "fake":
        directory = settings().fake_connector_dir
        if directory is None:  # refused outside local/test by settings validation
            raise ConnectorError("connector_unavailable")
        return FakeConnector(connection.id, Path(directory))
    raise ConnectorError("unknown_provider")


async def start_retrieval(
    ctx: AuthContext, *, engagement_id: UUID, request_item_id: UUID, period: Period
) -> StartedRun:
    """Authorise the human (`evidence.upload` on the engagement), record the run, and hand back
    the system context the pipeline runs under."""
    async with uow(ctx.tenant) as tx:
        engagement = await lock_ref(tx, engagement_id)
        await authorise(ctx, "evidence.upload", engagement.resource())
        connection = await active_connection_for(tx.session, engagement.client_entity_id)
        if connection is None:
            raise NoConnection("no active connection for the engagement's client entity")
        run = await insert_run(
            tx.session,
            tenant_id=ctx.tenant_id,
            connection_id=connection.id,
            engagement_id=engagement_id,
            request_item_id=request_item_id,
            period_start=period.start,
            period_end=period.end,
            started_by=ctx.tenant.actor_id,
        )
        tx.record(
            "sync_run.started",
            target=Target("sync_run", run.id),
            after=Ref(user_id=ctx.user_id, request_item_id=request_item_id),
        )
    return StartedRun(run.id, system_context(ctx, run.id))
