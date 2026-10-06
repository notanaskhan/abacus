"""AC-20: the worker's boot sequence, registries and SIGTERM handling (`abacus.worker.__main__`;
TASK-010 design section 6; ADR-017, ADR-104)."""

from __future__ import annotations

import asyncio
import os
import signal
from types import TracebackType
from typing import Self

import pytest

from abacus.worker import __main__ as worker_main


class _FakeWorker:
    def __init__(self) -> None:
        self.entered = False
        self.exited = False

    async def __aenter__(self) -> Self:
        self.entered = True
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.exited = True


async def test_ac20_the_worker_polls_until_sigterm_then_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake = _FakeWorker()

    async def build() -> _FakeWorker:
        return fake

    monkeypatch.setattr(worker_main, "build_worker", build)
    asyncio.get_running_loop().call_later(0.05, os.kill, os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert fake.entered
    assert fake.exited


async def test_ac20_sigint_also_stops_the_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeWorker()

    async def build() -> _FakeWorker:
        return fake

    monkeypatch.setattr(worker_main, "build_worker", build)
    asyncio.get_running_loop().call_later(0.05, os.kill, os.getpid(), signal.SIGINT)
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert fake.exited


async def test_ac20_a_failed_boot_check_stops_the_worker_before_it_polls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def unreachable() -> None:
        raise RuntimeError("database is down")

    monkeypatch.setattr(worker_main, "ping", unreachable)
    with pytest.raises(RuntimeError, match="database is down"):
        await worker_main.run()


def test_ac20_main_runs_the_worker_and_exits_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[bool] = []

    async def run() -> None:
        ran.append(True)

    monkeypatch.setattr(worker_main, "run", run)
    assert worker_main.main() == 0
    assert ran == [True]


def test_ac20_the_graceful_shutdown_window_is_a_minute() -> None:
    assert worker_main.GRACEFUL_SHUTDOWN.total_seconds() == 60


async def test_ac20_build_worker_checks_every_dependency_then_registers_the_module_registries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    built: dict[str, object] = {}

    async def ping() -> None:
        calls.append("ping")

    async def check_ready() -> None:
        calls.append("storage")

    async def client() -> str:
        calls.append("client")
        return "temporal-client"

    def worker(client: object, **kwargs: object) -> str:
        built["client"] = client
        built.update(kwargs)
        return "the-worker"

    monkeypatch.setattr(worker_main, "ping", ping)
    monkeypatch.setattr(worker_main, "key_service", lambda: calls.append("keys"))
    monkeypatch.setattr(worker_main, "payload_codec", lambda: calls.append("codec"))
    monkeypatch.setattr(worker_main, "check_ready", check_ready)
    monkeypatch.setattr(worker_main, "temporal_client", client)
    monkeypatch.setattr(worker_main, "Worker", worker)
    assert await worker_main.build_worker() == "the-worker"
    assert calls == ["ping", "keys", "codec", "storage", "client"]
    assert built["client"] == "temporal-client"
    assert built["workflows"] == list(worker_main.connections.WORKFLOWS)
    assert built["activities"] == list(worker_main.connections.ACTIVITIES)
    assert built["graceful_shutdown_timeout"] == worker_main.GRACEFUL_SHUTDOWN
