"""Record the entry assessor workflow's replay histories (SPEC-037 Q4, TASK-085; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_entry_assess <output-directory> [version]

Records the real `EntryAssessWorkflow` against throwaway containers with its activities replaced
by stubs (replay never runs activities):
- `entry-assess-<version>-completed.json`: a run is created, a slot granted, the draft made;
- `entry-assess-<version>-skipped.json`: no run is created (nobody to act for, or no document).
Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import (
    EntryAssessInput,
    EntryAssessRunInput,
    EntryAssessWorkflow,
    RunInput,
    SlotGrant,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_RUN = "00000000-0000-0000-0000-0000000000a1"
_FILE = "00000000-0000-0000-0000-0000000000f1"
_NAMES = ("completed", "skipped")
_ENGAGEMENT = "00000000-0000-0000-0000-0000000000d1"
_NOBODY = "00000000-0000-0000-0000-000000000000"


@activity.defn(name="entry_assess.create_run")
async def _create(given: EntryAssessInput) -> str | None:
    return None if given.requested_by == _NOBODY else _RUN


@activity.defn(name="screening.acquire_slot")
async def _acquire(given: RunInput) -> SlotGrant:
    return SlotGrant(True, 600)


@activity.defn(name="entry_assess.assess")
async def _draft(given: EntryAssessRunInput) -> dict[str, object]:
    return {"status": "completed", "run_id": _RUN}  # the workflow's run outcome, as data


@activity.defn(name="screening.fail_run")
async def _fail(given: object) -> dict[str, object]:
    return {"status": "failed", "run_id": _RUN}


@activity.defn(name="screening.release_slot")
async def _release(given: RunInput) -> None:
    return None


async def _run(client: Client, name: str, requested_by: str) -> WorkflowHistory:
    given = EntryAssessInput(_TENANT, _ENGAGEMENT, _FILE, "e1", requested_by)
    handle = await client.start_workflow(
        EntryAssessWorkflow.run,
        given,
        id=f"recorder-entry-assess-{name}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[EntryAssessWorkflow],
        activities=[_create, _acquire, _draft, _release, _fail],
    ):
        for name, who in (
            ("completed", "00000000-0000-0000-0000-0000000000b1"),
            ("skipped", _NOBODY),
        ):
            scrubbed = await decoded_and_scrubbed(await _run(client, name, who), payload_codec())
            path = out / f"entry-assess-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"entry-assess-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
