"""Record `ArchiveLockWorkflow`'s replay history (A-07-T37; ADR-090). See `histories.py` for the
rules.

Run: python -m abacus_tools.workflows.record_archive_lock <output-directory>

`archive-lock-v1-locked.json`: one lock with the activities stubbed: the seal built, the evidence
retention extended to the floor, the archive finished. A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.api import ArchiveLockInput, ArchiveLockWorkflow, ArchiveSealResult
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
NAME = "archive-lock-v1-locked.json"
_MANIFEST = "00000000-0000-4000-8000-0000000006a1"


@activity.defn(name="assurance.archive_lock.seal")
async def _seal(tenant_id: str, work_item_id: str, archive_id: str) -> ArchiveSealResult:
    return ArchiveSealResult(_MANIFEST, "d" * 64, False)


@activity.defn(name="assurance.archive_lock.extend_evidence")
async def _extend(tenant_id: str, work_item_id: str, archive_id: str) -> int:
    return 41


@activity.defn(name="assurance.archive_lock.finish")
async def _finish(tenant_id: str, work_item_id: str, archive_id: str, manifest_id: str) -> str:
    return "locked"


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[ArchiveLockWorkflow],
        activities=[_seal, _extend, _finish],
    ):
        lock = ArchiveLockInput(
            "00000000-0000-4000-8000-0000000000b1",
            "00000000-0000-4000-8000-0000000004e1",
            "00000000-0000-4000-8000-0000000006b1",
        )
        handle = await client.start_workflow(
            ArchiveLockWorkflow.run,
            lock,
            id=f"archive_lock:{lock.tenant_id}:{lock.work_item_id}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the archive lock history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
