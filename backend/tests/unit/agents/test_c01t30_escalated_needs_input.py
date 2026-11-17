"""C-01-T30 rest (S48): an escalated capability run waits on its person, so it emits
`agent_run.needs_input` (C16 `run_needs_input` to the initiator); other ends emit nothing."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from abacus.modules.agents import capability_runs as cr
from abacus.modules.agents.events import RunNeedsInput


class _Tx:
    session = object()

    def __init__(self, sink: list[object]) -> None:
        self.sink = sink

    def record(self, action: str, **_: object) -> None:
        self.sink.append(action)

    def emit(self, event: object) -> None:
        self.sink.append(event)


@pytest.mark.parametrize("status", ["escalated", "succeeded", "failed"])
async def test_only_an_escalation_asks_the_person(
    monkeypatch: pytest.MonkeyPatch, status: str
) -> None:
    sink: list[object] = []

    async def finished(*_: object, **__: object) -> bool:
        return True

    @asynccontextmanager
    async def uow(_t: object) -> AsyncGenerator[_Tx]:
        yield _Tx(sink)

    monkeypatch.setattr(cr, "finish_run", finished)
    monkeypatch.setattr(cr, "uow", uow)
    person, run, engagement = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    agent = SimpleNamespace(
        tenant=object(),
        agent_run_id=run,
        engagement_id=engagement,
        initiator=SimpleNamespace(user_id=person),
    )
    await cr.end_capability_run(agent, status=status)  # type: ignore[arg-type] -- the fields read
    events = [e for e in sink if isinstance(e, RunNeedsInput)]
    if status == "escalated":
        assert [(e.run_id, e.engagement_id, e.user_id) for e in events] == [
            (run, engagement, person)
        ]
    else:
        assert events == []
    assert f"agent_run.{status}" in sink
