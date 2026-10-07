"""AC-1, AC-15, AC-16, AC-20: the worker's boot sequence, work-class pools, registries and
SIGTERM handling (`abacus.worker.__main__`; TASK-010 design section 6; TASK-018 interface contract
"Worker"; ADR-017, ADR-071, ADR-104)."""

from __future__ import annotations

import asyncio
import json
import os
import signal
import sys
from collections.abc import Callable, Sequence
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.dispatch import WORK_CLASSES, WorkClass, queue_for
from abacus.kernel.error_tracking import ReportingInterceptor
from abacus.kernel.temporal_metrics import ScheduleToStartInterceptor
from abacus.worker import __main__ as worker_main


class _FakeWorker:
    """A pool as the worker drives it: `run()` until `shutdown()`, or until it fails or ends."""

    def __init__(
        self,
        *,
        fail: BaseException | None = None,
        end_early: bool = False,
        log: list[str] | None = None,
    ) -> None:
        self.entered = False
        self.exited = False
        self.shutdowns = 0
        self.fail = fail
        self.end_early = end_early
        self.log = log if log is not None else []
        self._stop = asyncio.Event()

    async def run(self) -> None:
        self.entered = True
        try:
            if self.fail is not None:
                raise self.fail
            if not self.end_early:
                await self._stop.wait()
        finally:
            self.exited = True

    async def shutdown(self) -> None:
        self.shutdowns += 1
        self.log.append("shutdown")
        self._stop.set()


