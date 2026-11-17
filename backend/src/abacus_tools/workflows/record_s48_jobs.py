"""Record S48's new workflows' replay histories (ADR-090; S48 end pass). See `histories.py`.

Run: python -m abacus_tools.workflows.record_s48_jobs <output-directory>

Each runs the real workflow against throwaway containers with its activity stubbed (replay never
runs activities):
- `flux-analytics-v1-computed.json`: one A-08-T21 flux compute that persisted the lines;
- `component-instructions-send-v1-completed.json`: an A-09-T27 send that waited out its 10-second
  Undo window, then completed once;
- `component-late-sweep-v1-swept.json`: one A-09-T28 hourly sweep that marked two deliverables
  late.
A history already on disk is never overwritten: only the missing ones are recorded.
"""

from __future__ import annotations

import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.assurance.api import (
    ComponentLateSweep,
    FluxAnalyticsWorkflow,
    FluxRunInput,
    InstructionsSendInput,
    InstructionsSendWorkflow,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE = "abacus-recorder"
TENANT = "00000000-0000-4000-8000-0000000000b1"
SET_ID = "00000000-0000-4000-8000-000000004821"
SEND_ID = "00000000-0000-4000-8000-000000004927"
FLUX = "flux-analytics-v1-computed.json"
SEND = "component-instructions-send-v1-completed.json"
LATE = "component-late-sweep-v1-swept.json"
_FILES = (FLUX, SEND, LATE)


@activity.defn(name="assurance.analytics.compute")
async def _compute(given: FluxRunInput) -> str:
    return "computed"


@activity.defn(name="assurance.component_instructions.complete_send")
async def _complete(given: InstructionsSendInput) -> str:
    return "sent"


@activity.defn(name="assurance.component_late.sweep")
async def _sweep() -> int:
    return 2


async def _flux(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        FluxAnalyticsWorkflow.run,
        FluxRunInput(TENANT, SET_ID),
        id=f"flux:{TENANT}:{SET_ID}:1",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _send(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        InstructionsSendWorkflow.run,
        InstructionsSendInput(TENANT, SEND_ID),
        id=f"component_send:{TENANT}:{SEND_ID}",
        task_queue=_TASK_QUEUE,
    )
    await handle.result()
    return await handle.fetch_history()


async def _late(client: Client) -> WorkflowHistory:
    handle = await client.start_workflow(
        ComponentLateSweep.run, id="component_late:platform", task_queue=_TASK_QUEUE
    )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[FluxAnalyticsWorkflow, InstructionsSendWorkflow, ComponentLateSweep],
        activities=[_compute, _complete, _sweep],
    ):
        for name, run in ((FLUX, _flux), (SEND, _send), (LATE, _late)):
            if (out / name).exists():
                continue
            scrubbed = await decoded_and_scrubbed(await run(client), payload_codec())
            (out / name).write_text(scrubbed.to_json())
            print(f"recorded {out / name}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if all((out / name).exists() for name in _FILES):
        print("every S48 history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
