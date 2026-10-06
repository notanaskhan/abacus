"""AC-14, AC-20: the worker runs the relay and routes events to module subscriptions (TASK-011b
interface contract, "Worker"; TASK-011 Q4)."""

from __future__ import annotations

import asyncio
import os
import signal
import uuid
from types import TracebackType
from typing import Self

import pytest

from abacus.kernel.uow.relay import Handler, OutboxEvent, Publisher, RoutingPublisher
from abacus.modules.agents.screenings import EVIDENCE_VERSION_CREATED
from abacus.worker import __main__ as worker_main


class _Worker:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    async def __aenter__(self) -> Self:
        self.log.append("worker entered")
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.log.append("worker exited")


def _event(event_type: str) -> OutboxEvent:
    return OutboxEvent(uuid.uuid4(), uuid.uuid4(), event_type, {})


def test_ac14_the_worker_hosts_connections_and_agents() -> None:
    assert (worker_main.connections, worker_main.agents) == worker_main.MODULES
    assert worker_main.SUBSCRIBERS == (worker_main.agents.SUBSCRIPTIONS,)


def test_ac14_the_publisher_routes_evidence_version_created_to_start_screening() -> None:
    built = worker_main.publisher()
    assert isinstance(built, RoutingPublisher)
    assert list(built.handlers) == [EVIDENCE_VERSION_CREATED]
    assert list(built.handlers[EVIDENCE_VERSION_CREATED]) == [worker_main.agents.start_screening]


async def test_ac14_the_publisher_runs_every_subscribed_handler_and_ignores_other_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[tuple[str, str]] = []

    def recorder(name: str) -> Handler:
        async def handle(event: OutboxEvent) -> None:
            seen.append((name, event.event_type))

        return handle

    monkeypatch.setattr(
        worker_main,
        "SUBSCRIBERS",
        (
            {"a.happened": recorder("one")},
            {"a.happened": recorder("two"), "b.happened": recorder("three")},
        ),
    )
    built = worker_main.publisher()
    await built.publish(_event("a.happened"))
    await built.publish(_event("b.happened"))
    await built.publish(_event("c.happened"))
    assert seen == [("one", "a.happened"), ("two", "a.happened"), ("three", "b.happened")]


async def test_ac20_a_failed_relay_database_check_stops_the_boot_after_ping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def ping() -> None:
        calls.append("ping")

    async def ping_relay() -> None:
        calls.append("ping_relay")
        raise RuntimeError("relay role cannot connect")

    monkeypatch.setattr(worker_main, "ping", ping)
    monkeypatch.setattr(worker_main, "ping_relay", ping_relay)
    monkeypatch.setattr(worker_main, "key_service", lambda: calls.append("keys"))
    with pytest.raises(RuntimeError, match="relay role cannot connect"):
        await worker_main.build_worker()
    assert calls == ["ping", "ping_relay"]


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
async def test_ac20_run_hosts_the_relay_inside_the_worker_until_the_signal(
    monkeypatch: pytest.MonkeyPatch, sig: signal.Signals
) -> None:
    log: list[str] = []
    seen: dict[str, object] = {}

    async def build() -> _Worker:
        return _Worker(log)

    async def relay(publisher: Publisher, stop: asyncio.Event) -> None:
        seen["publisher"] = publisher
        seen["stop"] = stop
        log.append("relay started")
        await stop.wait()
        # Finishing takes a moment: the worker must not exit before the relay has.
        await asyncio.sleep(0.05)
        log.append("relay finished")

    monkeypatch.setattr(worker_main, "build_worker", build)
    monkeypatch.setattr(worker_main, "run_relay", relay)
    asyncio.get_running_loop().call_later(0.1, os.kill, os.getpid(), sig)
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert log == ["worker entered", "relay started", "relay finished", "worker exited"]
    assert isinstance(seen["publisher"], RoutingPublisher)
    stop = seen["stop"]
    assert isinstance(stop, asyncio.Event)
    assert stop.is_set()
