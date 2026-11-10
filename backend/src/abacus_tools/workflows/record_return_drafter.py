"""Record `ReturnDrafterWorkflow`'s replay histories (T-04-T25; ADR-090). See `histories.py`.

Run: python -m abacus_tools.workflows.record_return_drafter <output-directory>

The draft activity is stubbed (no database), so each history pins the command sequence only:

- `return-drafter-v1-proposed.json`: consent in force; the draft proposes; the run succeeds.
- `return-drafter-v1-consent-waited.json`: the first draft answers `waiting_on_inputs`; the run
  waits until `inputs_ready`, then drafts again and succeeds (AC-9.3).
- `return-drafter-v1-stopped.json`: a run waiting on consent stopped by a person.

A history on disk is never overwritten.
"""

from __future__ import annotations

import asyncio
import sys
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Final

from temporalio import activity
from temporalio.client import Client, WorkflowHandle
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.tax.drafter_workflow import (
    DraftInput,
    DraftOutcome,
    ReturnDrafterWorkflow,
    drafter_workflow_id,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE: Final = "abacus-recorder-drafter"
_TENANT: Final = "00000000-0000-4000-8000-0000000000b1"
_ENTITY: Final = "00000000-0000-4000-8000-00000000fe1d"
SCENARIOS: Final = ("proposed", "consent-waited", "stopped")


class _Stubs:
    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.calls = 0

    def activities(self) -> list[Callable[..., Awaitable[object]]]:
        stubs = self

        @activity.defn(name="agents.run_v2.set_state")
        async def set_state(
            tenant_id: str,
            run_id: str,
            state: str,
            reason: str | None,
            blocked: dict[str, object] | None,
        ) -> int:
            return 1

        @activity.defn(name="tax.drafter.draft")
        async def draft(p: DraftInput) -> DraftOutcome:
            stubs.calls += 1
            if stubs.scenario != "proposed" and stubs.calls == 1:
                return DraftOutcome("waiting_on_inputs", ["consent_7216"])
            return DraftOutcome(
                "proposed",
                [],
                "00000000-0000-4000-8000-00000000a0a1",
                "00000000-0000-4000-8000-00000000c0c1",
                1,
            )

        return [set_state, draft]


async def _drive(scenario: str, handle: WorkflowHandle[object, str]) -> None:
    if scenario == "proposed":
        return
    await asyncio.sleep(2)
    await handle.signal("inputs_ready" if scenario == "consent-waited" else "stop")


async def _record_one(client: Client, out: Path, scenario: str) -> None:
    name = f"return-drafter-v1-{scenario}.json"
    if (out / name).exists():
        print(f"{name} is recorded; skipped")
        return
    stubs = _Stubs(scenario)
    queue = f"{_TASK_QUEUE}-{scenario}"
    async with Worker(
        client, task_queue=queue, workflows=[ReturnDrafterWorkflow], activities=stubs.activities()
    ):
        run = f"00000000-0000-4000-8000-{SCENARIOS.index(scenario) + 1:012d}"
        handle = await client.start_workflow(
            ReturnDrafterWorkflow.run,
            DraftInput(_TENANT, run, _ENTITY, 2025),
            id=drafter_workflow_id(_TENANT, run),
            task_queue=queue,
        )
        await _drive(scenario, handle)
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / name).write_text(scrubbed.to_json())
        print(f"recorded {out / name}")


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    for scenario in SCENARIOS:
        await _record_one(client, out, scenario)


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