class _Relay:
    """Stands in for `run_relay`: records that it ran, until the stop event."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self.started = 0
        monkeypatch.setattr(worker_main, "run_relay", self._run)

    async def _run(self, publisher: object, stop: asyncio.Event) -> None:
        self.started += 1
        await stop.wait()


def _build(monkeypatch: pytest.MonkeyPatch, pools: Sequence[_FakeWorker]) -> list[tuple[str, ...]]:
    asked: list[tuple[str, ...]] = []

    async def build(classes: Sequence[str]) -> list[_FakeWorker]:
        asked.append(tuple(classes))
        return list(pools)

    monkeypatch.setattr(worker_main, "build_workers", build)
    return asked


def _signal(sig: signal.Signals = signal.SIGTERM, after: float = 0.05) -> None:
    asyncio.get_running_loop().call_later(after, os.kill, os.getpid(), sig)


async def test_ac20_the_worker_polls_until_sigterm_then_exits_cleanly(
    monkeypatch: pytest.MonkeyPatch, tracing_shutdowns: list[bool], metrics_shutdowns: list[bool]
) -> None:
    error_flushes: list[bool] = []
    monkeypatch.setattr(worker_main, "flush_errors", lambda: error_flushes.append(True))
    _Relay(monkeypatch)
    fake = _FakeWorker()
    _build(monkeypatch, [fake])
    _signal()
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert fake.entered
    assert fake.exited
    assert fake.shutdowns == 1
    assert tracing_shutdowns == [True]  # spans are flushed on the way out
    assert metrics_shutdowns == [True]  # and metrics
    assert error_flushes == [True]  # and buffered error reports


async def test_ac1_run_runs_and_shuts_down_every_pool_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Relay(monkeypatch)
    pools = [_FakeWorker(), _FakeWorker(), _FakeWorker()]
    asked = _build(monkeypatch, pools)
    _signal()
    await asyncio.wait_for(worker_main.run(("interactive", "batch")), timeout=10)
    assert asked == [("interactive", "batch")]
    assert all(p.entered and p.exited and p.shutdowns == 1 for p in pools)


async def test_ac1_run_serves_every_class_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    _Relay(monkeypatch)
    asked = _build(monkeypatch, [_FakeWorker()])
    _signal()
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert asked == [WORK_CLASSES]


async def test_ac20_telemetry_is_shut_down_only_after_every_pool_has_drained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    log: list[str] = []
    _Relay(monkeypatch)
    pools = [_FakeWorker(log=log), _FakeWorker(log=log)]
    _build(monkeypatch, pools)
    monkeypatch.setattr(worker_main, "shutdown_tracing", lambda: log.append("tracing"))
    monkeypatch.setattr(worker_main, "shutdown_metrics", lambda: log.append("metrics"))
    monkeypatch.setattr(worker_main, "flush_errors", lambda: log.append("errors"))
    _signal()
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert log == ["shutdown", "shutdown", "tracing", "metrics", "errors"]
    assert all(p.exited for p in pools)


@pytest.mark.parametrize("sig", [signal.SIGTERM, signal.SIGINT])
async def test_ac20_either_signal_stops_the_worker(
    monkeypatch: pytest.MonkeyPatch, sig: signal.Signals
) -> None:
    _Relay(monkeypatch)
    fake = _FakeWorker()
    _build(monkeypatch, [fake])
    _signal(sig)
    await asyncio.wait_for(worker_main.run(), timeout=10)
    assert fake.exited


async def test_ac1_a_pool_that_ends_before_the_signal_stops_the_process_with_an_error(
    monkeypatch: pytest.MonkeyPatch, tracing_shutdowns: list[bool]
) -> None:
    _Relay(monkeypatch)
    dead, alive = _FakeWorker(end_early=True), _FakeWorker()
    _build(monkeypatch, [dead, alive])
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(worker_main.run(), timeout=10)  # no signal is sent
    assert alive.shutdowns == 1  # the others are stopped too
    assert alive.exited
    assert tracing_shutdowns == [True]  # and telemetry is still flushed


async def test_ac1_a_pool_that_fails_before_the_signal_raises_its_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Relay(monkeypatch)
    broken, alive = _FakeWorker(fail=ValueError("pool crashed")), _FakeWorker()
    _build(monkeypatch, [alive, broken])
    with pytest.raises(ValueError, match="pool crashed"):
        await asyncio.wait_for(worker_main.run(), timeout=10)
    assert alive.exited


async def test_ac1_a_relay_that_ends_before_the_signal_is_an_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ends(publisher: object, stop: asyncio.Event) -> None:
        return None

    monkeypatch.setattr(worker_main, "run_relay", ends)
    fake = _FakeWorker()
    _build(monkeypatch, [fake])
    with pytest.raises(RuntimeError):
        await asyncio.wait_for(worker_main.run(), timeout=10)
    assert fake.shutdowns == 1
    assert fake.exited


@pytest.mark.parametrize(
    ("classes", "expected"),
    [
        (("batch",), 0),
        (("background", "time_sensitive"), 0),
        (("interactive",), 1),
        (("interactive", "batch"), 1),
    ],
)
async def test_ac1_the_relay_runs_only_in_a_process_serving_interactive(
    monkeypatch: pytest.MonkeyPatch, classes: tuple[WorkClass, ...], expected: int
) -> None:
    relay = _Relay(monkeypatch)
    _build(monkeypatch, [_FakeWorker()])
    _signal()
    await asyncio.wait_for(worker_main.run(classes), timeout=10)
    assert relay.started == expected


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
        assert [type(i) for i in interceptors] == [
            ReportingInterceptor,
            ScheduleToStartInterceptor,
        ]


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
    expected = {"interactive": 10, "time_sensitive": 10, "background": 5, "batch": 2}
    for kwargs, work_class in zip(boot.built, WORK_CLASSES, strict=False):
        assert kwargs["max_concurrent_activities"] == expected[work_class]
        assert kwargs["max_concurrent_workflow_tasks"] == expected[work_class]


# TASK-018b: the slot caps and maximum wait are required fields of each class.
SLOT_FIELDS = {
    "firm_cap": 5,
    "engagement_cap": 2,
    "class_capacity": 10,
    "max_wait_seconds": 60,
    "admission_reserve_pct": 0,
}


async def test_ac1_limits_come_from_the_settings_by_class(
    boot: _Boot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv(
        "ABACUS_WORK_CLASSES",
        json.dumps(
            {
                "interactive": {"max_activities": 7, "max_workflow_tasks": 17, **SLOT_FIELDS},
                "time_sensitive": {"max_activities": 6, "max_workflow_tasks": 16, **SLOT_FIELDS},
                "background": {"max_activities": 1, "max_workflow_tasks": 11, **SLOT_FIELDS},
                "batch": {"max_activities": 2, "max_workflow_tasks": 12, **SLOT_FIELDS},
            }
        ),
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
    assert boot.queues() == [queue_for("time_sensitive"), queue_for("batch")]


async def test_ac16_the_legacy_queue_is_served_only_beside_the_interactive_pool(
    boot: _Boot,
) -> None:
    await worker_main.build_workers(("interactive", "batch"))
    assert boot.queues() == [
        queue_for("interactive"),
        queue_for("batch"),
        settings().temporal_task_queue,
    ]


@pytest.mark.parametrize(
    "classes",
    [("batch",), ("background",), ("time_sensitive",), ("time_sensitive", "background", "batch")],
)
async def test_ac16_a_process_without_the_interactive_pool_does_not_serve_the_legacy_queue(
    boot: _Boot, classes: tuple[WorkClass, ...]
) -> None:
    await worker_main.build_workers(classes)
    assert boot.queues() == [queue_for(c) for c in classes]


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

    def recorder(kind: str) -> Callable[[str], None]:
        def record(service: str) -> None:
            configured.append((kind, service))

        return record

    monkeypatch.setattr(worker_main, "configure_tracing", recorder("t"))
    monkeypatch.setattr(worker_main, "configure_metrics", recorder("m"))
    monkeypatch.setattr(worker_main, "configure_error_tracking", recorder("e"))
    await worker_main.build_workers()
    assert sorted(configured) == [
        ("e", "abacus-worker"),
        ("m", "abacus-worker"),
        ("t", "abacus-worker"),
    ]


def test_ac1_the_default_pool_sizes_are_set_per_class() -> None:
    expected = {"interactive": 10, "time_sensitive": 10, "background": 5, "batch": 2}
    assert {c: v.max_activities for c, v in settings().work_classes.items()} == expected
    assert {c: v.max_workflow_tasks for c, v in settings().work_classes.items()} == expected


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
