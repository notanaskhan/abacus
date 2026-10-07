"""AC-1, AC-15, AC-16, AC-20: the worker's boot sequence, work-class pools, registries and
SIGTERM handling (`abacus.worker.__main__`; TASK-010 design section 6; TASK-018 interface contract
"Worker"; ADR-017, ADR-071, ADR-104)."""

from __future__ import annotations

import asyncio
import os
import signal
import sys
from collections.abc import Sequence
from types import TracebackType
from typing import Self, cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.dispatch import WORK_CLASSES, queue_for
from abacus.kernel.error_tracking import ReportingInterceptor
from abacus.kernel.metrics import ScheduleToStartInterceptor
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
    monkeypatch: pytest.MonkeyPatch, tracing_shutdowns: list[bool], metrics_shutdowns: list[bool]
) -> None:
    error_flushes: list[bool] = []
    monkeypatch.setattr(worker_main, "flush_errors", lambda: error_flushes.append(True))
    fake = _FakeWorker()

    async def build(classes: Sequence[str]) -> list[_FakeWorker]:
        return [fake]

    monkeypatch.setattr(worker_main, "build_workers", build)
    asyncio.get_running_loop().call_later(0.05, os.kill, os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert fake.entered
    assert fake.exited
    assert tracing_shutdowns == [True]  # spans are flushed on the way out
    assert metrics_shutdowns == [True]  # and metrics
    assert error_flushes == [True]  # and buffered error reports


async def test_ac1_run_enters_every_worker_and_passes_the_classes_to_build_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pools = [_FakeWorker(), _FakeWorker(), _FakeWorker()]
    asked: list[tuple[str, ...]] = []

    async def build(classes: Sequence[str]) -> list[_FakeWorker]:
        asked.append(tuple(classes))
        return pools

    monkeypatch.setattr(worker_main, "build_workers", build)
    asyncio.get_running_loop().call_later(0.05, os.kill, os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(worker_main.run(("background", "batch")), timeout=10)
    assert asked == [("background", "batch")]
    assert all(p.entered and p.exited for p in pools)


async def test_ac1_run_serves_every_class_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[tuple[str, ...]] = []

    async def build(classes: Sequence[str]) -> list[_FakeWorker]:
        asked.append(tuple(classes))
        return [_FakeWorker()]

    monkeypatch.setattr(worker_main, "build_workers", build)
    asyncio.get_running_loop().call_later(0.05, os.kill, os.getpid(), signal.SIGTERM)
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert asked == [WORK_CLASSES]


async def test_ac20_sigint_also_stops_the_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = _FakeWorker()

    async def build(classes: Sequence[str]) -> list[_FakeWorker]:
        return [fake]

    monkeypatch.setattr(worker_main, "build_workers", build)
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


def test_ac1_main_runs_the_worker_with_every_class_by_default_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran: list[tuple[str, ...]] = []

    async def run(classes: Sequence[str]) -> None:
        ran.append(tuple(classes))

    monkeypatch.setattr(worker_main, "run", run)
    monkeypatch.setattr(sys, "argv", ["abacus.worker"])
    assert worker_main.main() == 0
    assert ran == [WORK_CLASSES]


def test_ac1_main_serves_the_classes_it_is_given(monkeypatch: pytest.MonkeyPatch) -> None:
    ran: list[tuple[str, ...]] = []

    async def run(classes: Sequence[str]) -> None:
        ran.append(tuple(classes))

    monkeypatch.setattr(worker_main, "run", run)
    assert worker_main.main(["--classes", "batch,interactive"]) == 0
    assert ran == [("interactive", "batch")]


def test_ac1_main_without_argv_reads_the_process_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    ran: list[tuple[str, ...]] = []

    async def run(classes: Sequence[str]) -> None:
        ran.append(tuple(classes))

    monkeypatch.setattr(worker_main, "run", run)
    monkeypatch.setattr(sys, "argv", ["abacus.worker", "--classes", "background"])
    assert worker_main.main() == 0
    assert ran == [("background",)]


def test_ac20_the_graceful_shutdown_window_is_a_minute() -> None:
    assert worker_main.GRACEFUL_SHUTDOWN.total_seconds() == 60


# --- build_workers -------------------------------------------------------------------------------


class _Boot:
    """Stubs every boot dependency of `build_workers`, recording calls and the Workers built."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.calls: list[str] = []
        self.built: list[dict[str, object]] = []
        self.clients: list[object] = []
        calls = self.calls

        async def ping() -> None:
            calls.append("ping")

        async def ping_relay() -> None:
            calls.append("ping_relay")

        async def check_ready() -> None:
            calls.append("storage")

        async def client() -> str:
            calls.append("client")
            return "temporal-client"

        def worker(client: object, **kwargs: object) -> dict[str, object]:
            self.clients.append(client)
            self.built.append(kwargs)
            return kwargs

        monkeypatch.setattr(worker_main, "ping", ping)
        monkeypatch.setattr(worker_main, "ping_relay", ping_relay)
        monkeypatch.setattr(worker_main, "key_service", lambda: calls.append("keys"))
        monkeypatch.setattr(worker_main, "payload_codec", lambda: calls.append("codec"))
        monkeypatch.setattr(worker_main, "check_ready", check_ready)
        monkeypatch.setattr(worker_main, "temporal_client", client)
        monkeypatch.setattr(worker_main, "Worker", worker)

    def queues(self) -> list[object]:
        return [w["task_queue"] for w in self.built]


@pytest.fixture
def boot(monkeypatch: pytest.MonkeyPatch) -> _Boot:
    return _Boot(monkeypatch)


async def test_ac1_build_workers_checks_every_dependency_in_order_then_builds_the_workers(
    boot: _Boot,
) -> None:
    workers = await worker_main.build_workers()
    assert boot.calls == ["ping", "ping_relay", "keys", "codec", "storage", "client"]
    assert len(workers) == len(boot.built) == len(WORK_CLASSES) + 1
    assert set(boot.clients) == {"temporal-client"}


async def test_ac1_every_worker_registers_every_modules_workflows_and_activities(
    boot: _Boot,
) -> None:
    await worker_main.build_workers()
    for kwargs in boot.built:
        assert kwargs["workflows"] == [
            *worker_main.connections.WORKFLOWS,
            *worker_main.agents.WORKFLOWS,
        ]
        assert kwargs["activities"] == [
            *worker_main.connections.ACTIVITIES,
            *worker_main.agents.ACTIVITIES,
        ]
        assert kwargs["graceful_shutdown_timeout"] == worker_main.GRACEFUL_SHUTDOWN


async def test_ac15_every_worker_has_the_reporting_and_schedule_to_start_interceptors(
    boot: _Boot,
) -> None:
    await worker_main.build_workers()
    for kwargs in boot.built:
        interceptors = cast("list[object]", kwargs["interceptors"])
        assert [type(i) for i in interceptors] == [ReportingInterceptor, ScheduleToStartInterceptor]


async def test_ac1_one_worker_per_class_polls_its_queue_then_the_legacy_queue(
    boot: _Boot,
) -> None:
    await worker_main.build_workers()
    assert boot.queues() == [*(queue_for(c) for c in WORK_CLASSES), settings().temporal_task_queue]
    assert boot.queues()[:4] == [
        "abacus-interactive",
        "abacus-time-sensitive",
        "abacus-background",
        "abacus-batch",
    ]


async def test_ac1_each_class_has_its_own_concurrency_limits(boot: _Boot) -> None:
    await worker_main.build_workers()
    expected = {"interactive": 50, "time_sensitive": 50, "background": 20, "batch": 10}
    for kwargs, work_class in zip(boot.built, WORK_CLASSES, strict=False):
        assert kwargs["max_concurrent_activities"] == expected[work_class]
        assert kwargs["max_concurrent_workflow_tasks"] == expected[work_class]


async def test_ac1_limits_come_from_the_settings_by_class(
    boot: _Boot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "ABACUS_WORKER_MAX_ACTIVITIES",
        '{"interactive": 7, "time_sensitive": 6, "background": 1, "batch": 2}',
    )
    monkeypatch.setenv(
        "ABACUS_WORKER_MAX_WORKFLOW_TASKS",
        '{"interactive": 17, "time_sensitive": 16, "background": 11, "batch": 12}',
    )
    settings.cache_clear()
    try:
        await worker_main.build_workers()
    finally:
        monkeypatch.undo()
        settings.cache_clear()
    # the legacy queue drains with the interactive limits
    assert [w["max_concurrent_activities"] for w in boot.built] == [7, 6, 1, 2, 7]
    assert [w["max_concurrent_workflow_tasks"] for w in boot.built] == [17, 16, 11, 12, 17]


async def test_ac1_a_process_serves_only_the_classes_it_is_given(boot: _Boot) -> None:
    await worker_main.build_workers(("time_sensitive", "batch"))
    assert boot.queues() == [
        queue_for("time_sensitive"),
        queue_for("batch"),
        settings().temporal_task_queue,
    ]


async def test_ac16_the_legacy_queue_is_not_served_when_switched_off(
    boot: _Boot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_SERVE_LEGACY_QUEUE", "false")
    settings.cache_clear()
    try:
        await worker_main.build_workers()
    finally:
        monkeypatch.undo()
        settings.cache_clear()
    assert boot.queues() == [queue_for(c) for c in WORK_CLASSES]


async def test_ac16_the_legacy_queue_is_the_configured_base_queue(
    boot: _Boot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("ABACUS_TEMPORAL_TASK_QUEUE", "custom-base")
    settings.cache_clear()
    try:
        await worker_main.build_workers()
    finally:
        monkeypatch.undo()
        settings.cache_clear()
    assert boot.queues() == [
        "custom-base-interactive",
        "custom-base-time-sensitive",
        "custom-base-background",
        "custom-base-batch",
        "custom-base",
    ]


def test_ac16_the_legacy_queue_is_served_by_default() -> None:
    assert settings().serve_legacy_queue is True


async def test_ac15_build_workers_configures_tracing_metrics_and_error_tracking(
    boot: _Boot, monkeypatch: pytest.MonkeyPatch
) -> None:
    configured: list[tuple[str, str]] = []
    monkeypatch.setattr(worker_main, "configure_tracing", lambda s: configured.append(("t", s)))
    monkeypatch.setattr(worker_main, "configure_metrics", lambda s: configured.append(("m", s)))
    monkeypatch.setattr(
        worker_main, "configure_error_tracking", lambda s: configured.append(("e", s))
    )
    await worker_main.build_workers()
    assert sorted(configured) == [
        ("e", "abacus-worker"),
        ("m", "abacus-worker"),
        ("t", "abacus-worker"),
    ]


def test_ac1_the_default_pool_sizes_are_set_per_class() -> None:
    expected = {"interactive": 50, "time_sensitive": 50, "background": 20, "batch": 10}
    assert settings().worker_max_activities == expected
    assert settings().worker_max_workflow_tasks == expected


# --- classes_from --------------------------------------------------------------------------------


def test_ac1_classes_default_to_all_four_in_order() -> None:
    assert worker_main.classes_from([]) == WORK_CLASSES
    assert WORK_CLASSES == ("interactive", "time_sensitive", "background", "batch")


def test_ac1_classes_parse_a_comma_separated_list() -> None:
    assert worker_main.classes_from(["--classes", "interactive,time_sensitive"]) == (
        "interactive",
        "time_sensitive",
    )


def test_ac1_classes_are_returned_in_the_canonical_order_without_duplicates() -> None:
    assert worker_main.classes_from(["--classes", "batch,interactive,batch,interactive"]) == (
        "interactive",
        "batch",
    )


@pytest.mark.parametrize("raw", ["", ",", "nonsense", "interactive,nonsense", "time-sensitive"])
def test_ac1_an_unknown_or_empty_class_list_exits_with_the_parser_error(raw: str) -> None:
    with pytest.raises(SystemExit) as raised:
        worker_main.classes_from(["--classes", raw])
    assert raised.value.code == 2
