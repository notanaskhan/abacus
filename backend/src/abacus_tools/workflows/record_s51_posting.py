"""Record the replay history of C-02-T18's `PostingBatchWorkflow` (Q-03-T195; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_s51_posting <output-directory>

Records the real workflow against throwaway containers with its activity replaced by a stub
(replay never runs activities): `posting-batch-v1-posted.json`, the grant's 10-second hold on a
durable timer, then one run of the batch. Synthetic identifiers only. Refuses to overwrite an
existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.adjustments.api import POSTING_RUN, PostingBatchWorkflow, PostingInput
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_INPUT = PostingInput(
    "00000000-0000-4000-8000-0000000000f1",
    "00000000-0000-4000-8000-0000000000f2",
)
POSTING = "posting-batch-v1-posted.json"
POSTING_ID = f"posting:{_INPUT.tenant_id}:{_INPUT.batch_id}"


@activity.defn(name=POSTING_RUN)
async def _run(given: PostingInput) -> str:
    return "posted"


async def _record(out: Path, stack: Stack) -> None:
    client: Client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[PostingBatchWorkflow], activities=[_run]
    ):
        handle = await client.start_workflow(
            PostingBatchWorkflow.run, _INPUT, id=POSTING_ID, task_queue=_TASK_QUEUE
        )
        await handle.result()
        history = await handle.fetch_history()
        scrubbed = await decoded_and_scrubbed(history, payload_codec())
        path = out / POSTING
        path.write_text(scrubbed.to_json())
        print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, [POSTING]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
