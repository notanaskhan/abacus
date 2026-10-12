"""Record the upload processing workflow's replay history (SPEC-029, TASK-054; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_upload_processing <output-directory> [version]

Records one run of the real `UploadProcessing` workflow against throwaway containers, with its
activity replaced by a stub (replay never runs activities):
`upload-processing-<version>-extracted.json`. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import UPLOAD_VERSION, UploadInput, UploadProcessing
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_VERSION_ID = "00000000-0000-0000-0000-0000000000f1"


@activity.defn(name="upload.extract")
async def _stub(given: UploadInput) -> str:
    return "extracted"


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[UploadProcessing], activities=[_stub]
    ):
        handle = await client.start_workflow(
            UploadProcessing.run,
            UploadInput(_TENANT, UPLOAD_VERSION, _VERSION_ID),
            id=f"recorder-upload-processing-{version}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
    path = out / f"upload-processing-{version}-extracted.json"
    path.write_text(scrubbed.to_json())
    print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"upload-processing-{version}-extracted.json"]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
