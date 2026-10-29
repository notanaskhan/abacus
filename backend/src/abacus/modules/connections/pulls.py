"""On-demand ledger pulls (A-02-T30; A-02 AC-46; DEC-829).

`POST /v1/engagements/{id}/connection/pulls` (`ledger.pull`, behind `connections.live_ledger`):
a person asks the engagement's live ledger for a trial balance at a period end, as the current
year (`standard`) or the prior year (`prior`). One `sync_runs` row, `trigger = 'on_demand'`, no
request item, the label it lands as; its RetrievalWorkflow pulls, normalises, validates and
snapshots, then ends at the snapshot (the `on-demand-pulls` patch): no evidence version and no
request item, so AUD-06 adopts the snapshot. While a pull for the same engagement, period and
label is running it is answered again. Refused: no live ledger connection (409
`connector_not_available`), a connection the client must sign in to again (409
`connection_needs_reauth`). The daily retrieval cap applies as to every run (SPEC-007 AC-4).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.config import settings
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.connections.entity import (
    REAUTH_REASONS,
    ConnectionNeedsReauth,
    ConnectorNotAvailable,
)
from abacus.modules.connections.models import SyncRun
from abacus.modules.connections.repository import (
    active_connection_for,
    insert_retry_run,
    runs_since,
)
from abacus.modules.connections.retrievals import ensure_workflow
from abacus.modules.connections.service import ActionCapReached, today_start
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import AuthContext, authorise

ACTION: Final = "ledger.pull"
LABELS: Final = frozenset({"standard", "prior"})


@dataclass(frozen=True)
class Pulled:
    run_id: UUID
    status: str
    created: bool


def period_of(period_end: date) -> tuple[date, date]:
    """The twelve months ending on `period_end`."""
    start = date(period_end.year - 1, period_end.month, period_end.day) + timedelta(days=1)
    return start, period_end


async def check_pull(ctx: AuthContext, engagement_id: UUID) -> None:
    """The route's check before its `Idempotency-Key` lookup, so a replay is authorised too."""
    engagement = await get_ref(ctx, engagement_id)
    await authorise(ctx, ACTION, engagement.resource())


async def pull(ctx: AuthContext, engagement_id: UUID, period_end: date, label: str) -> Pulled:
    """Record the on-demand run and make sure its workflow runs."""
    if label not in LABELS:
        raise ValueError(f"a pull lands as {sorted(LABELS)}, not {label!r}")
    start, end = period_of(period_end)
    cap = settings().retrieval_daily_cap
    capped = False
    run: SyncRun | None = None
    async with uow(ctx.tenant) as tx:
        engagement = await lock_ref(tx, engagement_id)
        await authorise(ctx, ACTION, engagement.resource())
        connection = await active_connection_for(tx.session, engagement.client_entity_id)
        if connection is None:
            raise ConnectorNotAvailable(str(engagement.client_entity_id))
        if connection.status_reason_code in REAUTH_REASONS:
            raise ConnectionNeedsReauth(str(connection.id))
        running = await tx.session.scalar(
            select(SyncRun).where(
                SyncRun.engagement_id == engagement_id,
                SyncRun.trigger == "on_demand",
                SyncRun.status == "running",
                SyncRun.period_end == end,
                SyncRun.label == label,
            )
        )
        if running is not None:
            tx.record(
                "sync_run.requested_again",
                target=Target("sync_run", running.id),
                after=Ref(user_id=ctx.user_id),
            )
            return Pulled(running.id, running.status, created=False)
        if await runs_since(tx.session, engagement_id, today_start()) >= cap:
            capped = True
            tx.record(
                "action_cap.refused",
                target=Target("engagement", engagement_id),
                after=Ref(user_id=ctx.user_id),
            )
        else:
            run = await insert_retry_run(
                tx.session,
                tenant_id=ctx.tenant_id,
                client_entity_id=engagement.client_entity_id,
                connection_id=connection.id,
                engagement_id=engagement_id,
                request_item_id=None,
                trigger="on_demand",
                label=label,
                dataset="trial_balance",
                period_start=start,
                period_end=end,
                started_by=str(ctx.user_id),
            )
            if run is None:
                raise ConnectorNotAvailable(str(connection.id))
            tx.record(
                "ledger.pull_requested",
                target=Target("sync_run", run.id),
                after=Ref(engagement_id=engagement_id, period_end=int(end.strftime("%Y%m%d"))),
            )
            tx.record(
                "sync_run.started",
                target=Target("sync_run", run.id),
                after=Ref(user_id=ctx.user_id),
            )
    if capped or run is None:
        raise ActionCapReached("retrieval")
    await ensure_workflow(ctx, run.id, created=True)
    return Pulled(run.id, "running", created=True)
