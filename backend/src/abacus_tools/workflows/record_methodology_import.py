"""Record the Methodology importer workflow's replay histories (K-01-T21; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_methodology_import <output-directory> [version]

Records the real `MethodologyImportWorkflow` against throwaway containers with its activities
replaced by stubs (replay never runs activities):
- `methodology-import-<version>-completed.json`: nine pages, two batches (the second carrying the
  first's run), then the version written for review;
- `methodology-import-<version>-held.json`: the PII hold ends it after the pages are read;
- `methodology-import-<version>-stopped.json`: the import was cancelled before the first batch;
- `methodology-import-<version>-failed.json`: the extract step fails, and the import is failed.
Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from contextlib import suppress
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowFailureError, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import (
    ImportBatchInput,
    ImportBatchOutcome,
    ImportFailInput,
    ImportFinishInput,
    ImportPagesOutcome,
    MethodologyImportInput,
    MethodologyImportWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_USER = "00000000-0000-0000-0000-0000000000b1"
_NAMES = ("completed", "held", "stopped", "failed")
_IMPORTS = {
    "completed": "00000000-0000-0000-0000-0000000000e1",
    "held": "00000000-0000-0000-0000-0000000000e2",
    "stopped": "00000000-0000-0000-0000-0000000000e3",
    "failed": "00000000-0000-0000-0000-0000000000e4",
}


@activity.defn(name="methodology.extract_pages")
async def _extract(given: MethodologyImportInput) -> ImportPagesOutcome:
    if given.import_id == _IMPORTS["failed"]:
        raise ApplicationError("unreadable", non_retryable=True)
    return ImportPagesOutcome(9, held=given.import_id == _IMPORTS["held"])


@activity.defn(name="agents.importer_parse_batch")
async def _batch(given: ImportBatchInput) -> ImportBatchOutcome:
    if given.import_id == _IMPORTS["stopped"]:
        return ImportBatchOutcome(None, stop=True)
    return ImportBatchOutcome(f"00000000-0000-0000-0000-0000000000a{given.first_page}", stop=False)


@activity.defn(name="methodology.finish_import")
async def _finish(given: ImportFinishInput) -> str:
    return "needs_review"


@activity.defn(name="methodology.fail_import")
async def _fail(given: ImportFailInput) -> None:
    return None


async def _run(client: Client, name: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        MethodologyImportWorkflow.run,
        MethodologyImportInput(_TENANT, _IMPORTS[name], _USER),
        id=f"recorder-methodology-import-{name}",
        task_queue=_TASK_QUEUE,
    )
    with suppress(WorkflowFailureError):  # the failed history's workflow ends `failed`, not raised
        await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[MethodologyImportWorkflow],
        activities=[_extract, _batch, _finish, _fail],
    ):
        for name in _NAMES:
            scrubbed = await decoded_and_scrubbed(await _run(client, name), payload_codec())
            path = out / f"methodology-import-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"methodology-import-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
