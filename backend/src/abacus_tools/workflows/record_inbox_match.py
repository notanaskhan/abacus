"""Record the matcher workflow's replay histories (SPEC-033, TASK-066; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_inbox_match <output-directory> [version]

Records the real `InboxMatchWorkflow` against throwaway containers with its activities replaced
by stubs (replay never runs activities):
- `inbox-match-<version>-completed.json`: a run is created, a slot granted, the match done;
- `inbox-match-<version>-skipped.json`: no run is created (nobody to act for, or nothing to
  match). Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import (
    InboxMatchWorkflow,
    MatchInput,
    MatchRunInput,
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


@activity.defn(name="inbox_match.create_run")
async def _create(given: MatchInput) -> str | None:
    return None if given.requested_by is None else _RUN


@activity.defn(name="screening.acquire_slot")
async def _acquire(given: RunInput) -> SlotGrant:
    return SlotGrant(True, 600)


@activity.defn(name="inbox_match.match")
async def _match(given: MatchRunInput) -> dict[str, object]:
    return {"status": "completed", "run_id": _RUN}  # the workflow's run outcome, as data


@activity.defn(name="screening.fail_run")
async def _fail(given: object) -> dict[str, object]:
    return {"status": "failed", "run_id": _RUN}


@activity.defn(name="screening.release_slot")
async def _release(given: RunInput) -> None:
    return None


async def _run(client: Client, name: str, requested_by: str | None) -> WorkflowHistory:
    handle = await client.start_workflow(
        InboxMatchWorkflow.run,
        MatchInput(_TENANT, _FILE, "e1", requested_by),
        id=f"recorder-inbox-match-{name}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[InboxMatchWorkflow],
        activities=[_create, _acquire, _match, _release, _fail],
    ):
        for name, who in (
            ("completed", "00000000-0000-0000-0000-0000000000b1"),
            ("skipped", None),
        ):
            scrubbed = await decoded_and_scrubbed(await _run(client, name, who), payload_codec())
            path = out / f"inbox-match-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"inbox-match-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
