"""Record S42's new workflow's replay histories (T-05-T54; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_s42_runs <output-directory>

Activities are stubbed (no database), so each history pins the command sequence only:

- `memo-draft-v1-drafted.json`: the run set running, one draft, the run succeeds.
- `memo-draft-v1-failed.json`: the draft answers a refusal; the run fails with that reason.
- `workbench-session-v2-read-only.json` (W-02-T15): one message, one v2 turn, then `close`.
- `workbench-session-v2-child-run.json`: one message whose v2 turn proposes writes; the child's
  workflow is started once through the start-child activity.
- `workbench-session-v2-side-queue.json` (W-02-T15 rest): a v2 turn asks a question, a second
  message is answered while it stays open, then the answer, then `close`.

A history on disk is never overwritten.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Final

from temporalio import activity
from temporalio.client import Client
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.tax.api import MemoDraftInput, MemoDraftWorkflow
from abacus.modules.workbench.api import (
    SessionInput,
    TurnDone,
    WorkbenchSessionWorkflow,
    session_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_QUEUE: Final = "abacus-recorder-s42"
_TENANT: Final = "00000000-0000-4000-8000-0000000000b1"
_RETURN: Final = "00000000-0000-4000-8000-00000000fe1d"
_CHILD: Final = "00000000-0000-4000-8000-0000000000c2"  # the child run the turn wrote


def _activities(scenario: str) -> list[Any]:  # Any: activity callables of several signatures
    @activity.defn(name="agents.run_v2.set_state")
    async def set_state(
        tenant_id: str,
        run_id: str,
        state: str,
        reason: str | None,
        blocked: dict[str, Any] | None,  # Any: JSON (Temporal cannot decode `object`)
    ) -> int:
        return 1

    @activity.defn(name="tax.memo.draft")
    async def draft(p: MemoDraftInput) -> str:
        return "drafted" if scenario == "drafted" else "uncited_answer"

    @activity.defn(name="workbench.session.turn_v2")
    async def turn_v2(tenant_id: str, session_id: str, kind: str, seq: int) -> TurnDone:
        if scenario == "side-queue" and seq == 1:
            return TurnDone(asked=2)
        return TurnDone(child_run_id=_CHILD) if scenario == "child-run" else TurnDone()

    @activity.defn(name="workbench.session.start_child")
    async def start_child(tenant_id: str, run_id: str) -> None:
        return None

    return [set_state, draft, turn_v2, start_child]


def _run_id(n: int) -> str:
    return f"00000000-0000-4000-8000-{n:012d}"


async def _save(client: Client, out: Path, name: str, handle: Any) -> None:  # noqa: ANN401 -- a workflow handle
    await asyncio.wait_for(handle.result(), timeout=180)  # a stuck run fails, not hangs
    scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
    (out / name).write_text(scrubbed.to_json())
    print(f"recorded {out / name}")


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    plan = [("memo-draft-v1-drafted.json", "drafted"), ("memo-draft-v1-failed.json", "failed")]
    for n, (name, scenario) in enumerate(plan, start=1):
        if (out / name).exists():
            print(f"{name} is recorded; skipped")
            continue
        queue = f"{_QUEUE}-{n}"
        async with Worker(
            client,
            task_queue=queue,
            workflows=[MemoDraftWorkflow],
            activities=_activities(scenario),
        ):
            run = _run_id(n)
            handle = await client.start_workflow(
                MemoDraftWorkflow.run,
                MemoDraftInput(_TENANT, run, _RETURN, ["overview", "capital"]),
                id=f"memo-draft:{_TENANT}:{run}",
                task_queue=queue,
            )
            await _save(client, out, name, handle)
    sessions = [
        ("workbench-session-v2-read-only.json", "read-only"),
        ("workbench-session-v2-child-run.json", "child-run"),
        ("workbench-session-v2-side-queue.json", "side-queue"),
    ]
    for n, (name, scenario) in enumerate(sessions, start=10):
        if (out / name).exists():
            print(f"{name} is recorded; skipped")
            continue
        queue = f"{_QUEUE}-{n}"
        async with Worker(
            client,
            task_queue=queue,
            workflows=[WorkbenchSessionWorkflow],
            activities=_activities(scenario),
        ):
            sid = _run_id(n)
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


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
