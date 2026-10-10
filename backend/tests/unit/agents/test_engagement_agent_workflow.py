"""SPEC-027 (TASK-050; ADR-062): the engagement agent's workflow loop, offline. Temporal's
`workflow` module is replaced by a fake: signals queue events, each runs one activity in order,
a failing event is skipped, the agent continues as new to bound its history, and ends when the
engagement is archived."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from temporalio.exceptions import ActivityError

from abacus.modules.agents import engagement_agent_workflow as module
from abacus.modules.agents.engagement_agent_workflow import (
    HANDLE,
    MAX_HANDLED,
    NEXT_TICK,
    TICK,
    EngagementAgent,
)
from abacus.modules.agents.workflow_types import (
    AgentEvent,
    AgentInput,
    HandleInput,
    HandleResult,
    NextTickInput,
)

GIVEN = AgentInput("t", "e")


def _ignore(*args: object, **kwargs: object) -> None:
    return None


class _Idle(Exception):
    """The fake clock: nothing left to wait for."""


class _ContinuedAsNew(Exception):
    pass


class _Fake:
    def __init__(
        self, agent: EngagementAgent, results: dict[str, HandleResult | Exception]
    ) -> None:
        self.agent = agent
        self.results = results
        self.handled: list[str] = []
        self.suggested = False
        self.logger = SimpleNamespace(warning=_ignore)
        self.v2 = False  # `patched("daily-tick")`: v1 histories replay without the tick
        self.ticks_left = 1  # how many idle waits time out into a tick before going idle
        self.asked_tick = 0
        self.clock = datetime(2026, 10, 12, 12, 0, tzinfo=UTC)

    def patched(self, name: str) -> bool:
        assert name == "daily-tick"
        return self.v2

    def now(self) -> datetime:
        return self.clock

    def uuid4(self) -> uuid.UUID:
        return uuid.uuid4()

    async def wait_condition(
        self, ready: Callable[[], bool], timeout: timedelta | None = None
    ) -> None:
        if ready():
            return
        if timeout is not None and self.ticks_left > 0:
            self.ticks_left -= 1
            self.clock += timeout
            raise TimeoutError
        raise _Idle

    async def execute_activity(
        self, name: str, given: HandleInput | NextTickInput, **_: object
    ) -> HandleResult | int:
        if name == NEXT_TICK:
            assert isinstance(given, NextTickInput) and given.tenant_id == GIVEN.tenant_id
            self.asked_tick += 1
            return 3600
        assert name == HANDLE
        assert isinstance(given, HandleInput)
        assert (given.tenant_id, given.engagement_id) == (GIVEN.tenant_id, GIVEN.engagement_id)
        self.handled.append(given.event_type)
        found = self.results.get(given.event_type, HandleResult(False))
        if isinstance(found, Exception):
            raise found
        return found

    def info(self) -> SimpleNamespace:
        return SimpleNamespace(is_continue_as_new_suggested=lambda: self.suggested)

    def continue_as_new(self, given: AgentInput) -> None:
        raise _ContinuedAsNew


def _run(
    monkeypatch: pytest.MonkeyPatch,
    events: list[str],
    results: dict[str, HandleResult | Exception] | None = None,
) -> tuple[_Fake, str | None, type[Exception] | None]:
    agent = EngagementAgent()
    fake = _Fake(agent, results or {})
    for n, name in enumerate(events):
        agent.event(AgentEvent(name, str(n), {}))
    monkeypatch.setattr(module, "workflow", fake)
    try:
        outcome = asyncio.run(agent.run(GIVEN))
        return fake, outcome, None
    except (_Idle, _ContinuedAsNew) as stopped:
        return fake, None, type(stopped)


def test_ac1_events_are_handled_in_order_one_activity_each(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake, outcome, stopped = _run(monkeypatch, ["engagement.created", "evidence_version.created"])
    assert fake.handled == ["engagement.created", "evidence_version.created"]
    assert outcome is None and stopped is _Idle  # waiting for the next event


def test_ac1_the_agent_ends_when_the_engagement_is_archived(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake, outcome, _ = _run(
        monkeypatch,
        ["evidence_version.created", "connection.created", "inbox_file.added"],
        {"connection.created": HandleResult(True)},
    )
    assert outcome == "ended"
    assert fake.handled == ["evidence_version.created", "connection.created"]


def test_a_failing_event_is_skipped_and_the_agent_carries_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    failure = ActivityError(
        "x",
        scheduled_event_id=1,
        started_event_id=2,
        identity="i",
        activity_type=HANDLE,
        activity_id="1",
        retry_state=None,
    )
    fake, _, stopped = _run(
        monkeypatch,
        ["evidence_version.created", "connection.created"],
        {"evidence_version.created": failure},
    )
    assert fake.handled == ["evidence_version.created", "connection.created"]
    assert stopped is _Idle


def test_it_continues_as_new_when_temporal_suggests_it(monkeypatch: pytest.MonkeyPatch) -> None:
    agent = EngagementAgent()
    fake = _Fake(agent, {})
    fake.suggested = True
    agent.event(AgentEvent("evidence_version.created", "1", {}))
    monkeypatch.setattr(module, "workflow", fake)
    with pytest.raises(_ContinuedAsNew):
        asyncio.run(agent.run(GIVEN))
    assert fake.handled == ["evidence_version.created"]


def test_the_history_is_bounded() -> None:
    assert MAX_HANDLED == 500


# --- v2: the daily tick (SPEC-027; TASK-051) -----------------------------------------------------


def _v2(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> _Fake:
    agent = EngagementAgent()
    fake = _Fake(agent, {})
    fake.v2 = True
    for n, name in enumerate(events):
        agent.event(AgentEvent(name, str(n), {}))
    monkeypatch.setattr(module, "workflow", fake)
    with pytest.raises(_Idle):
        asyncio.run(agent.run(GIVEN))
    return fake


def test_v2_an_idle_agent_ticks_when_its_time_comes(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _v2(monkeypatch, [])
    assert fake.handled == [TICK]
    # The delay came from the activity (recorded, so replay is deterministic), then again for the
    # next tick.
    assert fake.asked_tick == 2


def test_v2_events_are_handled_before_the_tick_and_keep_its_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _v2(monkeypatch, ["evidence_version.created", "inbox_file.added"])
    assert fake.handled == ["evidence_version.created", "inbox_file.added", TICK]
    assert fake.asked_tick == 2  # once before the first wait, once after the tick


def test_v1_never_asks_for_a_tick(monkeypatch: pytest.MonkeyPatch) -> None:
    fake, _, stopped = _run(monkeypatch, ["engagement.created"])
    assert fake.asked_tick == 0 and stopped is _Idle
