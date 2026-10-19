"""Record the procedure selection workflow's replay histories (SPEC-037, TASK-083; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_procedure_select <output-directory> [version]

Records the real `ProcedureSelectWorkflow` against throwaway containers with its activities
replaced by stubs (replay never runs activities):
- `procedure-select-<version>-selected.json`: the selection activity completes;
- `procedure-select-<version>-failed.json`: it fails every attempt, and the fail step runs.
Refuses to overwrite an existing file.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.fieldwork.api import ProcedureSelectInput, ProcedureSelectWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_TENANT = "00000000-0000-0000-0000-000000000001"
_FAILING = "00000000-0000-0000-0000-0000000000f0"
_NAMES = ("selected", "failed")


@activity.defn(name="procedure.select")
async def _select(given: ProcedureSelectInput) -> str:
    if given.procedure_id == _FAILING:
        raise RuntimeError("stub failure")
    return "selected"


@activity.defn(name="procedure.fail")
async def _fail(given: ProcedureSelectInput) -> None:
    return None


async def _run(client: Client, name: str, procedure_id: str) -> WorkflowHistory:
    handle = await client.start_workflow(
        ProcedureSelectWorkflow.run,
        ProcedureSelectInput(_TENANT, procedure_id, "00000000-0000-0000-0000-0000000000b1"),
        id=f"recorder-procedure-select-{name}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[ProcedureSelectWorkflow],
        activities=[_select, _fail],
    ):
        for name, procedure in (
            ("selected", "00000000-0000-0000-0000-0000000000a1"),
            ("failed", _FAILING),
        ):
            scrubbed = await decoded_and_scrubbed(
                await _run(client, name, procedure), payload_codec()
            )
            path = out / f"procedure-select-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    if refuse_overwrite(out, [f"procedure-select-{version}-{n}.json" for n in _NAMES]):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
