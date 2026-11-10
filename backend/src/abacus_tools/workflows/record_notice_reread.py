"""Record `NoticeIntakeRereadWorkflow`'s replay history (N-04-T19; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_notice_reread <output-directory> [version]

Records the real workflow with a stub: `notice-intake-reread-<version>.json`. Refuses to overwrite
an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.notices.api import (
    IntakeReadStep,
    NoticeIntakeInput,
    NoticeIntakeRereadWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_INTAKE = "00000000-0000-0000-0000-0000000000a3"


@activity.defn(name="notice_intake.reread")
async def _reread(step: IntakeReadStep) -> str:
    return "ready"


async def _record(path: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[NoticeIntakeRereadWorkflow],
        activities=[_reread],
    ):
        handle = await client.start_workflow(
            NoticeIntakeRereadWorkflow.run,
            NoticeIntakeInput(_TENANT, _INTAKE),
            id="recorder-notice-intake-reread",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        history = await handle.fetch_history()
    path.write_text((await decoded_and_scrubbed(history, payload_codec())).to_json())
    print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    name = f"notice-intake-reread-{version}.json"
    if refuse_overwrite(out, [name]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out / name, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
