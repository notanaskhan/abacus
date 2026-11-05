"""Record `FormExtractionWorkflow`'s replay histories (P-11-T26; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_form_extraction <output-directory> [version]

Records the workflow against throwaway containers with its activity replaced by a stub:
`form-extraction-<version>-recorded.json`. Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.evidence.form_extraction_workflow import FormExtractionWorkflow
from abacus.modules.evidence.workflow_types import FormExtractionInput
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_VERSION = "00000000-0000-0000-0000-0000000000c1"


@activity.defn(name="forms.extract")
async def _extract(given: FormExtractionInput) -> int:
    return 6


async def _run(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        FormExtractionWorkflow.run,
        FormExtractionInput(_TENANT, _VERSION),
        id="recorder-form-extraction",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    path = refuse_overwrite(out / f"form-extraction-{version}-recorded.json")
    client = await connect(stack)
    async with Worker(
        client, task_queue=_TASK_QUEUE, workflows=[FormExtractionWorkflow], activities=[_extract]
    ):
        history = await _run(client)
    path.write_text(await decoded_and_scrubbed(history, payload_codec()), encoding="utf-8")


def main() -> None:
    out = Path(sys.argv[1])
    version = sys.argv[2] if len(sys.argv) > 2 else "v1"
    run_with_stack(lambda stack: _record(out, version, stack))


if __name__ == "__main__":
    main()
