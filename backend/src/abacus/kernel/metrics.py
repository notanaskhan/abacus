"""Metrics (ADR-094; SPEC-003 AC-15; TASK-018 design §7).

    configure_metrics("abacus-worker")                 # once, at process start
    meter(__name__).create_histogram("abacus.schedule_to_start", unit="s")

Like spans, metrics carry identifiers and outcomes only: every instrument passes through a view
that keeps only the allowlisted attribute keys (`_ATTRIBUTES`), so a stray attribute never leaves
the process. Export is over OTLP when `otlp_endpoint` is set; otherwise metrics stay in process
(tests read them through `in_memory_reader()`).
"""

from __future__ import annotations

from typing import Final

from opentelemetry import metrics
from opentelemetry.metrics import Meter
from opentelemetry.sdk.metrics import AlwaysOffExemplarFilter, MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource

from abacus.kernel.config import settings
from abacus.kernel.telemetry import otlp_url

# The only attribute keys any metric may carry (identifiers and outcomes, never client data).
# A metric that needs the tenant gets its own view, per instrument (018b's slots metrics).
_ATTRIBUTES: Final = frozenset({"work_class", "provider", "model", "reason", "outcome"})
_provider: MeterProvider | None = None
_test_reader: InMemoryMetricReader | None = None


def _views() -> list[View]:
    return [View(instrument_name="*", attribute_keys=set(_ATTRIBUTES))]


def configure_metrics(service: str, reader: MetricReader | None = None) -> MeterProvider:
    """Install the process's meter provider (idempotent: the first call wins). A test passes its
    reader on the first call (`in_memory_reader`)."""
    global _provider
    if _provider is not None and reader is not None:
        raise RuntimeError(
            "metrics are already configured: a reader must come with the first call"
        )
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
            metric_readers=readers,
            resource=Resource.create(attributes),
            views=_views(),
            # Exemplars would keep the attributes the view drops: never record them.
            exemplar_filter=AlwaysOffExemplarFilter(),
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


def in_memory_reader() -> InMemoryMetricReader:
    """The test process's in-memory reader, attached to the provider when it is first built."""
    global _test_reader
    if settings().environment not in ("local", "test"):
        raise RuntimeError("the in-memory metric reader is for tests only")
    if _test_reader is None:
        _test_reader = InMemoryMetricReader()
        configure_metrics("abacus-test", _test_reader)
    return _test_reader
