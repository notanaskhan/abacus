"""Record the `IntakeWithdrawalPurge` workflow's replay histories (N-01-T14; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_intake_purge <output-directory> [version]

Records the real workflow against throwaway containers with its activity replaced by a stub
(replay never runs activities), the 30-day window shortened to a second:
- `intake-purge-<version>-erased.json`: the erase answers 0 at once;
- `intake-purge-<version>-held.json`: the erase answers "wait a day" once (a hold), then 0.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.communications.api import (
    IntakePurgeInput,
    IntakeWithdrawalPurgeWorkflow,
    intake_purge_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_ERASED = "00000000-0000-4000-8000-0000000000d1"
_HELD = "00000000-0000-4000-8000-0000000000d2"
_NAMES = ("erased", "held")
_asked: dict[str, int] = {}


@activity.defn(name="communications.erase_withdrawn_intake")
async def _erase(given: IntakePurgeInput) -> int:
    _asked[given.upload_id] = _asked.get(given.upload_id, 0) + 1
    if given.upload_id == _HELD and _asked[given.upload_id] == 1:
        return 1  # the stand-in for a day while held
    return 0


async def _run(client: Client, upload: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        IntakeWithdrawalPurgeWorkflow.run,
        IntakePurgeInput(_TENANT, upload, wait_seconds=1),
        id=intake_purge_id(_TENANT, upload),
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record_all(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[IntakeWithdrawalPurgeWorkflow],
        activities=[_erase],
    ):
        for name, upload in (("erased", _ERASED), ("held", _HELD)):
            scrubbed = await decoded_and_scrubbed(await _run(client, upload), payload_codec())
            path = out / f"intake-purge-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"intake-purge-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record_all(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
