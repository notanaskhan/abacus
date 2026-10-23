"""Record the `NotificationEmail` workflow's replay histories (P-01-T12; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_notification_email <output-directory> [version]

Records the real `NotificationEmailWorkflow` against throwaway containers with its activities
replaced by stubs (replay never runs activities):
- `notification-email-<version>-sent.json`: the send succeeds and the outcome is recorded;
- `notification-email-<version>-failed.json`: the send fails on every attempt, and the delivery
  is still settled (`failed`).
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.notifications.api import (
    DeliveryOutcome,
    NotificationEmailInput,
    NotificationEmailWorkflow,
    notification_email_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_SENT = "00000000-0000-4000-8000-0000000000a1"
_FAILED = "00000000-0000-4000-8000-0000000000a2"
_NAMES = ("sent", "failed")


@activity.defn(name="notifications.send_email")
async def _send(given: NotificationEmailInput) -> str:
    if given.notification_id == _FAILED:
        raise ApplicationError("TransportRefused", type="TransportRefused", non_retryable=True)
    return "sent"


@activity.defn(name="notifications.record_delivery")
async def _record(given: DeliveryOutcome) -> str:
    return given.outcome


async def _run(client: Client, notification_id: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        NotificationEmailWorkflow.run,
        NotificationEmailInput(_TENANT, notification_id),
        id=notification_email_id(_TENANT, notification_id),
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record_all(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[NotificationEmailWorkflow],
        activities=[_send, _record],
    ):
        for name, notification in (("sent", _SENT), ("failed", _FAILED)):
            scrubbed = await decoded_and_scrubbed(
                await _run(client, notification), payload_codec()
            )
            path = out / f"notification-email-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"notification-email-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record_all(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
