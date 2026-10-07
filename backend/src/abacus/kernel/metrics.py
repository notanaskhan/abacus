"""Metrics (ADR-094; SPEC-003 AC-15; TASK-018 design §7).

    configure_metrics("abacus-worker")                 # once, at process start
    meter(__name__).create_histogram("abacus.schedule_to_start", unit="s")

Like spans, metrics carry identifiers and outcomes only: every instrument passes through a view
that keeps only the allowlisted attribute keys (`_ATTRIBUTES`), so a stray attribute never leaves
the process. Export is over OTLP when `otlp_endpoint` is set; otherwise metrics stay in process
(tests read them through `test_reader()`).

`ScheduleToStartInterceptor` records how long each activity waited on its task queue, by work
class: the latency each worker pool's sizing is judged by (ADR-071, ADR-094).
"""

from __future__ import annotations

from typing import Final

from opentelemetry import metrics
from opentelemetry.metrics import Histogram, Meter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource
from temporalio import activity
from temporalio.worker import (
    ActivityInboundInterceptor,
    ExecuteActivityInput,
    Interceptor,
)

from abacus.kernel.config import settings
from abacus.kernel.dispatch import WORK_CLASSES, queue_for
from abacus.kernel.telemetry import otlp_url

# The only attribute keys any metric may carry (identifiers and outcomes, never client data).
_ATTRIBUTES: Final = frozenset(
    {"work_class", "provider", "model", "reason", "outcome", "tenant.id"}
)
SCHEDULE_TO_START: Final = "abacus.schedule_to_start"
_provider: MeterProvider | None = None
_test_reader: InMemoryMetricReader | None = None


def _views() -> list[View]:
    return [View(instrument_name="*", attribute_keys=set(_ATTRIBUTES))]


def configure_metrics(service: str, reader: MetricReader | None = None) -> MeterProvider:
    """Install the process's meter provider (idempotent: the first call wins). A test passes its
    reader on the first call (`test_reader`)."""
    global _provider
    if _provider is None:
        s = settings()
        readers: list[MetricReader] = [] if reader is None else [reader]
        if s.otlp_endpoint is not None:
            from opentelemetry.exporter.otlp.proto.http.metric_exporter import (  # export only
                OTLPMetricExporter,
            )

            exporter = OTLPMetricExporter(
                endpoint=otlp_url(s.otlp_endpoint, s.environment, "metrics")
            )
            readers.append(PeriodicExportingMetricReader(exporter))
        attributes = {"service.name": service, "deployment.environment": s.environment}
        if s.release is not None:
            attributes["service.version"] = s.release
        _provider = MeterProvider(
            metric_readers=readers, resource=Resource.create(attributes), views=_views()
        )
        metrics.set_meter_provider(_provider)
    return _provider


def meter(name: str) -> Meter:
    return metrics.get_meter(name)


def shutdown_metrics() -> None:
    """Export what is buffered and stop (process shutdown)."""
    if _provider is not None:
        _provider.force_flush()
        _provider.shutdown()


def test_reader() -> InMemoryMetricReader:
    """The test process's in-memory reader, attached to the provider when it is first built."""
    global _test_reader
    if settings().environment not in ("local", "test"):
        raise RuntimeError("the in-memory metric reader is for tests only")
    if _test_reader is None:
        _test_reader = InMemoryMetricReader()
        configure_metrics("abacus-test", _test_reader)
    return _test_reader


def work_class_of_queue(task_queue: str) -> str:
    """The work class a task queue serves, or `legacy` for the old single queue."""
    for work_class in WORK_CLASSES:
        if task_queue == queue_for(work_class):
            return work_class
    return "legacy"


_histogram: Histogram | None = None


def _schedule_to_start() -> Histogram:
    global _histogram
    if _histogram is None:
        _histogram = meter(__name__).create_histogram(
            SCHEDULE_TO_START,
            unit="s",
            description="Time an activity waited on its task queue before a worker started it",
        )
    return _histogram


class _ScheduleToStartInbound(ActivityInboundInterceptor):
    async def execute_activity(self, input: ExecuteActivityInput) -> object:
        info = activity.info()
        waited = (info.started_time - info.current_attempt_scheduled_time).total_seconds()
        _schedule_to_start().record(
            max(waited, 0.0), {"work_class": work_class_of_queue(info.task_queue)}
        )
        return await super().execute_activity(input)


class ScheduleToStartInterceptor(Interceptor):
    """Worker interceptor: record each activity's schedule-to-start latency by work class."""

    def intercept_activity(self, next: ActivityInboundInterceptor) -> ActivityInboundInterceptor:
        return _ScheduleToStartInbound(next)
