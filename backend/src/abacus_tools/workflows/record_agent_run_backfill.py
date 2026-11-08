"""Record `AgentRunBackfill`'s replay histories (P-10-T14; ADR-090). See `histories.py` for the
fixture rules.

Run: python -m abacus_tools.workflows.record_agent_run_backfill <output-directory>

Records the real workflow against throwaway containers with its activity replaced by a stub:
- `agent-run-backfill-v1-completed.json`: two batches (500 rows, then 120 and nothing left);
- `agent-run-backfill-v1-resumed.json`: a restart after an interruption, carrying 1,000 done,
  whose one batch finds 40 rows left.
A history already on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import BACKFILL_ID_PREFIX, AgentRunBackfillWorkflow, BackfillInput
from abacus.modules.agents.run_backfill_workflow import BackfillBatch
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-0000000000b1"  # Brightwater Hale's synthetic id shape
COMPLETED = "agent-run-backfill-v1-completed.json"
RESUMED = "agent-run-backfill-v1-resumed.json"
_batches: list[BackfillBatch] = []


@activity.defn(name="agents.backfill_run_batch")
async def _batch(tenant_id: str, limit: int) -> BackfillBatch:
    return _batches.pop(0)


async def _run(client: Client, params: BackfillInput, suffix: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        AgentRunBackfillWorkflow.run,
        params,
        id=f"{BACKFILL_ID_PREFIX}{_TENANT}-{suffix}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[AgentRunBackfillWorkflow],
        activities=[_batch],
    ):
        runs = (
            (
                COMPLETED,
                BackfillInput(_TENANT, 500, 0.1),
                [BackfillBatch(500, True), BackfillBatch(120, False)],
            ),
            (RESUMED, BackfillInput(_TENANT, 500, 0.1, 1000), [BackfillBatch(40, False)]),
        )
        for name, params, batches in runs:
            if (out / name).exists():
                continue
            _batches[:] = batches
            history = await _run(client, params, name.split("-v1-")[1].removesuffix(".json"))
            scrubbed = await decoded_and_scrubbed(history, payload_codec())
            path = out / name
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if all((out / name).exists() for name in (COMPLETED, RESUMED)):
        print("every agent-run-backfill history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
