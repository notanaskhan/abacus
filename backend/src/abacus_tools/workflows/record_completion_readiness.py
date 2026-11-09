"""Record `CompletionReadinessWorkflow`'s replay history (#4231; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_completion_readiness <output-directory>

`completion-readiness-v1-checked.json`: the 60-second wait, then the readiness run with the
activity stubbed. A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from abacus.kernel.temporal import data_converter, payload_codec
from abacus.modules.assurance.api import CompletionReadinessWorkflow, ReadinessInput
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "completion-readiness-v1-checked.json"


@activity.defn(name="assurance.completion_readiness")
async def _readiness(params: ReadinessInput) -> str | None:
    return "00000000-0000-4000-8000-000000004231"


async def _record(out: Path) -> None:
    # The time-skipping test server lets the 60-second wait pass at once.
    async with (
        await WorkflowEnvironment.start_time_skipping(data_converter=data_converter()) as env,
        Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[CompletionReadinessWorkflow],
            activities=[_readiness],
        ),
    ):
        handle = await env.client.start_workflow(
            CompletionReadinessWorkflow.run,
            ReadinessInput(
                "00000000-0000-4000-8000-0000000000b1", "00000000-0000-4000-8000-0000000004a1"
            ),
            id="completion_readiness:recorder",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    import asyncio

    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the completion readiness history is recorded; nothing to do")
        return 0
    asyncio.run(_record(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
