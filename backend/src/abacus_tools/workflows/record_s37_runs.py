"""Record S37's new workflows' replay histories (P-10-T43; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_s37_runs <output-directory>

Activities are stubbed (no database), so each history pins the command sequence only:

- `session-v1-read-only.json`: one message, one inline turn, then `close`.
- `session-v1-child-run.json`: one message whose turn proposes writes; the child
  `AgentRunWorkflow` (a stub here) starts once, abandoned on close.
- `session-v1-side-queue.json`: a message whose turn asks a question, a second message answered
  while the question stays open, then the answer, then `close`.
- `run-events-prune-v1.json` (P-10-T44): one prune activity.

A history on disk is never overwritten.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Final

from temporalio import activity, workflow
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import AgentRunInput, RunEventsPruneWorkflow
from abacus.modules.workbench.session_workflow import (
    SessionInput,
    TurnDone,
    WorkbenchSessionWorkflow,
    session_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TENANT: Final = "00000000-0000-4000-8000-0000000000aa"
_QUEUE: Final = "record-s37"
_CHILD: Final = "00000000-0000-4000-8000-0000000000c1"


@workflow.defn(name="AgentRunWorkflow")
class _StubRun:
    @workflow.run
    async def run(self, p: AgentRunInput) -> str:
        return "awaiting_plan_approval"


class _Stubs:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario

    def activities(self) -> list[Any]:  # Any: activity callables
        @activity.defn(name="workbench.session.turn")
        async def turn(tenant_id: str, session_id: str, kind: str, seq: int) -> TurnDone:
            if self.scenario == "child-run":
                return TurnDone(child_run_id=_CHILD)
            if self.scenario == "side-queue" and seq == 1:
                return TurnDone(asked=2)
            return TurnDone()

        @activity.defn(name="agents.run_events.prune")
        async def prune() -> int:
            return 3

        return [turn, prune]


def _session_id(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


async def _save(client: Client, out: Path, name: str, handle: Any) -> None:  # noqa: ANN401 -- a workflow handle
    await asyncio.wait_for(handle.result(), timeout=180)
    scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
    (out / name).write_text(scrubbed.to_json())
    print(f"recorded {out / name}")


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    plan = [
        ("session-v1-read-only.json", "read-only"),
        ("session-v1-child-run.json", "child-run"),
        ("session-v1-side-queue.json", "side-queue"),
    ]
    for n, (name, scenario) in enumerate(plan, start=1):
        if (out / name).exists():
            print(f"{name} is recorded; skipped")
            continue
        queue = f"{_QUEUE}-{n}"
        async with Worker(
            client,
            task_queue=queue,
            workflows=[WorkbenchSessionWorkflow, _StubRun],
            activities=_Stubs(scenario).activities(),
        ):
            sid = _session_id(n)
            handle = await client.start_workflow(
                WorkbenchSessionWorkflow.run,
                SessionInput(_TENANT, sid),
                id=session_workflow_id(_TENANT, sid),
                task_queue=queue,
                start_signal="user_message",
                start_signal_args=[1],
            )
            if scenario == "side-queue":
                await asyncio.sleep(1)
                await handle.signal("user_message", 3)  # answered first; the question stays open
                await asyncio.sleep(1)
                await handle.signal("answer", [4, 2])
            await asyncio.sleep(1)
            await handle.signal("close")
            await _save(client, out, name, handle)
    name = "run-events-prune-v1.json"
    if (out / name).exists():
        print(f"{name} is recorded; skipped")
        return
    async with Worker(
        client,
        task_queue=f"{_QUEUE}-prune",
        workflows=[RunEventsPruneWorkflow],
        activities=_Stubs("prune").activities(),
    ):
        handle = await client.start_workflow(
            RunEventsPruneWorkflow.run, id="run_events_prune:record", task_queue=f"{_QUEUE}-prune"
        )
        await _save(client, out, name, handle)


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
