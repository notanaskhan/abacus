"""Record `AgentRunWorkflow`'s replay history (P-10-T29; ADR-090). See `histories.py` for the
rules.

Run: python -m abacus_tools.workflows.record_agent_run <output-directory>

`agent-run-v1-succeeded.json`: one run with the activities stubbed: the plan (one narration step)
recorded as version 1, the person's `plan_decided` signal, the plan read back approved, the step
dispatched and succeeded, the run completed. A history on disk is never overwritten.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from temporalio import activity
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import (
    AgentRunInput,
    AgentRunWorkflow,
    RunV2Facts,
    RunV2PlanState,
    RunV2StepOutcome,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed

JsonObject = dict[str, Any]  # Any: JSON (the converter decodes Any, not object)
_TASK_QUEUE = "abacus-recorder"
NAME = "agent-run-v1-succeeded.json"
_ENGAGEMENT = "00000000-0000-4000-8000-0000000004a1"
_STEPS: list[JsonObject] = [
    {"key": "narrate", "label": "Narrate", "level": 0, "kind": "narration"}
]


@activity.defn(name="agents.run_v2.load")
async def _load(tenant_id: str, run_id: str) -> RunV2Facts:
    return RunV2Facts("queued", _ENGAGEMENT, [], [], {}, 1, _STEPS)


@activity.defn(name="agents.run_v2.record_plan")
async def _record_plan(
    tenant_id: str,
    run_id: str,
    steps: list[JsonObject],
    problems: list[str],
) -> int:
    return 1


@activity.defn(name="agents.run_v2.plan_state")
async def _plan_state(tenant_id: str, run_id: str) -> RunV2PlanState:
    return RunV2PlanState(1, "approved", _STEPS)


@activity.defn(name="agents.run_v2.set_state")
async def _set_state(
    tenant_id: str,
    run_id: str,
    state: str,
    reason: str | None,
    blocked: JsonObject | None,
) -> int:
    return 1


@activity.defn(name="agents.run_v2.paused")
async def _paused(tenant_id: str, engagement_id: str | None) -> bool:
    return False


@activity.defn(name="agents.run_v2.execute_step")
async def _execute(
    tenant_id: str,
    run_id: str,
    seq: int,
    step: JsonObject,
    attempt: int = 1,
) -> RunV2StepOutcome:
    return RunV2StepOutcome("succeeded")


@activity.defn(name="agents.run_v2.complete")
async def _complete(tenant_id: str, run_id: str, state: str, reason: str | None) -> None:
    return None


async def _record(out: Path, stack: Stack) -> None:
    client = await connect(stack)
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[AgentRunWorkflow],
        activities=[_load, _record_plan, _plan_state, _set_state, _paused, _execute, _complete],
    ):
        run = AgentRunInput(
            "00000000-0000-4000-8000-0000000000b1", "00000000-0000-4000-8000-0000000007a1"
        )
        handle = await client.start_workflow(
            AgentRunWorkflow.run,
            run,
            id=f"agent_run:{run.tenant_id}:{run.run_id}",
            task_queue=_TASK_QUEUE,
        )
        await handle.signal(AgentRunWorkflow.plan_decided, "approved")
        await handle.result()
        scrubbed = await decoded_and_scrubbed(await handle.fetch_history(), payload_codec())
        (out / NAME).write_text(scrubbed.to_json())
        print(f"recorded {out / NAME}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    if (out / NAME).exists():
        print("the agent run history is recorded; nothing to do")
        return 0

    async def record(stack: Stack) -> None:
        await _record(out, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
