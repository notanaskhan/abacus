"""S33 partials round (A-07-T32; DEC-3138): a composed letter names the run that drafted it (the
run opens first, a refused draft ends it failed), and a burst of checklist changes starts one
60-second readiness run per work item."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace
from typing import Any, cast

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.assurance import agent_capabilities as caps
from abacus.modules.assurance import completion_projector as cp
from abacus.modules.assurance import completion_readiness_workflow as crw
from abacus.modules.assurance import rep_letters
from abacus.modules.identity.api import AuthContext

RUN = uuid.uuid4()
WI = uuid.uuid4()


def _ctx() -> AuthContext:
    user = uuid.uuid4()
    return cast(
        AuthContext,
        SimpleNamespace(
            tenant=TenantContext(uuid.uuid4(), "human", str(user)),
            tenant_id=uuid.uuid4(),
            user_id=user,
        ),
    )


def _wire(monkeypatch: pytest.MonkeyPatch, events: list[str]) -> None:
    def record(action: str, **_k: object) -> None:
        events.append(action)

    @asynccontextmanager
    async def unit(_t: object) -> AsyncGenerator[object]:
        yield SimpleNamespace(record=record)

    async def item(*_a: object) -> object:
        return SimpleNamespace(engagement_id=uuid.uuid4())

    async def begin(*_a: object) -> uuid.UUID:
        events.append("begin")
        return RUN

    async def finish(*_a: object) -> None:
        events.append("finish")

    async def fail(_tx: object, _run: uuid.UUID, code: str) -> None:
        events.append(f"fail:{code}")

    monkeypatch.setattr(caps, "uow", unit)
    monkeypatch.setattr(caps, "assurance_item", item)
    monkeypatch.setattr(caps, "begin_code_run", begin)
    monkeypatch.setattr(caps, "finish_code_run", finish)
    monkeypatch.setattr(caps, "fail_code_run", fail)


async def test_the_draft_names_the_run_that_composed_it(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    _wire(monkeypatch, events)
    seen: dict[str, Any] = {}  # Any: the keyword arguments under test

    async def start(_ctx: object, _wi: uuid.UUID, **kw: object) -> object:
        seen.update(kw)
        events.append("draft")
        return SimpleNamespace(version_no=2)

    monkeypatch.setattr(rep_letters, "start_letter", start)
    assert await caps.letter_compose(_ctx(), WI) == RUN
    assert seen == {"drafted_by_run_id": RUN}
    assert events == ["begin", "agent_run.started", "draft", "finish"]


async def test_a_refused_draft_ends_the_run_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    _wire(monkeypatch, events)

    async def refuse(*_a: object, **_k: object) -> object:
        raise rep_letters.NoTemplate(facts={"family": "representation_letter"})

    monkeypatch.setattr(rep_letters, "start_letter", refuse)
    with pytest.raises(rep_letters.NoTemplate):
        await caps.letter_compose(_ctx(), WI)
    assert events[-2:] == [f"fail:{rep_letters.NoTemplate.code}", "agent_run.failed"]
    assert "finish" not in events


async def test_a_changed_item_starts_one_waiting_readiness_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started: list[dict[str, Any]] = []  # Any: the dispatch's keyword arguments

    async def dispatch(workflow: type, arg: object, **kw: object) -> None:
        started.append({"workflow": workflow, "arg": arg, **kw})

    async def live(*_a: object) -> bool:
        return True

    async def changed(*_a: object, **_k: object) -> int:
        return 2

    monkeypatch.setattr("abacus.kernel.dispatch.dispatch", dispatch)
    monkeypatch.setattr(cp, "projector_live", live)
    monkeypatch.setattr(cp, "store_items", changed)
    tenant = uuid.uuid4()
    event = SimpleNamespace(
        tenant_id=tenant, event_id=uuid.uuid4(), payload={"work_item_id": str(WI)}
    )
    await cp.on_completion_event(event)  # type: ignore[arg-type]  # an outbox event double
    (only,) = started
    assert only["workflow"] is crw.CompletionReadinessWorkflow
    assert only["id"] == f"completion_readiness:{tenant}:{WI}"
    assert only["id_conflict_policy"].name == "USE_EXISTING"
    assert crw.DEBOUNCE.total_seconds() == 60


async def test_no_change_starts_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    started: list[object] = []

    async def dispatch(*a: object, **_k: object) -> None:
        started.append(a)

    async def live(*_a: object) -> bool:
        return True

    async def unchanged(*_a: object, **_k: object) -> int:
        return 0

    monkeypatch.setattr("abacus.kernel.dispatch.dispatch", dispatch)
    monkeypatch.setattr(cp, "projector_live", live)
    monkeypatch.setattr(cp, "store_items", unchanged)
    event = SimpleNamespace(
        tenant_id=uuid.uuid4(), event_id=uuid.uuid4(), payload={"work_item_id": str(WI)}
    )
    await cp.on_completion_event(event)  # type: ignore[arg-type]  # an outbox event double
    assert started == []
