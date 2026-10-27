"""SPEC-027 (TASK-050; ADR-090): the engagement agent replays its recorded histories, and a change
to what it schedules is detected as non-determinism.

Offline: `Replayer` needs no Temporal server and no codec. The histories
(`tests/workflows/histories/engagement-agent-v*.json`) were recorded by
`abacus_tools.workflows.record_engagement_agent` with a stub activity; they are never re-recorded.
"""

from __future__ import annotations

import base64
import re
from datetime import timedelta
from pathlib import Path

import pytest
from temporalio import workflow
from temporalio.client import WorkflowHistory
from temporalio.exceptions import ActivityError
from temporalio.worker import Replayer, UnsandboxedWorkflowRunner

from abacus.modules.agents.engagement_agent_workflow import EngagementAgent
from abacus.modules.agents.workflow_types import AgentEvent, AgentInput, HandleInput, HandleResult

HISTORIES = Path(__file__).resolve().parent / "histories"
ALL = sorted(HISTORIES.glob("engagement-agent-v*.json"))
IDS = [p.stem for p in ALL]


def _history(path: Path) -> WorkflowHistory:
    return WorkflowHistory.from_json("test-engagement-agent", path.read_text(encoding="utf-8"))


def test_the_histories_are_committed() -> None:
    assert IDS == [
        "engagement-agent-v1-failed-event-skipped",
        "engagement-agent-v1-handled-then-ended",
        # v2 (TASK-051): `patched("daily-tick")`; v1's still replay against the same code.
        "engagement-agent-v2-failed-event-skipped",
        "engagement-agent-v2-handled-then-ended",
        "engagement-agent-v2-ticked-then-ended",
        # v3 (R-01-T24): `patched("follow_up_policy_v1")`; v1's and v2's still replay.
        "engagement-agent-v3-failed-event-skipped",
        "engagement-agent-v3-handled-then-ended",
        "engagement-agent-v3-ticked-then-ended",
    ]


def _decoded(text: str) -> str:
    """The history with every payload's data decoded (they're plain JSON, base64)."""
    found = [text]
    for match in re.finditer(r'"data": "([A-Za-z0-9+/=]+)"', text):
        found.append(base64.b64decode(match.group(1)).decode("utf-8", "replace"))
    return "\n".join(found)


def test_v2_ticked_history_waited_then_handled_a_tick() -> None:
    text = _decoded(
        (HISTORIES / "engagement-agent-v2-ticked-then-ended.json").read_text(encoding="utf-8")
    )
    assert "engagement_agent.next_tick" in text
    assert "agent.tick" in text
    assert "daily-tick" in text  # the version marker


def test_v3_tick_carries_the_follow_up_policy_marker_and_v2_does_not() -> None:
    """R-01-T24 (ADR-090): the patched tick asks P-4 to read the firm's policy; a pre-change
    history's tick carries no marker, so its replay keeps the old constants."""
    v3 = _decoded(
        (HISTORIES / "engagement-agent-v3-ticked-then-ended.json").read_text(encoding="utf-8")
    )
    v2 = _decoded(
        (HISTORIES / "engagement-agent-v2-ticked-then-ended.json").read_text(encoding="utf-8")
    )
    assert "follow_up_policy_v1" in v3 and '"follow_up_policy":"v1"' in v3
    assert "follow_up_policy" not in v2


@pytest.mark.parametrize("path", ALL, ids=IDS)
async def test_the_agent_replays_its_recorded_history(path: Path) -> None:
    await Replayer(workflows=[EngagementAgent]).replay_workflow(_history(path))


@workflow.defn(name="EngagementAgent")
class _Renamed:
    """The same loop scheduling a differently named activity: replay must refuse it."""

    def __init__(self) -> None:
        self._events: list[AgentEvent] = []

    @workflow.signal(name="event")
    def event(self, event: AgentEvent) -> None:
        self._events.append(event)

    @workflow.run
    async def run(self, given: AgentInput) -> str:
        while True:
            await workflow.wait_condition(lambda: bool(self._events))
            while self._events:
                event = self._events.pop(0)
                try:
                    result = await workflow.execute_activity(
                        "engagement_agent.renamed",
                        HandleInput(
                            given.tenant_id,
                            given.engagement_id,
                            event.event_type,
                            event.event_id,
                            event.payload,
                        ),
                        result_type=HandleResult,
                        start_to_close_timeout=timedelta(minutes=2),
                    )
                except ActivityError:
                    continue
                if result.end:
                    return "ended"


async def test_a_changed_activity_sequence_is_non_determinism() -> None:
    path = HISTORIES / "engagement-agent-v1-handled-then-ended.json"
    with pytest.raises(workflow.NondeterminismError):
        # Unsandboxed: the test module itself defines the changed workflow.
        replayer = Replayer(workflows=[_Renamed], workflow_runner=UnsandboxedWorkflowRunner())
        await replayer.replay_workflow(_history(path))
