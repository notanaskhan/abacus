"""Record `SealVerifyWorkflow`'s and `SealVerifySweepWorkflow`'s replay histories (A-07-T42;
ADR-090; the S35 end pass). See `histories.py` for the rules.

Run: python -m abacus_tools.workflows.record_seal_verify <output-directory>

The activities are stubbed (no database), so each history pins the command sequence only:

- `seal-verify-v1-matched.json`: one locked archive's seal checked on request; it matches.
- `seal-verify-sweep-v1-swept.json`: the monthly sweep over every firm's locked archives.

A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.api import (
    SealVerifyInput,
    SealVerifySweepWorkflow,
    SealVerifyWorkflow,
    VerifyResult,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
MATCHED = "seal-verify-v1-matched.json"
SWEPT = "seal-verify-sweep-v1-swept.json"
_TENANT = "00000000-0000-4000-8000-0000000000b1"
_ARCHIVE = "00000000-0000-4000-8000-0000000006b1"


@activity.defn(name="assurance.archive.verify_seal")
async def _verify(tenant_id: str, archive_id: str) -> VerifyResult:
    return VerifyResult(archive_id, True)


@activity.defn(name="assurance.archive.verify_all")
async def _verify_all() -> int:
    return 3


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[SealVerifyWorkflow, SealVerifySweepWorkflow],
        activities=[_verify, _verify_all],
    ):
        if not (out / MATCHED).exists():
            handle = await client.start_workflow(
                SealVerifyWorkflow.run,
                SealVerifyInput(_TENANT, _ARCHIVE),
                id=f"seal_verify:{_TENANT}:{_ARCHIVE}:00000000-0000-4000-8000-000000000001",
                task_queue=_TASK_QUEUE,
            )
            await handle.result()
            scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
            (out / MATCHED).write_text(scrubbed.to_json())
            print(f"recorded {out / MATCHED}")
        if not (out / SWEPT).exists():
            sweep = await client.start_workflow(
                SealVerifySweepWorkflow.run, id="seal_verify:platform", task_queue=_TASK_QUEUE
            )
            await sweep.result()
            scrubbed = await decoded_and_scrubbed(await sweep.fetch_history(), payload_codec())
            (out / SWEPT).write_text(scrubbed.to_json())
            print(f"recorded {out / SWEPT}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / MATCHED).exists() and (out / SWEPT).exists():
        print("the seal verification histories are recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
