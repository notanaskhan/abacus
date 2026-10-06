"""AC-14, AC-20: the routing publisher and the relay loop against the real outbox (TASK-011b
interface contract, "Relay (kernel)"; TASK-011 Q4).

Events are emitted through the real unit of work. The shared database may hold other tests'
unpublished rows, so every assertion is about the events a test emitted itself. Intervals are
small and each test bounds its own waiting. Expectations come from the contract, not the
implementation.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from itertools import pairwise
from typing import Annotated, ClassVar, cast

import pytest

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, configure_relay_engine
from abacus.kernel.uow import DomainEvent, Target, uow
from abacus.kernel.uow import relay as relay_module
from abacus.kernel.uow.relay import (
    Handler,
    OutboxEvent,
    Publisher,
    RelayResult,
    RoutingPublisher,
    relay_once,
    run_relay,
)

from .support import Migrated, Seeder

KNOWN = f"relay_screening.known_{uuid.uuid4().hex[:8]}"
OTHER = f"relay_screening.other_{uuid.uuid4().hex[:8]}"


class Known(DomainEvent):
    event_type: ClassVar[str] = KNOWN
    n: Annotated[int, classified("public")]


class Other(DomainEvent):
    event_type: ClassVar[str] = OTHER
    n: Annotated[int, classified("public")]


@pytest.fixture(autouse=True)
def relay_engine_for_this_loop(migrated_db: Migrated) -> None:
    configure_relay_engine(migrated_db.relay_url)


async def _emit(event: DomainEvent, tenant_id: uuid.UUID | None = None) -> uuid.UUID:
    ctx = TenantContext(tenant_id or uuid.uuid4(), "human", "u-relay")
    async with uow(ctx) as tx:
        tx.record("probe.pinged", target=Target("probe", "1"))
        tx.emit(event)
    return event.event_id


async def _row(seed: Seeder, event_id: uuid.UUID) -> dict[str, object]:
    [row] = await seed.rows(
        "SELECT published_at, attempts, last_error, next_attempt_at FROM outbox WHERE id = $1",
        event_id,
    )
    return dict(row)


async def _until(condition: Callable[[], Awaitable[bool]], timeout: float = 15.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if await condition():
            return
        await asyncio.sleep(0.02)
    raise AssertionError("condition not met in time")


class Recorder:
    def __init__(self) -> None:
        self.seen: list[tuple[str, uuid.UUID]] = []

    def handler(self, name: str, *, fail: Exception | None = None) -> Handler:
        async def handle(event: OutboxEvent) -> None:
            self.seen.append((name, event.event_id))
            if fail is not None:
                raise fail

        return handle

    def names_for(self, event_id: uuid.UUID) -> list[str]:
        return [name for name, found in self.seen if found == event_id]


class Collecting:
    """A publisher that remembers the ids it was given (all events, any test's)."""

    def __init__(self) -> None:
        self.ids: list[uuid.UUID] = []

    async def publish(self, event: OutboxEvent) -> None:
        self.ids.append(event.event_id)


# --- RoutingPublisher through the relay ----------------------------------------------------------


async def test_ac20_the_relay_runs_every_handler_of_the_event_type_in_order(seed: Seeder) -> None:
    recorder = Recorder()
    publisher = RoutingPublisher(
        {
            KNOWN: [recorder.handler("first"), recorder.handler("second")],
            OTHER: [recorder.handler("other")],
        }
    )
    known, other = await _emit(Known(n=1)), await _emit(Other(n=2))
    await relay_once(publisher, batch=500)
    assert recorder.names_for(known) == ["first", "second"]
    assert recorder.names_for(other) == ["other"]
    assert (await _row(seed, known))["published_at"] is not None
    assert (await _row(seed, other))["published_at"] is not None


async def test_ac20_an_event_with_no_handlers_is_published_without_error(seed: Seeder) -> None:
    recorder = Recorder()
    publisher = RoutingPublisher({OTHER: [recorder.handler("other")]})
    unknown = await _emit(Known(n=1))
    result = await relay_once(publisher, batch=500)
    assert result.failed == 0
    row = await _row(seed, unknown)
    assert row["published_at"] is not None
    assert (row["attempts"], row["last_error"]) == (0, None)
    assert recorder.seen == []


async def test_ac20_a_handler_error_backs_the_event_off_and_it_is_not_published(
    seed: Seeder,
) -> None:
    recorder = Recorder()
    publisher = RoutingPublisher(
        {
            KNOWN: [
                recorder.handler("first"),
                recorder.handler("broken", fail=ValueError("client says SECRET-MARKER")),
                recorder.handler("never"),
            ]
        }
    )
    failing = await _emit(Known(n=1))
    result = await relay_once(publisher, batch=500)
    assert result.failed >= 1
    assert recorder.names_for(failing) == ["first", "broken"]
    row = await _row(seed, failing)
    assert row["published_at"] is None
    assert row["attempts"] == 1
    assert row["last_error"] == "ValueError"  # the class name only
    assert cast(datetime, row["next_attempt_at"]) > datetime.now(UTC)
    # Backed off: the next pass leaves it alone.
    await relay_once(publisher, batch=500)
    assert recorder.names_for(failing) == ["first", "broken"]
    assert (await _row(seed, failing))["attempts"] == 1


async def test_ac20_a_handler_error_does_not_block_other_events(seed: Seeder) -> None:
    recorder = Recorder()
    publisher = RoutingPublisher(
        {
            KNOWN: [recorder.handler("broken", fail=RuntimeError("down"))],
            OTHER: [recorder.handler("ok")],
        }
    )
    failing, fine = await _emit(Known(n=1)), await _emit(Other(n=2))
    await relay_once(publisher, batch=500)
    assert (await _row(seed, failing))["published_at"] is None
    assert (await _row(seed, fine))["published_at"] is not None


# --- run_relay -----------------------------------------------------------------------------------


async def test_ac20_run_relay_returns_at_once_when_already_stopped() -> None:
    stop = asyncio.Event()
    stop.set()
    started = time.monotonic()
    await asyncio.wait_for(run_relay(Collecting(), stop, interval=30), timeout=5)
    assert time.monotonic() - started < 2


async def test_ac20_run_relay_stops_promptly_during_its_idle_wait() -> None:
    stop = asyncio.Event()
    task = asyncio.create_task(run_relay(Collecting(), stop, interval=30))
    await asyncio.sleep(0.3)  # one pass done, now idling for 30 seconds
    assert not task.done()
    started = time.monotonic()
    stop.set()
    await asyncio.wait_for(task, timeout=3)
    assert time.monotonic() - started < 2


async def test_ac20_run_relay_publishes_events_as_they_arrive(seed: Seeder) -> None:
    recorder = Recorder()
    publisher = RoutingPublisher({KNOWN: [recorder.handler("seen")]})
    stop = asyncio.Event()
    task = asyncio.create_task(run_relay(publisher, stop, interval=0.05))
    try:
        first = await _emit(Known(n=1))
        await _until(lambda: _published(seed, first))
        await asyncio.sleep(0.2)
        second = await _emit(Known(n=2))
        await _until(lambda: _published(seed, second))
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=5)
    assert recorder.names_for(first) == ["seen"]
    assert recorder.names_for(second) == ["seen"]


