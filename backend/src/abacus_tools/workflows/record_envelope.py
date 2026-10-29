"""Record the `Envelope` workflow's replay histories (N-02-T14; ADR-090). See `histories.py` for
the fixture rules.

Run: python -m abacus_tools.workflows.record_envelope <output-directory> [version]

Records the real `EnvelopeWorkflow` against throwaway containers with its activities replaced
by stubs (replay never runs activities):
- `envelope-<version>-completed.json`: sent with one reminder due in a second; the reminder
  goes, two provider hints follow (viewed, then completed) and the evidence is recorded;
- `envelope-<version>-expired.json`: sent, nobody signs, the expiry fires.
Synthetic identifiers only. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import timedelta
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.clock import system_now
from abacus.kernel.temporal import payload_codec
from abacus.modules.signatures.api import (
    EnvelopeInput,
    EnvelopeWorkflow,
    ReminderDue,
    SendPlan,
    envelope_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_COMPLETED = "00000000-0000-4000-8000-0000000000e1"
_EXPIRED = "00000000-0000-4000-8000-0000000000e2"
_NAMES = ("completed", "expired")
_polls: dict[str, int] = {}


@activity.defn(name="signatures.envelope_send")
async def _send(given: EnvelopeInput) -> SendPlan:
    now = system_now()
    if given.envelope_id == _EXPIRED:
        return SendPlan("sent", (now + timedelta(seconds=2)).isoformat(), [])
    return SendPlan(
        "sent", (now + timedelta(hours=1)).isoformat(), [(now + timedelta(seconds=1)).isoformat()]
    )


@activity.defn(name="signatures.envelope_poll")
async def _poll(given: EnvelopeInput) -> str:
    _polls[given.envelope_id] = _polls.get(given.envelope_id, 0) + 1
    return "viewed" if _polls[given.envelope_id] == 1 else "completed"


@activity.defn(name="signatures.envelope_remind")
async def _remind(given: ReminderDue) -> str:
    return "skipped"


@activity.defn(name="signatures.envelope_expire")
async def _expire(given: EnvelopeInput) -> str:
    return "expired"


@activity.defn(name="signatures.envelope_complete")
async def _complete(given: EnvelopeInput) -> str:
    return "recorded"


async def _run(client: Client, envelope_id: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        EnvelopeWorkflow.run,
        EnvelopeInput(_TENANT, envelope_id),
        id=envelope_workflow_id(_TENANT, envelope_id),
        task_queue=_TASK_QUEUE,
    )
    if envelope_id == _COMPLETED:
        await asyncio.sleep(2)  # past the reminder
        for _ in range(2):
            await handle.signal(EnvelopeWorkflow.provider_hint)
            await asyncio.sleep(0.5)
    await handle.result()
    return await handle.fetch_history()


async def _record_all(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[EnvelopeWorkflow],
        activities=[_send, _poll, _remind, _expire, _complete],
    ):
        for name, envelope in (("completed", _COMPLETED), ("expired", _EXPIRED)):
            scrubbed = await decoded_and_scrubbed(await _run(client, envelope), payload_codec())
            path = out / f"envelope-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"envelope-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record_all(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
