"""Record the K-1 release's replay histories (T-02-T21; T-02 §4.11; ADR-090). See `histories.py`
for the fixture rules.

Run: python -m abacus_tools.workflows.record_k1_release <output-directory> [version]

Records runs of the real workflow against throwaway containers, with its activities replaced by
stubs (replay never runs activities): the Undo window's timer (a second here, from the input),
then
- `k1-release-<version>-completed.json`: the grant consumed, two recipients delivered, completed;
- `k1-release-<version>-undone.json`: an Undo voided the grant, so the run ends there;
- `k1-release-<version>-delivery-failed.json`: the second delivery is refused (decided, not
  retried), and `fail` records it; the first recipient stays delivered.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.tax.api import (
    K1DeliveryInput,
    K1ReleaseFailure,
    K1ReleaseInput,
    K1ReleaseWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_RELEASES = {
    "completed": "00000000-0000-4000-8000-0000000001a1",
    "undone": "00000000-0000-4000-8000-0000000001a2",
    "delivery-failed": "00000000-0000-4000-8000-0000000001a3",
}
_PACKAGES = ["00000000-0000-4000-8000-0000000001b1", "00000000-0000-4000-8000-0000000001b2"]
_NAME = "k1-release-{v}-{case}.json"


@activity.defn(name="schedule_k_release.start")
async def _start(given: K1ReleaseInput) -> str:
    return "undone" if given.release_id == _RELEASES["undone"] else "running"


@activity.defn(name="schedule_k_release.packages")
async def _packages(given: K1ReleaseInput) -> list[str]:
    return list(_PACKAGES)


@activity.defn(name="schedule_k_release.deliver")
async def _deliver(given: K1DeliveryInput) -> str:
    if given.release_id == _RELEASES["delivery-failed"] and given.package_id == _PACKAGES[1]:
        raise ApplicationError("contact_missing", type="DeliveryRefused", non_retryable=True)
    return "released"


@activity.defn(name="schedule_k_release.complete")
async def _complete(given: K1ReleaseInput) -> str:
    return "completed"


@activity.defn(name="schedule_k_release.fail")
async def _fail(given: K1ReleaseFailure) -> str:
    return "failed"


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[K1ReleaseWorkflow],
        activities=[_start, _packages, _deliver, _complete, _fail],
    ):
        for case, release_id in _RELEASES.items():
            handle = await client.start_workflow(
                K1ReleaseWorkflow.run,
                K1ReleaseInput(_TENANT, release_id, 1),
                id=f"recorder-k1-release-{version}-{case}",
                task_queue=_TASK_QUEUE,
            )
            await handle.result()
            scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
            path = out / _NAME.format(v=version, case=case)
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [_NAME.format(v=version, case=case) for case in _RELEASES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
