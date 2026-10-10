"""Record the engagement agent's replay histories (SPEC-027, TASK-050; ADR-090). See
`histories.py` for the fixture rules.

Run: python -m abacus_tools.workflows.record_engagement_agent <output-directory> [version]

Records two runs of the real `EngagementAgent` workflow against throwaway containers, with its
activity replaced by a stub (a history records what was scheduled and returned; replay never runs
activities):
- `engagement-agent-<version>-handled-then-ended.json`: three events, the third reports the
  engagement archived, so the agent ends;
- `engagement-agent-<version>-failed-event-skipped.json`: the first event's activity fails every
  attempt and is skipped; the next ends the agent;
- `engagement-agent-<version>-ticked-then-ended.json` (v2, TASK-051): the idle agent ticks once
  (the next-tick stub answers 2 seconds), then an event ends it.

Refuses to overwrite an existing file: a changed workflow records `v<N+1>`.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from temporalio import activity
from temporalio.client import Client, WorkflowHistory
from temporalio.exceptions import ApplicationError
from temporalio.worker import Worker

from abacus.kernel.temporal import payload_codec
from abacus.modules.agents.api import (
    ENGAGEMENT_AGENT_HANDLE as HANDLE,
)
from abacus.modules.agents.api import (
    ENGAGEMENT_AGENT_NEXT_TICK as NEXT_TICK,
)
from abacus.modules.agents.api import (
    AgentEvent,
    AgentInput,
    EngagementAgent,
    HandleInput,
    HandleResult,
    NextTickInput,
)
from abacus_tools.stack import Stack, connect, run_with_stack
from abacus_tools.workflows.histories import decoded_and_scrubbed
from abacus_tools.workflows.record_retrieval import refuse_overwrite

_TASK_QUEUE = "abacus-recorder"
_NAMES = ("handled-then-ended", "failed-event-skipped", "ticked-then-ended")
_TICK_SECONDS = 2  # the stub's delay to the next tick, so a tick fires while recording
_TENANT = "00000000-0000-0000-0000-000000000001"
_ENGAGEMENT = "00000000-0000-0000-0000-0000000000e1"


@activity.defn(name=NEXT_TICK)
async def _next_tick(given: NextTickInput) -> int:
    return _TICK_SECONDS


@activity.defn(name=HANDLE)
async def _stub(given: HandleInput) -> HandleResult:
    if given.event_type == "fails":
        raise ApplicationError("stub failure", type="StubFailure", non_retryable=True)
    return HandleResult(given.event_type == "ends")


async def _run(
    client: Client, name: str, events: list[str], wait_for_tick: bool = False
) -> WorkflowHistory:
    handle = await client.start_workflow(
        EngagementAgent.run,
        AgentInput(_TENANT, _ENGAGEMENT),
        id=f"recorder-engagement-agent-{name}",
        task_queue=_TASK_QUEUE,
        start_signal="event",
        start_signal_args=[AgentEvent(events[0], "00000000-0000-0000-0000-000000000101", {})],
    )
    if wait_for_tick:
        await asyncio.sleep(_TICK_SECONDS + 3)  # the idle agent ticks once
    for n, event in enumerate(events[1:], start=2):
        await handle.signal(
            "event", AgentEvent(event, f"00000000-0000-0000-0000-00000000010{n}", {})
        )
    await handle.result()
    return await handle.fetch_history()


async def _record(out: Path, version: str, stack: Stack) -> None:
    client = await connect(stack)
    codec = payload_codec()
    async with Worker(
        client,
        task_queue=_TASK_QUEUE,
        workflows=[EngagementAgent],
        activities=[_stub, _next_tick],
    ):
        runs = {
            "handled-then-ended": (
                ["engagement.created", "evidence_version.created", "ends"],
                False,
            ),
            "failed-event-skipped": (["fails", "ends"], False),
            "ticked-then-ended": (["engagement.created", "ends"], True),
        }
        for name, (events, tick) in runs.items():
            history = await _run(client, f"{version}-{name}", events, tick)
            scrubbed = await decoded_and_scrubbed(history, codec)
            path = out / f"engagement-agent-{version}-{name}.json"
            path.write_text(scrubbed.to_json())
            print(f"recorded {path}")


def main(argv: list[str]) -> int:
    out = Path(argv[0]) if argv else Path("tests/workflows/histories")
    version = argv[1] if len(argv) > 1 else "v1"
    names = [f"engagement-agent-{version}-{n}.json" for n in _NAMES]  # v2: with the tick
    if refuse_overwrite(out, names):
        return 1

    async def record(stack: Stack) -> None:
        await _record(out, version, stack)

    run_with_stack(record)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
