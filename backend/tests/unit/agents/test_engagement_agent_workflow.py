"""SPEC-027 (TASK-050; ADR-062): the engagement agent's workflow loop, offline. Temporal's
`workflow` module is replaced by a fake: signals queue events, each runs one activity in order,
a failing event is skipped, the agent continues as new to bound its history, and ends when the
engagement is archived."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from types import SimpleNamespace

import pytest
from temporalio.exceptions import ActivityError

from abacus.modules.agents import engagement_agent_workflow as module
from abacus.modules.agents.engagement_agent_workflow import HANDLE, MAX_HANDLED, EngagementAgent
from abacus.modules.agents.workflow_types import AgentEvent, AgentInput, HandleInput, HandleResult

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

    async def wait_condition(self, ready: Callable[[], bool]) -> None:
        if not ready():
            raise _Idle

    async def execute_activity(self, name: str, given: HandleInput, **_: object) -> HandleResult:
        assert name == HANDLE
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
