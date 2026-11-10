"""Record `PostReleaseClocksWorkflow`'s replay history (A-07-T36; ADR-090). See `histories.py` for
the rules.

Run: python -m abacus_tools.workflows.record_post_release <output-directory>

`post-release-v1-stopped.json`: a release dated in the past, so each boundary is due at once: the
first fire reports a running clock, the second finds both clocks stopped and the workflow ends. The
activity is stubbed. A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.api import (
    PostReleaseClocksInput,
    PostReleaseClocksWorkflow,
    PostReleaseFireResult,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "post-release-v1-stopped.json"
_FIRED: list[int] = []


@activity.defn(name="assurance.post_release.fire")
async def _fire(
    tenant_id: str, engagement_id: str, work_item_id: str, kind: str, boundary: str, at: str
) -> PostReleaseFireResult:
    _FIRED.append(1)
    return PostReleaseFireResult(running=len(_FIRED) == 1, both_stopped=len(_FIRED) > 1)


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[PostReleaseClocksWorkflow], activities=[_fire]
    ):
        clocks = PostReleaseClocksInput(
            "00000000-0000-4000-8000-0000000000b1",
            "00000000-0000-4000-8000-0000000004a1",
            "00000000-0000-4000-8000-0000000004e1",
            "2020-01-06",
        )
        handle = await client.start_workflow(
            PostReleaseClocksWorkflow.run,
            clocks,
            id=f"post_release:{clocks.tenant_id}:{clocks.work_item_id}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the post-release history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
