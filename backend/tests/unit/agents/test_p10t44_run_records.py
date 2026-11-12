"""P-10-T44 (TASK-7302; SPEC-647 AC-RR2, AC-RR3; DEC-4302): frozen trace exports, pure parts.

The database path (`agent_run_traces`, the prune definer, a run 90 days old exported after its
`run_events` went) is `tests/integration/agent_tests/test_p10t44_run_records.py`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from abacus.modules.agents import trace_records

pytestmark = pytest.mark.asyncio


def _patch(
    monkeypatch: pytest.MonkeyPatch, found: object, newest: object
) -> list[dict[str, object]]:
    written: list[dict[str, object]] = []

    async def fingerprint(_s: object, _r: uuid.UUID) -> object:
        return found

    class _Result:
        def first(self) -> object:
            return newest

    @asynccontextmanager
    async def session(_t: object) -> AsyncGenerator[object]:
        async def execute(_q: object, _p: object = None) -> _Result:
            return _Result()

        yield SimpleNamespace(execute=execute)

    @asynccontextmanager
    async def unit(_t: object) -> AsyncGenerator[object]:
        async def execute(_q: object, params: dict[str, object]) -> None:
            written.append(params)

        yield SimpleNamespace(
            session=SimpleNamespace(execute=execute), record=lambda *a, **k: None
        )

    monkeypatch.setattr(trace_records, "source_fingerprint", fingerprint)
    monkeypatch.setattr(trace_records, "tenant_session", session)
    monkeypatch.setattr(trace_records, "uow", unit)
    return written


async def _body(
    monkeypatch: pytest.MonkeyPatch, found: object, newest: object, built: bytes
) -> tuple[bytes, list[dict[str, object]]]:
    written = _patch(monkeypatch, found, newest)

    async def build() -> bytes:
        return built

    tenant = SimpleNamespace(tenant_id=uuid.uuid4())
    body = await trace_records.frozen_body(tenant, uuid.uuid4(), "content", "trace-v1", build)  # type: ignore[arg-type]  # a test double
    return body, written


async def test_acrr3_an_ended_run_whose_rows_held_still_answers_its_frozen_bytes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eng = uuid.uuid4()
    frozen = SimpleNamespace(version=1, body='{"rows":[1,2]}', source_sha256="f" * 64)
    body, written = await _body(monkeypatch, ("f" * 64, "approved", eng), frozen, b'{"rows":[9]}')
    assert body == b'{"rows":[1,2]}' and written == []


async def test_a_run_whose_rows_moved_freezes_a_new_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    eng = uuid.uuid4()
    frozen = SimpleNamespace(version=1, body='{"rows":[1]}', source_sha256="f" * 64)
    body, written = await _body(
        monkeypatch, ("e" * 64, "approved", eng), frozen, b'{"rows":[1,2]}'
    )
    assert body == b'{"rows":[1,2]}'
    assert written[0]["version"] == 2 and written[0]["source"] == "e" * 64


async def test_an_open_run_is_built_and_never_frozen(monkeypatch: pytest.MonkeyPatch) -> None:
    body, written = await _body(monkeypatch, ("a" * 64, "running", uuid.uuid4()), None, b"{}")
    assert body == b"{}" and written == []


def test_the_prune_runs_daily_as_the_one_actor_the_definer_admits() -> None:
    (schedule,) = trace_records.PRUNE_SCHEDULES
    assert schedule.id == "run_events_prune:platform" and schedule.every.days == 1
    assert trace_records.PRUNE_ACTOR == "agents.run_events_prune"