async def _published(seed: Seeder, event_id: uuid.UUID) -> bool:
    return (await _row(seed, event_id))["published_at"] is not None


async def test_ac20_run_relay_idles_between_passes_when_quiet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    passes: list[float] = []

    async def counting(publisher: Publisher, batch: int = 25) -> RelayResult:
        passes.append(time.monotonic())
        return await relay_once(publisher, batch)

    monkeypatch.setattr(relay_module, "relay_once", counting)
    stop = asyncio.Event()
    task = asyncio.create_task(run_relay(Collecting(), stop, interval=0.2, batch=500))
    await asyncio.sleep(1.0)
    stop.set()
    await asyncio.wait_for(task, timeout=3)
    # About one pass per interval: not a busy loop, not stalled.
    assert 3 <= len(passes) <= 8
    gaps = [b - a for a, b in pairwise(passes)]
    assert all(gap >= 0.15 for gap in gaps)


async def test_ac20_run_relay_does_not_wait_while_passes_are_full(seed: Seeder) -> None:
    recorder = Recorder()
    publisher = RoutingPublisher({KNOWN: [recorder.handler("seen")]})
    ids = [await _emit(Known(n=n)) for n in range(6)]
    stop = asyncio.Event()
    started = time.monotonic()
    # batch=2 and a 30 second idle: only back-to-back full passes can finish within the test.
    task = asyncio.create_task(run_relay(publisher, stop, interval=30, batch=2))
    try:

        async def all_published() -> bool:
            return all([await _published(seed, i) for i in ids])

        await _until(all_published, timeout=10)
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=5)
    assert time.monotonic() - started < 10


async def test_ac20_run_relay_survives_a_failing_pass_and_logs_only_the_class(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    recorder = Recorder()
    publisher = RoutingPublisher({KNOWN: [recorder.handler("seen")]})
    calls = {"n": 0}

    async def flaky(publisher: Publisher, batch: int = 25) -> RelayResult:
        calls["n"] += 1
        if calls["n"] <= 2:
            raise ConnectionError("database away: SECRET-MARKER")
        return await relay_once(publisher, batch)

    monkeypatch.setattr(relay_module, "relay_once", flaky)
    event_id = await _emit(Known(n=1))
    stop = asyncio.Event()
    task = asyncio.create_task(run_relay(publisher, stop, interval=0.05))
    try:
        await _until(lambda: _published(seed, event_id))
    finally:
        stop.set()
        await asyncio.wait_for(task, timeout=5)
    assert calls["n"] >= 3
    assert not task.cancelled()
    output = capsys.readouterr().out
    assert "SECRET-MARKER" not in output
    records = [json.loads(line) for line in output.splitlines() if line.startswith("{")]
    failed = [r for r in records if r.get("event") == "outbox.relay_pass_failed"]
    assert len(failed) == 2
    assert all("ConnectionError" in json.dumps(r) for r in failed)
