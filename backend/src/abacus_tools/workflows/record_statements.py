"""Records the statements workflows' histories with stubbed activities (A-06-T25; ADR-090).

python -m abacus_tools.workflows.record_statements tests/workflows/histories v1
"""

from __future__ import annotations

import contextlib
import sys
from pathlib import Path
from typing import Any

from temporalio import activity
from temporalio.client import Client, WorkflowFailureError, WorkflowHandle
from temporalio.common import RetryPolicy
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.reporting.api import (
    DRAFT_ACTIVITY,
    DRAFT_FAILED_ACTIVITY,
    TIE_OUT_ACTIVITY,
    FsDraftInput,
    FsDraftWorkflow,
    TieOutInput,
    TieOutWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_ENGAGEMENT = "00000000-0000-0000-0000-0000000000e1"
_ITEM = "00000000-0000-0000-0000-0000000000a1"
_GOOD = "00000000-0000-0000-0000-0000000000b1"
_BAD = "00000000-0000-0000-0000-0000000000b2"
_VERSION = "00000000-0000-0000-0000-0000000000c1"


@activity.defn(name=DRAFT_ACTIVITY)
async def _draft(given: FsDraftInput) -> str:
    if given.run_id == _BAD:
        raise ApplicationError("no final trial balance", non_retryable=True)
    return _VERSION


@activity.defn(name=DRAFT_FAILED_ACTIVITY)
async def _failed(given: FsDraftInput) -> None:
    del given


@activity.defn(name=TIE_OUT_ACTIVITY)
async def _tied(given: TieOutInput) -> str:
    return given.statement_version_id


async def _save(handle: WorkflowHandle[Any, Any], path: Path) -> None:  # Any: either workflow
    with contextlib.suppress(WorkflowFailureError):  # the failed draft's ends failed, on purpose
        await handle.result()
    scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
    path.write_text(scrubbed.to_json())
    print(f"recorded {path}")


async def _record(out: Path, version: str, stack: Stack) -> None:
    client: Client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[FsDraftWorkflow, TieOutWorkflow],
        activities=[_draft, _failed, _tied],
    ):
        for name, run in (("drafted", _GOOD), ("failed", _BAD)):
            handle = await client.start_workflow(
                FsDraftWorkflow.run,
                FsDraftInput(_TENANT, run, _ENGAGEMENT, _ITEM),
                id=f"recorder-fs-draft-{name}",
                task_queue=_TASK_QUEUE,
                retry_policy=RetryPolicy(maximum_attempts=1),
            )
            await _save(handle, out / f"fs-draft-{version}-{name}.json")
        handle = await client.start_workflow(
            TieOutWorkflow.run,
            TieOutInput(_TENANT, _VERSION),
            id="recorder-tie-out",
            task_queue=_TASK_QUEUE,
        )
        await _save(handle, out / f"tie-out-{version}-tied.json")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    names = [f"fs-draft-{version}-drafted.json", f"fs-draft-{version}-failed.json",
             f"tie-out-{version}-tied.json"]  # fmt: skip
    if refuse_overwrite(out, names):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
