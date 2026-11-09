"""Record `ReleaseWorkflow`'s replay history (A-07-T30; ADR-090). See `histories.py` for the rules.

Run: python -m abacus_tools.workflows.record_release <output-directory>

`release-v1-released.json`: one in-app release with the activities stubbed: the grant consumed
and the final render queued as version 2, the render job done on its first read, G8 recorded.
A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.api import ReleaseRequest, ReleaseWorkflow, RenderedFinal
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "release-v1-released.json"
_FINAL = "00000000-0000-4000-8000-0000000005f2"
_EVIDENCE = "00000000-0000-4000-8000-0000000005e2"
_RELEASE = "00000000-0000-4000-8000-0000000005a1"


@activity.defn(name="assurance.release.consume_and_render")
async def _consume(request: ReleaseRequest) -> int:
    return 2


@activity.defn(name="assurance.release.final_render")
async def _final(request: ReleaseRequest, version_no: int) -> RenderedFinal:
    return RenderedFinal(_FINAL, _EVIDENCE, "a" * 64, 3)


@activity.defn(name="assurance.release.record")
async def _record_release(request: ReleaseRequest, final: RenderedFinal) -> str:
    return _RELEASE


@activity.defn(name="assurance.release.fail")
async def _fail(request: ReleaseRequest, reason: str) -> None:
    return None


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[ReleaseWorkflow],
        activities=[_consume, _final, _record_release, _fail],
    ):
        request = ReleaseRequest(
            "00000000-0000-4000-8000-0000000000b1",
            "00000000-0000-4000-8000-0000000004a1",
            "00000000-0000-4000-8000-0000000004e1",
            "00000000-0000-4000-8000-0000000005c1",
            "00000000-0000-4000-8000-0000000001d1",
            "00000000-0000-4000-8000-0000000005b1",
            "00000000-0000-4000-8000-0000000005d1",
            "b" * 64,
            "c" * 64,
            "release-recorder",
        )
        handle = await client.start_workflow(
            ReleaseWorkflow.run,
            request,
            id=f"release:{request.tenant_id}:{request.work_item_id}:{request.grant_id}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the release history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
