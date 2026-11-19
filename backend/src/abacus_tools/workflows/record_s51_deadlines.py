"""Record the replay history of T-08-T10's `FilingDeadlineRecomputeWorkflow` (Q-03-T195;
ADR-090). See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_s51_deadlines <output-directory>

Records the real workflow against throwaway containers with its activity replaced by a stub
(replay never runs activities): `filing-deadline-recompute-v1-recomputed.json`, one run of
the sweep. Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.practice.api import FilingDeadlineRecomputeWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
SWEPT = "filing-deadline-recompute-v1-recomputed.json"
SWEPT_ID = "filing_deadlines_recompute:platform"


@activity.defn(name="practice.filing_deadlines_recompute")
async def _sweep() -> int:
    return 1


async def _record(out: Path, stack: Stack) -> None:
    client: Client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[FilingDeadlineRecomputeWorkflow],
        activities=[_sweep],
    ):
        handle = await client.start_workflow(
            FilingDeadlineRecomputeWorkflow.run, id=SWEPT_ID, task_queue=_TASK_QUEUE
        )
        await handle.result()
        history = await handle.fetch_history()
        scrubbed = await decoded_and_scrubbed(history, payload_codec())
        path = out / SWEPT
        path.write_text(scrubbed.to_json())
        print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, [SWEPT]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
