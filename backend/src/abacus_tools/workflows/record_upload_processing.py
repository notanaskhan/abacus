"""Record the upload processing workflow's replay history (SPEC-029, TASK-054; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_upload_processing <output-directory> [version]
[words-failed|pii-scan-failed]

Records one run of the real `UploadProcessing` workflow against throwaway containers, with its
activities replaced by stubs (replay never runs activities):
`upload-processing-<version>-extracted.json`. v2 (TASK-055) adds the `checks` step, v3
(TASK-056) `previews`, v4 (P-03-T05) `words`, recorded as `upload-processing-v4-words.json`.
`v4 words-failed` records the words step failing for good and the run still ending with the
extraction's status. v5 (P-03-T13) adds `pii_scan` (`upload-processing-v5-pii-scan.json`), and
`v5 pii-scan-failed` the scan failing for good; v6 (R-01-T09) adds `portal_drop_sort` for an inbox
file (`upload-processing-v6-portal-drop-sort.json`). Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.api import (
    UPLOAD_INBOX,
    UPLOAD_VERSION,
    UploadInput,
    UploadProcessing,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_VERSION_ID = "00000000-0000-0000-0000-0000000000f1"


@activity.defn(name="upload.extract")
async def _stub(given: UploadInput) -> str:
    return "extracted"


@activity.defn(name="upload.check")
async def _check_stub(given: UploadInput) -> int:
    return 3


@activity.defn(name="upload.preview")
async def _preview_stub(given: UploadInput) -> str:
    return "pages"


@activity.defn(name="upload.words")
async def _words_stub(given: UploadInput) -> int:
    return 1


@activity.defn(name="upload.words")
async def _words_failing_stub(given: UploadInput) -> int:
    raise ApplicationError("IntegrityError", non_retryable=True)


@activity.defn(name="upload.pii_scan")
async def _pii_scan_stub(given: UploadInput) -> int:
    return 2


@activity.defn(name="upload.pii_scan")
async def _pii_scan_failing_stub(given: UploadInput) -> int:
    raise ApplicationError("IntegrityError", non_retryable=True)


@activity.defn(name="upload.portal_drop_sort")
async def _drop_sort_stub(given: UploadInput) -> str:
    return "rule_linked"


# The outcome a history is named after: from v4 on, the step the version added.
_OUTCOMES = {"v4": "words", "v5": "pii-scan", "v6": "portal-drop-sort"}


def _file_name(version: str, outcome: str | None = None) -> str:
    named = outcome or _OUTCOMES.get(version, "extracted")
    return f"upload-processing-{version}-{named}.json"


async def _record(out: Path, version: str, stack: Stack, outcome: str | None = None) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[UploadProcessing],
        activities=[
            _stub,
            _check_stub,
            _preview_stub,
            _words_failing_stub if outcome == "words-failed" else _words_stub,
            _pii_scan_failing_stub if outcome == "pii-scan-failed" else _pii_scan_stub,
            _drop_sort_stub,
        ],
    ):
        handle = await client.start_workflow(
            UploadProcessing.run,
            # v6 (R-01-T09): the drop sort runs for an inbox file (a portal drop) only.
            UploadInput(_TENANT, UPLOAD_INBOX if version == "v6" else UPLOAD_VERSION, _VERSION_ID),
            id=f"recorder-upload-processing-{version}-{outcome or 'ok'}",
            task_queue=_TASK_QUEUE,
        )
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
    path = out / _file_name(version, outcome)
    path.write_text(scrubbed.to_json())
    print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    outcome = argv[2] if len(argv) > 2 else None
    if outcome not in (None, "words-failed", "pii-scan-failed"):
        print("outcome is words-failed, pii-scan-failed or nothing")
        return 2
    if refuse_overwrite(out, [_file_name(version, outcome)]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack, outcome)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
