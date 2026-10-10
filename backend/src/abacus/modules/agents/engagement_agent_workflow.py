"""The engagement agent's workflow (SPEC-027; TASK-050; ADR-058, ADR-062, ADR-090). PROTECTED.

One long-lived workflow per engagement, `engagement-agent:<tenant_id>:<engagement_id>`. Domain
events arrive as `event` signals (`kernel.dispatch.signal_with_start`). Each runs one activity,
`engagement_agent.handle`, which reads the current state and applies the matching policy: the
workflow holds no business state, so replays stay deterministic and redeliveries harmless. It
continues as new to bound its history, and ends when the engagement is archived. Since v2
(`patched("daily-tick")`, TASK-051) it also ticks daily at 09:00 on business days in the firm's
time zone (the delay comes from an activity, so replay stays deterministic). A failing
event is logged and skipped: one bad event never stops the engagement's agent.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.workflow_types import (
        AgentEvent,
        AgentInput,
        HandleInput,
        HandleResult,
        NextTickInput,
    )

HANDLE: Final = "engagement_agent.handle"
NEXT_TICK: Final = "engagement_agent.next_tick"
TICK: Final = "agent.tick"
MAX_HANDLED: Final = 500  # events per run before continuing as new


@workflow.defn(name="EngagementAgent")
class EngagementAgent:
    def __init__(self) -> None:
        self._events: list[AgentEvent] = []
        self._tick_at: datetime | None = None

    @workflow.signal(name="event")
    def event(self, event: AgentEvent) -> None:
        self._events.append(event)

    async def _wait(self, given: AgentInput) -> None:
        """Until an event arrives or (v2, SPEC-027 TASK-051) the daily tick is due: then the tick
        joins the queue as an `agent.tick` event."""
        if not workflow.patched("daily-tick"):
            await workflow.wait_condition(lambda: bool(self._events))
            return
        if self._tick_at is None:
            seconds = await workflow.execute_activity(
                NEXT_TICK,
                NextTickInput(given.tenant_id),
                result_type=int,
                start_to_close_timeout=timedelta(seconds=30),
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            self._tick_at = workflow.now() + timedelta(seconds=seconds)
        remaining = self._tick_at - workflow.now()
        try:
            await workflow.wait_condition(
                lambda: bool(self._events), timeout=max(remaining, timedelta(seconds=1))
            )
        except TimeoutError:
            self._tick_at = None
            self._events.append(AgentEvent(TICK, str(workflow.uuid4()), {}))

    @workflow.run
    async def run(self, given: AgentInput) -> str:
        handled = 0
        while True:
            await self._wait(given)
            while self._events:
                event = self._events.pop(0)
                try:
                    result = await workflow.execute_activity(
                        HANDLE,
                        HandleInput(
                            given.tenant_id,
                            given.engagement_id,
                            event.event_type,
                            event.event_id,
                            event.payload,
                        ),
                        result_type=HandleResult,
                        start_to_close_timeout=timedelta(minutes=2),
                        retry_policy=RetryPolicy(maximum_attempts=5),
                    )
                except ActivityError:
                    workflow.logger.warning("engagement_agent.event_failed")
                    continue
                handled += 1
                if result.end:
                    return "ended"
            if handled >= MAX_HANDLED or workflow.info().is_continue_as_new_suggested():
                workflow.continue_as_new(given)
