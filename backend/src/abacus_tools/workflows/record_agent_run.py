"""Record `AgentRunWorkflow`'s replay histories (P-10-T29 part 1, P-10-T32 part 2; ADR-090). See
`histories.py` for the rules.

Run: python -m abacus_tools.workflows.record_agent_run <output-directory>

Each history runs one plan with the activities stubbed (no database), so it pins the workflow's
command sequence only:

- `agent-run-v2-approved.json`: a 4-step plan over 3 levels, approved, every step succeeds.
- `agent-run-v2-decision-resumed.json`: Planning materiality as a decision card; the run is
  `blocked_on_decision` until `decision_decided`, then only the held branch resumes (AC-W4).
- `agent-run-v2-question-skipped.json`: a question skipped; the skip default applies (AC-W5).
- `agent-run-v2-step-retried.json`: the Internal Control step fails, a person retries it, the new
  row succeeds and its dependant runs (AC-W6).
- `agent-run-v2-stopped.json`: a held run stopped by a person.

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
from abacus.modules.agents.run_activities import PlanState, RunFacts, StepOutcome
from abacus.modules.agents.run_waits import WaitState
from abacus.modules.agents.run_workflow import AgentRunInput, AgentRunWorkflow
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

_TASK_QUEUE: Final = "abacus-recorder"
_TENANT: Final = "00000000-0000-4000-8000-0000000000b1"
_ENGAGEMENT: Final = "00000000-0000-4000-8000-0000000004e1"


def _step(key: str, level: int, kind: str = "tool", *deps: str) -> dict[str, object]:
    return {
        "key": key,
        "label": key,
        "level": level,
        "kind": kind,
        "tool": "ledger.read_trial_balance" if kind == "tool" else None,
        "arguments": {},
        "depends_on": list(deps),
    }


PLANS: Final[dict[str, list[dict[str, object]]]] = {
    "approved": [
        _step("tb", 0),
        _step("risks", 1, "tool", "tb"),
        _step("materiality_calc", 1, "tool", "tb"),
        _step("summary", 2, "narration", "risks", "materiality_calc"),
    ],
    "decision-resumed": [
        _step("tb", 0),
        _step("materiality", 1, "decision", "tb"),
        _step("ic", 1, "tool", "tb"),
        _step("sampling", 2, "tool", "materiality"),
    ],
    "question-skipped": [
        _step("population", 0, "question"),
        _step("eligibility", 1, "tool", "population"),
    ],
    "step-retried": [
        _step("tb", 0),
        _step("ic", 1, "tool", "tb"),
        _step("deficiencies", 2, "tool", "ic"),
    ],
    "stopped": [
        _step("tb", 0),
        _step("materiality", 1, "decision", "tb"),
    ],
}


class _Stubs:
    """The activities, stubbed per scenario; held steps resolve once the scenario says so."""

    def __init__(self, scenario: str) -> None:
        self.scenario = scenario
        self.plan = PLANS[scenario]
        self.failed_once = False
        self.resolved = False

    def activities(self) -> list[Callable[..., Awaitable[object]]]:
        stubs = self

        @activity.defn(name="agents.run_v2.load")
        async def load(tenant_id: str, run_id: str) -> RunFacts:
            return RunFacts("created", _ENGAGEMENT, [], [], {}, 3, stubs.plan)

        @activity.defn(name="agents.run_v2.record_plan")
        async def record_plan(
            tenant_id: str, run_id: str, steps: list[dict[str, object]], problems: list[str]
        ) -> int:
            return 1

        @activity.defn(name="agents.run_v2.plan_state")
        async def plan_state(tenant_id: str, run_id: str) -> PlanState:
            return PlanState(1, "approved", stubs.plan)

        @activity.defn(name="agents.run_v2.set_state")
        async def set_state(
            tenant_id: str,
            run_id: str,
            state: str,
            reason: str | None,
            blocked: dict[str, object] | None,
        ) -> int:
            return 1

        @activity.defn(name="agents.run_v2.paused")
        async def paused(tenant_id: str, engagement_id: str | None) -> bool:
            return False

        @activity.defn(name="agents.run_v2.execute_step")
        async def execute_step(
            tenant_id: str,
            run_id: str,
            seq: int,
            step: dict[str, object],
            attempt: int = 1,
            retry_of_seq: int | None = None,
        ) -> StepOutcome:
            kind = str(step["kind"])
            if kind == "decision":
                return StepOutcome("blocked", wait_ref="00000000-0000-4000-8000-00000000dc01")
            if kind == "question":
                return StepOutcome(
                    "waiting_on_inputs", wait_ref="00000000-0000-4000-8000-00000000a501"
                )
            if stubs.scenario == "step-retried" and step["key"] == "ic" and retry_of_seq is None:
                return StepOutcome("failed", "tool_failed")
            return StepOutcome("succeeded", records_read=12, active_ms=900)

        @activity.defn(name="agents.run_v2.wait_state")
        async def wait_state(tenant_id: str, run_id: str, seq: int, kind: str) -> WaitState:
            if not stubs.resolved:
                return WaitState("open")
            if kind == "question":
                return WaitState("skipped_default", "succeeded")
            return WaitState("decided", "succeeded")

        @activity.defn(name="agents.run_v2.cancel_held")
        async def cancel_held(tenant_id: str, run_id: str) -> int:
            return 1

        @activity.defn(name="agents.run_v2.complete")
        async def complete(tenant_id: str, run_id: str, state: str, reason: str | None) -> None:
            return None

        return [
            load,
            record_plan,
            plan_state,
            set_state,
            paused,
            execute_step,
            wait_state,
            cancel_held,
            complete,
        ]


async def _drive(scenario: str, stubs: _Stubs, handle: WorkflowHandle[object, str]) -> None:
    await asyncio.sleep(1)
    await handle.signal("plan_decided", "approved")
    await asyncio.sleep(2)
    if scenario in ("decision-resumed", "question-skipped"):
        stubs.resolved = True
        signal = "decision_decided" if scenario == "decision-resumed" else "question_answered"
        await handle.signal(signal)
    elif scenario == "step-retried":
        await handle.signal("step_retry", "ic")
    elif scenario == "stopped":
        await handle.signal("stop")


async def _record_one(client: Client, out: Path, scenario: str) -> None:
    name = f"agent-run-v2-{scenario}.json"
    if (out / name).exists():
        print(f"{name} is recorded; skipped")
        return
    stubs = _Stubs(scenario)
    queue = f"{_TASK_QUEUE}-{scenario}"
    async with Worker(
        client, task_queue=queue, workflows=[AgentRunWorkflow], activities=stubs.activities()
    ):
        run = f"00000000-0000-4000-8000-{list(PLANS).index(scenario) + 1:012d}"
        handle = await client.start_workflow(
            AgentRunWorkflow.run,
            AgentRunInput(_TENANT, run),
            id=f"agent_run:{_TENANT}:{run}",
            task_queue=queue,
        )
        await _drive(scenario, stubs, handle)
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / name).write_text(scrubbed.to_json())
        print(f"recorded {out / name}")


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    for scenario in PLANS:
        await _record_one(client, out, scenario)


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
