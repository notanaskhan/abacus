"""Record the replay history of C-02-T28's `PackageAssemblyWorkflow` (Q-03-T195; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_s52_package <output-directory>

The real workflow against throwaway containers with its activity stubbed (replay never runs
activities): `package-assembly-v1-finished.json`. Synthetic identifiers only; refuses to overwrite.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.closes.api import PACKAGE_FINISH as FINISH
from abacus.modules.closes.api import PackageAssemblyWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_INPUT = [
    "00000000-0000-4000-8000-0000000000f1",
    "00000000-0000-4000-8000-0000000000f3",
    "00000000-0000-4000-8000-0000000000f4",
    "00000000-0000-4000-8000-0000000000f5",
    "2",
]
FILE = "package-assembly-v1-finished.json"


@activity.defn(name=FINISH)
async def _finish(given: list[str]) -> str:
    return "succeeded"


async def _record(out: Path, stack: Stack) -> None:
    client: Client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[PackageAssemblyWorkflow], activities=[_finish]
    ):
        handle = await client.start_workflow(
            PackageAssemblyWorkflow.run,
            _INPUT,
            id=f"close_package:{_INPUT[0]}:{_INPUT[1]}:2",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        path = out / FILE
        path.write_text(scrubbed.to_json())
        print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, [FILE]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
