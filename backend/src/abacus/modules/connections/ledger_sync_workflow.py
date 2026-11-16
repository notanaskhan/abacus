"""`LedgerSyncWorkflow` (C-01-T17; C-01 §4.5; ADR-090; red): one per firm, `ledger_sync:<tenant>`.

Orchestration only. Each loop asks `ledger_sync.plan_tick` which connections are due and how long
to sleep (business hours, schedules and the firm's clock are read in that activity, so replay stays
deterministic), runs `ledger_sync.sync_entity` for each, one at a time, then waits for the next
tick or a `sync_now` signal. A Sync now runs its entity at once (`on_demand`), ahead of scheduled
work. Failure codes cross as data in the result, never as provider text; an activity that fails
outright is logged and the next tick tries again, so one bad entity never stops the firm's sync.
It continues as new every 24 ticks, carrying any pending Sync now requests.

Started by `kernel.dispatch.signal_with_start` (Sync now) and by the closes module when a close
for an entity with a live ledger connection is generated. Changes are guarded with
`workflow.patched(...)`; histories in `tests/workflows/histories/ledger-sync-v1-*.json` replay.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.connections.ledger_sync_types import (
        PLAN_TICK,
        SYNC_ENTITY,
        SYNC_NOW,
        TICKS_PER_RUN,
        LedgerSyncInput,
        PlanTickInput,
        PlanTickResult,
        SyncEntityInput,
        SyncEntityResult,
        SyncNowSignal,
    )

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=5),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=4,
)
_PLAN_TIMEOUT = timedelta(seconds=60)
_SYNC_TIMEOUT = timedelta(minutes=15)


@workflow.defn(name="LedgerSyncWorkflow")
class LedgerSyncWorkflow:
    def __init__(self) -> None:
        self._now: list[SyncNowSignal] = []

    @workflow.signal(name=SYNC_NOW)
    def sync_now(self, request: SyncNowSignal) -> None:
        if all(r.connection_id != request.connection_id for r in self._now):
            self._now.append(request)

    async def _sync(self, given: LedgerSyncInput, item: SyncEntityInput) -> None:
        del given
        try:
            result = await workflow.execute_activity(
                SYNC_ENTITY,
                item,
                result_type=SyncEntityResult,
                start_to_close_timeout=_SYNC_TIMEOUT,
                retry_policy=_RETRY,
            )
        except ActivityError:
            workflow.logger.warning("ledger_sync.entity_failed")
            return
        if result.failure_code is not None:
            workflow.logger.info("ledger_sync.entity_outcome", extra={"state": result.state})

    async def _drain_now(self, given: LedgerSyncInput) -> None:
        while self._now:
            request = self._now.pop(0)
            await self._sync(
                given,
                SyncEntityInput(
                    given.tenant_id,
                    request.connection_id,
                    "on_demand",
                    request.started_by,
                    request.request_id,
                ),
            )

    @workflow.run
    async def run(self, given: LedgerSyncInput) -> str:
        self._now.extend(given.pending)
        ticks = 0
        while True:
            await self._drain_now(given)
            plan = await workflow.execute_activity(
                PLAN_TICK,
                PlanTickInput(given.tenant_id),
                result_type=PlanTickResult,
                start_to_close_timeout=_PLAN_TIMEOUT,
                retry_policy=_RETRY,
            )
            for connection_id in plan.connection_ids:
                await self._drain_now(given)  # a Sync now never waits behind the hour's queue
                await self._sync(
                    given,
                    SyncEntityInput(
                        given.tenant_id, connection_id, "schedule", "connections:ledger_sync"
                    ),
                )
            ticks += 1
            if ticks >= TICKS_PER_RUN or workflow.info().is_continue_as_new_suggested():
                workflow.continue_as_new(LedgerSyncInput(given.tenant_id, list(self._now)))
            try:
                await workflow.wait_condition(
                    lambda: bool(self._now),
                    timeout=timedelta(seconds=max(plan.wait_seconds, 1)),
                )
            except TimeoutError:
                pass
