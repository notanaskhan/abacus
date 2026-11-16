"""Record `LedgerSyncWorkflow`'s replay history (C-01-T17; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_ledger_sync <output-directory>

`ledger-sync-v1-ticks.json`: one run of the firm's loop with both activities stubbed: a Sync now
signalled at start, then 24 hourly ticks (one due connection each, a minute's wait) and the
continue-as-new that ends the run. A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.connections.ledger_sync_types import (
    PLAN_TICK,
    SYNC_ENTITY,
    SYNC_NOW,
    LedgerSyncInput,
    PlanTickInput,
    PlanTickResult,
    SyncEntityInput,
    SyncEntityResult,
    SyncNowSignal,
)
from abacus.modules.connections.ledger_sync_workflow import LedgerSyncWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "ledger-sync-v1-ticks.json"
TENANT = "00000000-0000-4000-8000-0000000000b1"
CONNECTION = "00000000-0000-4000-8000-0000000017c1"


@activity.defn(name=PLAN_TICK)
async def _plan(given: PlanTickInput) -> PlanTickResult:
    return PlanTickResult(1, [CONNECTION])


@activity.defn(name=SYNC_ENTITY)
async def _sync(given: SyncEntityInput) -> SyncEntityResult:
    return SyncEntityResult("unchanged" if given.trigger == "schedule" else "synced", 0, 1)


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[LedgerSyncWorkflow], activities=[_plan, _sync]
    ):
        handle = await client.start_workflow(
            LedgerSyncWorkflow.run,
            LedgerSyncInput(TENANT),
            id=f"ledger_sync:{TENANT}",
            task_queue=_TASK_QUEUE,
            start_signal=SYNC_NOW,
            start_signal_args=[
                SyncNowSignal(CONNECTION, "00000000-0000-4000-8000-0000000017d1", "recorder")
            ],
        )
        first_run = handle.result_run_id
        try:
            await handle.result(follow_runs=False)
        except Exception:  # noqa: BLE001 -- the run ends by continuing as new
            pass
        run = client.get_workflow_handle(handle.id, run_id=first_run)
        scrubbed = await decoded_and_scrubbed(await run.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")
        await client.get_workflow_handle(handle.id).terminate("recorded")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the ledger sync history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
