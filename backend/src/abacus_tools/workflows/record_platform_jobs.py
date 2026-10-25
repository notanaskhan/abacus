"""Record the platform jobs' replay histories (Q-01-T26; ADR-090). See `histories.py` for the
fixture rules.

Run: python -m abacus_tools.workflows.record_platform_jobs <output-directory>

Records the real `SpendAnomalyWorkflow` and `NotificationPurgeWorkflow` against throwaway
containers with their activities replaced by stubs (replay never runs activities):
- `spend-anomaly-v1-flagged.json`: one pass that flagged one engagement;
- `notification-purge-v1-purged.json`: one pass that purged three notifications.
Each run is started the way its Schedule starts it: no argument, its own id. Refuses to overwrite
an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHandle, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.notifications.api import NOTIFICATION_PURGE_ID, NotificationPurgeWorkflow
from abacus.modules.platform.api import SPEND_ANOMALY_ID, SpendAnomalyWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_FILES = ("spend-anomaly-v1-flagged.json", "notification-purge-v1-purged.json")


@activity.defn(name="platform.flag_spend_anomalies")
async def _flag() -> int:
    return 1


@activity.defn(name="notifications.purge_expired")
async def _purge() -> int:
    return 3


async def _run(client: Client, workflow: type, workflow_id: str) -> WorkflowHistory:
    handle: WorkflowHandle[object, int] = await client.start_workflow(
        workflow.run,  # pyright: ignore[reportUnknownArgumentType,reportUnknownMemberType] -- a @workflow.defn class
        id=workflow_id,
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[SpendAnomalyWorkflow, NotificationPurgeWorkflow],
        activities=[_flag, _purge],
    ):
        runs = (
            (SpendAnomalyWorkflow, SPEND_ANOMALY_ID, _FILES[0]),
            (NotificationPurgeWorkflow, NOTIFICATION_PURGE_ID, _FILES[1]),
        )
        for workflow, workflow_id, name in runs:
            scrubbed = await decoded_and_scrubbed(
                await _run(client, workflow, workflow_id), payload_codec()
            )
            path = out / name
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if refuse_overwrite(out, list(_FILES)):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
