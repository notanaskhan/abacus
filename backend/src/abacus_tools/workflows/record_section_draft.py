"""Record `SectionDraftWorkflow`'s replay history (A-04-T41; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_section_draft <output-directory> [version]

Records the real workflow against throwaway containers with its activities replaced by stubs:
`section-draft-<version>-drafted.json`. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import (
    RunInput,
    SectionDraftInput,
    SectionDraftWorkflow,
    SlotGrant,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_RUN = "00000000-0000-0000-0000-0000000000d1"
_PAPER = "00000000-0000-0000-0000-0000000000d2"


@activity.defn(name="screening.acquire_slot")
async def _acquire(given: RunInput) -> SlotGrant:
    return SlotGrant(granted=True, max_wait_seconds=60)


@activity.defn(name="screening.release_slot")
async def _release(given: RunInput) -> None:
    return None


@activity.defn(name="section_draft.draft")
async def _draft(given: SectionDraftInput) -> dict[str, str]:
    return {"status": "completed", "run_id": _RUN}


@activity.defn(name="agents.persist_run_record")
async def _persist(given: RunInput) -> None:
    return None


async def _run(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        SectionDraftWorkflow.run,
        SectionDraftInput(_TENANT, _RUN, _PAPER, "gap", "gap_analysis"),
        id="recorder-section-draft",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[SectionDraftWorkflow],
        activities=[_acquire, _release, _draft, _persist],
    ):
        scrubbed = await decoded_and_scrubbed(await _run(client), payload_codec())
    path = out / f"section-draft-{version}-drafted.json"
    path.write_text(scrubbed.to_json())
    print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"section-draft-{version}-drafted.json"]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
