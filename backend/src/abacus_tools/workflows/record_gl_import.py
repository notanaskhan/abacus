"""Record the general ledger import workflow's replay histories (SPEC-034, TASK-069; ADR-090).
See `histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_gl_import <output-directory> [version]

Records the real `GlImportWorkflow` against throwaway containers with its activity replaced by a
stub (replay never runs activities):
- `gl-import-<version>-reconciled.json`: the import is processed and reconciled;
- `gl-import-<version>-waiting.json`: there's no trial balance yet.
From v2 (TASK-070) a reconciled import is then rendered as evidence (`gl_import.render`).
Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.connections.api import GlImportInput, GlImportWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_NAMES = ("reconciled", "waiting")
_WAITING = "00000000-0000-0000-0000-0000000000c2"


@activity.defn(name="gl_import.process")
async def _process(given: GlImportInput) -> str:
    return "waiting_for_tb" if given.import_id == _WAITING else "reconciled"


@activity.defn(name="gl_import.render")  # v2 (TASK-070)
async def _render(given: GlImportInput) -> list[str]:
    return ["00000000-0000-0000-0000-0000000000e1"]


async def _run(client: Client, name: str, import_id: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        GlImportWorkflow.run,
        GlImportInput(_TENANT, import_id),
        id=f"recorder-gl-import-{name}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[GlImportWorkflow],
        activities=[_process, _render],
    ):
        for name, import_id in (
            ("reconciled", "00000000-0000-0000-0000-0000000000c1"),
            ("waiting", _WAITING),
        ):
            scrubbed = await decoded_and_scrubbed(
                await _run(client, name, import_id), payload_codec()
            )
            path = out / f"gl-import-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"gl-import-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
