"""Record the `AttachmentTriage` workflow's replay histories (N-01-T12; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_attachment_triage <output-directory> [version]

Records the real `AttachmentTriageWorkflow` against throwaway containers with its activities
replaced by stubs (replay never runs activities):
- `attachment-triage-<version>-waiting.json`: every upload step succeeds; the matched attachment
  becomes Waiting;
- `attachment-triage-<version>-step-failed.json`: the word layer fails on every attempt; the
  steps after it still run and the attachment stays New.
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
from abacus.modules.communications.api import (
    AttachmentTriageWorkflow,
    TriageInput,
    attachment_triage_id,
)
from abacus.modules.evidence.api import UploadInput
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-4000-8000-000000000001"
_WAITING = "00000000-0000-4000-8000-0000000000c1"
_FAILED = "00000000-0000-4000-8000-0000000000c2"
_NAMES = ("waiting", "step-failed")


@activity.defn(name="upload.extract")
async def _extract(given: UploadInput) -> str:
    return "extracted"


@activity.defn(name="upload.words")
async def _words(given: UploadInput) -> int:
    if given.source_id == _FAILED:
        raise ApplicationError("unreadable", non_retryable=True)
    return 2


@activity.defn(name="upload.pii_scan")
async def _pii(given: UploadInput) -> int:
    return 1


@activity.defn(name="upload.masked_preview")
async def _masked(given: UploadInput) -> str:
    return "pages"


@activity.defn(name="communications.attachment_triaged")
async def _triaged(given: TriageInput) -> str:
    return "new" if given.attachment_id == _FAILED else "waiting"


async def _run(client: Client, attachment: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        AttachmentTriageWorkflow.run,
        TriageInput(_TENANT, attachment),
        id=attachment_triage_id(_TENANT, attachment),
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record_all(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[AttachmentTriageWorkflow],
        activities=[_extract, _words, _pii, _masked, _triaged],
    ):
        for name, attachment in (("waiting", _WAITING), ("step-failed", _FAILED)):
            scrubbed = await decoded_and_scrubbed(await _run(client, attachment), payload_codec())
            path = out / f"attachment-triage-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"attachment-triage-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record_all(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
