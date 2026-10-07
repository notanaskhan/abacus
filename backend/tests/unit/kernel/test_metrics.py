"""AC-15: the metrics foundation, the schedule-to-start interceptor and `otlp_url` (TASK-018
interface contract "Metrics" and revision 1; SPEC-003 AC-15; ADR-094).

The meter provider is global and set once per process, so these tests build a fresh provider with
their own in-memory reader (the module's remembered one is swapped out for the test) and read
instruments from that provider directly. Expectations come from the contract, not the
implementation.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from typing import ClassVar, cast

import pytest
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import Histogram as HistogramData
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    MetricExporter,
    MetricExportResult,
    MetricsData,
)
from opentelemetry.sdk.metrics.export import Sum as SumData
from temporalio.testing import ActivityEnvironment
from temporalio.worker import ActivityInboundInterceptor, ExecuteActivityInput

from abacus.kernel import metrics as metrics_module
from abacus.kernel import temporal_metrics
from abacus.kernel.config import settings
from abacus.kernel.dispatch import WorkClass, queue_for
from abacus.kernel.metrics import configure_metrics, in_memory_reader, shutdown_metrics
from abacus.kernel.telemetry import otlp_url
from abacus.kernel.temporal_metrics import SCHEDULE_TO_START, ScheduleToStartInterceptor

ALLOWED = {"work_class", "provider", "model", "reason", "outcome"}


@pytest.fixture
def fresh(monkeypatch: pytest.MonkeyPatch) -> Iterator[InMemoryMetricReader]:
    """A fresh provider with its own reader, never the global one."""
    monkeypatch.setattr(metrics_module, "_provider", None)
    monkeypatch.setattr(temporal_metrics, "_histogram", None)
    installed: list[object] = []
    monkeypatch.setattr("opentelemetry.metrics.set_meter_provider", installed.append)
    reader = InMemoryMetricReader()
    provider = configure_metrics("abacus-test", reader)

    def meter_of(name: str) -> Meter:
        return provider.get_meter(name)

    monkeypatch.setattr(temporal_metrics, "meter", meter_of, raising=True)
    yield reader
    provider.shutdown()


def _ignore(provider: object) -> None:
    return None


def _points(reader: InMemoryMetricReader, name: str) -> list[dict[str, object]]:
    """Every data point of one instrument: its attributes, count and sum or value."""
    data: MetricsData | None = reader.get_metrics_data()
    found: list[dict[str, object]] = []
    if data is None:
        return found
    for resource in data.resource_metrics:
        for scope in resource.scope_metrics:
            for metric in scope.metrics:
                if metric.name != name:
                    continue
                if isinstance(metric.data, HistogramData):
                    for h in metric.data.data_points:
                        point: dict[str, object] = {"attributes": dict(h.attributes or {})}
                        point.update(count=h.count, sum=h.sum)
                        found.append(point)
                elif isinstance(metric.data, SumData):
                    for n in metric.data.data_points:
                        total: dict[str, object] = {"attributes": dict(n.attributes or {})}
                        total.update(value=n.value)
                        found.append(total)
    return found


# --- the provider and its view -------------------------------------------------------------------


def test_ac15_configure_metrics_returns_one_provider_and_the_first_call_wins(
    fresh: InMemoryMetricReader,
) -> None:
    first = configure_metrics("abacus-test")
    assert isinstance(first, MeterProvider)
    assert configure_metrics("another-service") is first


def test_ac15_a_reader_after_the_provider_exists_is_refused(
    fresh: InMemoryMetricReader,
) -> None:
    with pytest.raises(RuntimeError):
        configure_metrics("abacus-test", InMemoryMetricReader())


def test_ac15_the_provider_is_installed_as_the_global_one_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(metrics_module, "_provider", None)
    installed: list[object] = []
    monkeypatch.setattr("opentelemetry.metrics.set_meter_provider", installed.append)
    provider = configure_metrics("abacus-test", InMemoryMetricReader())
    try:
        configure_metrics("abacus-test")
        assert installed == [provider]
    finally:
        provider.shutdown()


def test_ac15_the_view_drops_attributes_that_are_not_allowlisted(
    fresh: InMemoryMetricReader,
) -> None:
    provider = configure_metrics("abacus-test")
    counter = provider.get_meter("test").create_counter("abacus.test_counter")
    counter.add(
        1,
        {
            "work_class": "batch",
            "provider": "fake",
            "model": "small",
            "reason": "deferred",
            "outcome": "admitted",
            "tenant.id": "11111111-1111-1111-1111-111111111111",
            "engagement_id": "e",
            "client_name": "ACME Holdings",
            "amount": "1000.00",
        },
    )
    [point] = _points(fresh, "abacus.test_counter")
    assert point["attributes"] == {
        "work_class": "batch",
        "provider": "fake",
        "model": "small",
        "reason": "deferred",
        "outcome": "admitted",
    }


@pytest.mark.parametrize("name", sorted(ALLOWED))
def test_ac15_each_allowlisted_key_is_kept(fresh: InMemoryMetricReader, name: str) -> None:
    provider = configure_metrics("abacus-test")
    provider.get_meter("test").create_counter("abacus.one_key").add(1, {name: "v"})
    [point] = _points(fresh, "abacus.one_key")
    assert point["attributes"] == {name: "v"}


def test_ac15_the_tenant_is_not_an_allowed_attribute(fresh: InMemoryMetricReader) -> None:
    provider = configure_metrics("abacus-test")
    provider.get_meter("test").create_histogram("abacus.hist").record(
        1.0, {"tenant.id": "t", "work_class": "interactive"}
    )
    [point] = _points(fresh, "abacus.hist")
    assert point["attributes"] == {"work_class": "interactive"}


def test_ac15_a_metric_with_only_dropped_attributes_still_records_one_point(
    fresh: InMemoryMetricReader,
) -> None:
    provider = configure_metrics("abacus-test")
    counter = provider.get_meter("test").create_counter("abacus.dropped")
    counter.add(1, {"secret": "a"})
    counter.add(2, {"secret": "b"})
    [point] = _points(fresh, "abacus.dropped")
    assert point["attributes"] == {}
    assert point["value"] == 3


def test_ac15_exemplars_never_carry_the_dropped_attributes(fresh: InMemoryMetricReader) -> None:
    provider = configure_metrics("abacus-test")
    histogram = provider.get_meter("test").create_histogram("abacus.exemplars")
    histogram.record(1.0, {"tenant.id": "leaked-tenant", "work_class": "batch"})
    data = fresh.get_metrics_data()
    assert data is not None
    assert "leaked-tenant" not in repr(data)


# --- the in-memory reader and shutdown -----------------------------------------------------------


def test_ac15_the_in_memory_reader_is_one_reader_per_process() -> None:
    first = in_memory_reader()
    assert isinstance(first, InMemoryMetricReader)
    assert in_memory_reader() is first


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac15_the_in_memory_reader_is_refused_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr("abacus.kernel.metrics.settings", lambda: _Settings(environment, None))
    with pytest.raises(RuntimeError):
        in_memory_reader()


class _WatchedReader(InMemoryMetricReader):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        self.calls.append("flush")
        return super().force_flush(timeout_millis)

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: object) -> None:
        self.calls.append("shutdown")
        super().shutdown(timeout_millis)  # pyright: ignore[reportUnknownMemberType] -- otel's untyped kwargs


def test_ac15_shutdown_flushes_then_stops_the_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_module, "_provider", None)
    monkeypatch.setattr("opentelemetry.metrics.set_meter_provider", _ignore)
    reader = _WatchedReader()
    configure_metrics("abacus-test", reader)
    shutdown_metrics()
    assert reader.calls[0] == "flush"
    assert reader.calls[-1] == "shutdown"


def test_ac15_shutdown_without_a_provider_does_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(metrics_module, "_provider", None)
    shutdown_metrics()


# --- OTLP ----------------------------------------------------------------------------------------


class _Settings:
    release = None

    def __init__(self, environment: str, endpoint: str | None) -> None:
        self.environment = environment
        self.otlp_endpoint = endpoint


class _Recording(MetricExporter):
    instances: ClassVar[list[_Recording]] = []

    def __init__(self, **options: object) -> None:
        super().__init__(preferred_temporality={}, preferred_aggregation={})
        self.options = options
        _Recording.instances.append(self)

    def export(
        self, metrics_data: MetricsData, timeout_millis: float = 10_000, **kwargs: object
    ) -> MetricExportResult:
        return MetricExportResult.SUCCESS

    def force_flush(self, timeout_millis: float = 10_000) -> bool:
        return True

    def shutdown(self, timeout_millis: float = 30_000, **kwargs: object) -> None:
        return None


@pytest.fixture
def otlp(monkeypatch: pytest.MonkeyPatch) -> list[_Recording]:
    _Recording.instances.clear()
    monkeypatch.setattr(metrics_module, "_provider", None)
    monkeypatch.setattr("opentelemetry.metrics.set_meter_provider", _ignore)
    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.metric_exporter.OTLPMetricExporter", _Recording
    )
    return _Recording.instances


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("endpoint", ["http://collector.invalid:4318", "ftp://collector.invalid"])
def test_ac15_outside_local_and_test_a_non_https_otlp_endpoint_is_refused(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording], environment: str, endpoint: str
) -> None:
    monkeypatch.setattr("abacus.kernel.metrics.settings", lambda: _Settings(environment, endpoint))
    with pytest.raises(RuntimeError):
        configure_metrics("abacus-worker")
    assert otlp == []


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac15_an_https_endpoint_exports_to_the_metrics_path(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording], environment: str
) -> None:
    monkeypatch.setattr(
        "abacus.kernel.metrics.settings",
        lambda: _Settings(environment, "https://collector.invalid/"),
    )
    provider = configure_metrics("abacus-worker")
    try:
        [created] = otlp
        assert created.options["endpoint"] == "https://collector.invalid/v1/metrics"
    finally:
        provider.shutdown()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac15_http_is_fine_in_local_and_test(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording], environment: str
) -> None:
    monkeypatch.setattr(
        "abacus.kernel.metrics.settings",
        lambda: _Settings(environment, "http://localhost:4318"),
    )
    provider = configure_metrics("abacus-worker")
    try:
        [created] = otlp
        assert created.options["endpoint"] == "http://localhost:4318/v1/metrics"
    finally:
        provider.shutdown()


def test_ac15_without_an_endpoint_no_exporter_is_built(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording]
) -> None:
    monkeypatch.setattr("abacus.kernel.metrics.settings", lambda: _Settings("local", None))
    provider = configure_metrics("abacus-worker")
    provider.shutdown()
    assert otlp == []


# --- otlp_url ------------------------------------------------------------------------------------


def test_ac15_otlp_url_defaults_to_traces_and_trims_the_trailing_slash() -> None:
    assert otlp_url("http://localhost:4318/", "local") == "http://localhost:4318/v1/traces"
    assert otlp_url("http://localhost:4318", "test") == "http://localhost:4318/v1/traces"


def test_ac15_otlp_url_names_the_signal() -> None:
    assert otlp_url("https://c.invalid", "production", "metrics") == "https://c.invalid/v1/metrics"
    assert otlp_url("http://c.invalid", "local", "traces") == "http://c.invalid/v1/traces"


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("signal", ["traces", "metrics"])
def test_ac15_otlp_url_refuses_plain_http_outside_local_and_test(
    environment: str, signal: str
) -> None:
    with pytest.raises(RuntimeError):
        otlp_url("http://c.invalid", environment, signal)


# --- the schedule-to-start interceptor -----------------------------------------------------------

T0 = datetime(2026, 1, 1, tzinfo=UTC)


class _Terminal(ActivityInboundInterceptor):
    def __init__(self) -> None:  # the end of the chain
        self.ran = 0

    async def execute_activity(self, input: ExecuteActivityInput) -> object:
        self.ran += 1
        return "the-result"


async def _run(task_queue: str, waited: timedelta) -> tuple[object, _Terminal]:
    env = ActivityEnvironment()
    env.info = dataclasses.replace(
        env.info,
        task_queue=task_queue,
        current_attempt_scheduled_time=T0,
        started_time=T0 + waited,
    )
    terminal = _Terminal()
    inbound = ScheduleToStartInterceptor().intercept_activity(terminal)
    given = ExecuteActivityInput(fn=lambda: None, args=[], executor=None, headers={})
    return await env.run(inbound.execute_activity, given), terminal


def test_ac15_the_histogram_is_named_for_schedule_to_start() -> None:
    assert SCHEDULE_TO_START == "abacus.schedule_to_start"


@pytest.mark.parametrize("work_class", ["interactive", "time_sensitive", "background", "batch"])
async def test_ac15_the_wait_is_recorded_by_work_class(
    fresh: InMemoryMetricReader, work_class: str
) -> None:
    result, terminal = await _run(
        queue_for(cast("WorkClass", work_class)), timedelta(milliseconds=1500)
    )
    assert result == "the-result"  # the activity still runs, and its result passes through
    assert terminal.ran == 1
    [point] = _points(fresh, SCHEDULE_TO_START)
    assert point["attributes"] == {"work_class": work_class}
    assert point["count"] == 1
    assert point["sum"] == pytest.approx(1.5)


async def test_ac16_the_legacy_queue_is_reported_as_legacy(fresh: InMemoryMetricReader) -> None:
    await _run(settings().temporal_task_queue, timedelta(seconds=2))
    [point] = _points(fresh, SCHEDULE_TO_START)
    assert point["attributes"] == {"work_class": "legacy"}
    assert point["sum"] == pytest.approx(2.0)


async def test_ac15_any_other_queue_is_reported_as_legacy(fresh: InMemoryMetricReader) -> None:
    await _run("some-other-queue", timedelta(seconds=1))
    [point] = _points(fresh, SCHEDULE_TO_START)
    assert point["attributes"] == {"work_class": "legacy"}


async def test_ac15_a_negative_wait_is_recorded_as_zero(fresh: InMemoryMetricReader) -> None:
    await _run(queue_for("batch"), timedelta(seconds=-3))  # clock skew between server and worker
    [point] = _points(fresh, SCHEDULE_TO_START)
    assert point["sum"] == 0
    assert point["count"] == 1


async def test_ac15_each_activity_is_one_observation_per_class(
    fresh: InMemoryMetricReader,
) -> None:
    await _run(queue_for("interactive"), timedelta(seconds=1))
    await _run(queue_for("interactive"), timedelta(seconds=2))
    await _run(queue_for("batch"), timedelta(seconds=10))
    points = {
        cast("dict[str, str]", p["attributes"])["work_class"]: p
        for p in _points(fresh, SCHEDULE_TO_START)
    }
    assert points["interactive"]["count"] == 2
    assert points["interactive"]["sum"] == pytest.approx(3.0)
    assert points["batch"]["count"] == 1
    assert set(points) == {"interactive", "batch"}
