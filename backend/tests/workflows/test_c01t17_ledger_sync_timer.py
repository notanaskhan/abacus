"""C-01-T17 (C-01 §4.5): `LedgerSyncWorkflow` on Temporal's time-skipping server, activities
stubbed. A Sync now runs its entity at once (`on_demand`), ahead of the hour's queue; each tick
runs the due connections as `schedule`; the run continues as new after 24 ticks."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

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
from abacus.modules.connections.ledger_sync_workflow import LedgerSyncWorkflow

QUEUE = "ledger-sync"
TENANT = "00000000-0000-4000-8000-0000000000b1"
DUE = "00000000-0000-4000-8000-0000000017c1"
NOW = "00000000-0000-4000-8000-0000000017c2"
calls: list[tuple[str, str]] = []
plans: list[int] = []


@activity.defn(name=PLAN_TICK)
async def _plan(given: PlanTickInput) -> PlanTickResult:
    plans.append(1)
    return PlanTickResult(3600, [DUE])


@activity.defn(name=SYNC_ENTITY)
async def _sync(given: SyncEntityInput) -> SyncEntityResult:
    calls.append((given.connection_id, given.trigger))
    return SyncEntityResult("synced", 1, 3)


@pytest.fixture
async def env() -> AsyncGenerator[WorkflowEnvironment]:
    calls.clear()
    plans.clear()
    environment = await WorkflowEnvironment.start_time_skipping()
    try:
        async with Worker(
            environment.client,
            task_queue=QUEUE,
            workflows=[LedgerSyncWorkflow],
            activities=[_plan, _sync],
        ):
            yield environment
    finally:
        await environment.shutdown()


@pytest.mark.asyncio
async def test_ac_sync_now_runs_first_and_on_demand(env: WorkflowEnvironment) -> None:
    handle = await env.client.start_workflow(
        LedgerSyncWorkflow.run,
        LedgerSyncInput(TENANT),
        id=f"ledger_sync:{TENANT}",
        task_queue=QUEUE,
        start_signal=SYNC_NOW,
        start_signal_args=[SyncNowSignal(NOW, "00000000-0000-4000-8000-0000000017d1", "priya")],
    )
    await env.sleep(10)
    assert calls[0] == (NOW, "on_demand")
    assert (DUE, "schedule") in calls
    await handle.terminate("done")


@pytest.mark.asyncio
async def test_ac_it_continues_as_new_after_24_ticks(env: WorkflowEnvironment) -> None:
    handle = await env.client.start_workflow(
        LedgerSyncWorkflow.run,
        LedgerSyncInput(TENANT),
        id=f"ledger_sync:{TENANT}:can",
        task_queue=QUEUE,
    )
    first = handle.result_run_id
    await env.sleep(3600 * (TICKS_PER_RUN + 1))
    described = await env.client.get_workflow_handle(handle.id, run_id=first).describe()
    assert described.status is not None and described.status.name == "CONTINUED_AS_NEW"
    assert len(plans) >= TICKS_PER_RUN
    await handle.terminate("done")
