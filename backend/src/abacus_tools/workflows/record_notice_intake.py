"""Record `NoticeIntakeWorkflow`'s replay histories (N-04-T07; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_notice_intake <output-directory> [version]

Records the real workflow with stubs: a file read before the intake existed, a `text_ready` signal
and a `refused` signal: `notice-intake-<version>-{already,read,refused}.json`. Refuses to overwrite
an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.notices.api import IntakeReadStep, NoticeIntakeInput, NoticeIntakeWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_READ_ALREADY = "00000000-0000-0000-0000-0000000000a1"
_WAITING = "00000000-0000-0000-0000-0000000000a2"
_NAMES = ("already", "read", "refused")


@activity.defn(name="notice_intake.read_if_ready")
async def _read_if_ready(step: IntakeReadStep) -> str:
    return "ready" if step.intake_id == _READ_ALREADY else "extracting"


@activity.defn(name="notice_intake.read")
async def _read(step: IntakeReadStep) -> str:
    return "manual_entry" if step.refusal else "ready"


@activity.defn(name="notice_intake.mark_failed")
async def _mark_failed(step: IntakeReadStep) -> str:
    return "failed"


async def _run(client: Client, name: str) -> WorkflowHistory:
    intake = _READ_ALREADY if name == "already" else _WAITING
    handle = await client.start_workflow(
        NoticeIntakeWorkflow.run,
        NoticeIntakeInput(_TENANT, intake),
        id=f"recorder-notice-intake-{name}",
        task_queue=_TASK_QUEUE,
    )
    if name == "read":
        await handle.signal("text_ready")
    elif name == "refused":
        await handle.signal("refused", "consent_7216")
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[NoticeIntakeWorkflow],
        activities=[_read_if_ready, _read, _mark_failed],
    ):
        for name in _NAMES:
            scrubbed = await decoded_and_scrubbed(await _run(client, name), payload_codec())
            path = out / f"notice-intake-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"notice-intake-{version}-{name}.json" for name in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
