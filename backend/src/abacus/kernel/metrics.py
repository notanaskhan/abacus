"""Metrics (ADR-094; SPEC-003 AC-15; TASK-018 design §7).

    configure_metrics("abacus-worker")                 # once, at process start
    meter(__name__).create_histogram("abacus.schedule_to_start", unit="s")

Like spans, metrics carry identifiers and outcomes only: every instrument passes through a view
that keeps only the allowlisted attribute keys (`_ATTRIBUTES`), so a stray attribute never leaves
the process. Export is over OTLP when `otlp_endpoint` is set; otherwise metrics stay in process
(tests read them through `in_memory_reader()`). Attribute values pass the TIN backstop as they
are recorded (`ScrubbingMeter`, ADR-167): an unmasked SSN, ITIN or EIN form becomes its mask.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final, cast

from opentelemetry import metrics
from opentelemetry.context import Context
from opentelemetry.metrics import Counter, Histogram, Meter
from opentelemetry.sdk.metrics import AlwaysOffExemplarFilter, MeterProvider
from opentelemetry.sdk.metrics.export import (
    InMemoryMetricReader,
    MetricReader,
    PeriodicExportingMetricReader,
)
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource
from opentelemetry.util.types import Attributes, AttributeValue

from abacus.kernel.config import settings
from abacus.kernel.telemetry import otlp_url
from abacus.kernel.tin_patterns import scrub_tins

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


def _masked(attributes: Attributes) -> Attributes:
    if not attributes:
        return attributes
    out: dict[str, object] = {}
    for key, value in attributes.items():
        if isinstance(value, str):
            out[key] = scrub_tins(value)
        elif isinstance(value, Sequence) and not isinstance(value, bytes):
            out[key] = [scrub_tins(v) if isinstance(v, str) else v for v in value]
        else:
            out[key] = value
    return cast(Mapping[str, AttributeValue], out)


class _Counter(Counter):
    def __init__(self, inner: Counter, name: str, unit: str, description: str) -> None:
        super().__init__(name, unit, description)
        self._inner = inner

    def add(
        self, amount: float, attributes: Attributes = None, context: Context | None = None
    ) -> None:
        self._inner.add(amount, _masked(attributes), context)


class _Histogram(Histogram):
    def __init__(self, inner: Histogram, name: str, unit: str, description: str) -> None:
        super().__init__(name, unit, description)
        self._inner = inner

    def record(
        self, amount: float, attributes: Attributes = None, context: Context | None = None
    ) -> None:
        self._inner.record(amount, _masked(attributes), context)


class ScrubbingMeter:
    """The meter product code gets: counters and histograms whose attribute values pass the TIN
    backstop before the SDK sees them (the view above still drops every key not allowlisted)."""

    def __init__(self, inner: Meter) -> None:
        self._inner = inner

    def create_counter(self, name: str, unit: str = "", description: str = "") -> Counter:
        inner = self._inner.create_counter(name, unit, description)
        return _Counter(inner, name, unit, description)

    def create_histogram(
        self,
        name: str,
        unit: str = "",
        description: str = "",
        *,
        explicit_bucket_boundaries_advisory: Sequence[float] | None = None,
    ) -> Histogram:
        inner = self._inner.create_histogram(
            name,
            unit,
            description,
            explicit_bucket_boundaries_advisory=explicit_bucket_boundaries_advisory,
        )
        return _Histogram(inner, name, unit, description)


def meter(name: str) -> ScrubbingMeter:
    return ScrubbingMeter(metrics.get_meter(name))


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
