"""Record the replay histories of S52's two other workflows (Q-03-T195; ADR-090; S52 end pass):
Q-05-T15's `DestructionExecuteWorkflow` and T-08-T14's `StandardsRunWorkflow`. See `histories.py`
for the fixture rules.

Run: python -m abacus_tools.workflows.record_s52_runs <output-directory>

The real workflows against throwaway containers with their activities stubbed (replay never runs
activities): `destruction-execute-v1-certified.json` (one resumable activity) and
`standards-run-v1-two-items.json` (list, two items in parallel, finish). Synthetic identifiers
only; refuses to overwrite.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import DESTRUCTION_EXECUTE, DestructionExecuteWorkflow
from abacus.modules.tax.api import (
    STANDARDS_FINISH_ACTIVITY,
    STANDARDS_ITEM_ACTIVITY,
    StandardsRunWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-0000000000e1"
_BATCH = "00000000-0000-4000-8000-0000000000e2"
_APPROVER = "00000000-0000-4000-8000-0000000000e3"
_RUN = "00000000-0000-4000-8000-0000000000e4"
_ITEMS = ["00000000-0000-4000-8000-0000000000e5", "00000000-0000-4000-8000-0000000000e6"]
DESTRUCTION = "destruction-execute-v1-certified.json"
STANDARDS = "standards-run-v1-two-items.json"


@activity.defn(name=DESTRUCTION_EXECUTE)
async def _execute(given: list[str]) -> str:
    return "certified"


@activity.defn(name="standards_run_items")
async def _items(given: list[str]) -> list[str]:
    return list(_ITEMS)


@activity.defn(name=STANDARDS_ITEM_ACTIVITY)
async def _item(given: list[str]) -> str:
    return "done"


@activity.defn(name=STANDARDS_FINISH_ACTIVITY)
async def _finish(given: list[str]) -> str:
    return "completed"


async def _record(out: Path, stack: Stack) -> None:
    client: Client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[DestructionExecuteWorkflow, StandardsRunWorkflow],
        activities=[_execute, _items, _item, _finish],
    ):
        for workflow_run, given, wid, name in (
            (
                DestructionExecuteWorkflow.run,
                [_TENANT, _BATCH, _APPROVER],
                f"destruction:{_TENANT}:{_BATCH}",
                DESTRUCTION,
            ),
            (
                StandardsRunWorkflow.run,
                [_TENANT, _RUN],
                f"standards_run:{_TENANT}:{_RUN}",
                STANDARDS,
            ),
        ):
            handle = await client.start_workflow(
                workflow_run, given, id=wid, task_queue=_TASK_QUEUE
            )
            await handle.result()
            scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
            path = out / name
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, [DESTRUCTION, STANDARDS]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
