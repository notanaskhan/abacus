"""AC-20: the tracing helpers (TASK-013 interface contract, "Telemetry"; ADR-022).

The tracer provider is global and set once per process, so these tests add an in-memory exporter
to it, clear it per test, and look only at spans of the trace they started. Provider setup is
checked on a fresh provider (the module's remembered one is swapped out for the test).
"""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from typing import ClassVar

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from abacus.kernel.config import settings
from abacus.kernel.telemetry import (
    TRACEPARENT,
    configure_tracing,
    continue_trace,
    current_span_id,
    current_trace_id,
    current_traceparent,
    tracer,
)
from abacus.kernel.telemetry import test_exporter as shared_exporter

REMOTE_TRACE = "a1" * 16
REMOTE_SPAN = "b2" * 8
REMOTE = f"00-{REMOTE_TRACE}-{REMOTE_SPAN}-01"


@pytest.fixture(scope="module")
def exporter() -> InMemorySpanExporter:
    return shared_exporter()


@pytest.fixture(autouse=True)
def clean(exporter: InMemorySpanExporter, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in ("ABACUS_RELEASE", "ABACUS_OTLP_ENDPOINT"):
        monkeypatch.delenv(name, raising=False)
    settings.cache_clear()
    exporter.clear()
    yield
    exporter.clear()
    settings.cache_clear()


def _span(exporter: InMemorySpanExporter, name: str) -> ReadableSpan:
    [found] = [s for s in exporter.get_finished_spans() if s.name == name]
    return found


# --- ids -----------------------------------------------------------------------------------------


def test_ac20_ids_are_none_outside_a_span() -> None:
    assert current_trace_id() is None
    assert current_span_id() is None
    assert current_traceparent() is None


def test_ac20_trace_id_is_32_hex_and_span_id_is_16_inside_a_span(
    exporter: InMemorySpanExporter,
) -> None:
    with tracer("t").start_as_current_span("ids"):
        trace_id, span_id = current_trace_id(), current_span_id()
    assert trace_id is not None
    assert span_id is not None
    assert re.fullmatch(r"[0-9a-f]{32}", trace_id)
    assert re.fullmatch(r"[0-9a-f]{16}", span_id)
    span = _span(exporter, "ids")
    assert span.context is not None
    assert format(span.context.trace_id, "032x") == trace_id
    assert format(span.context.span_id, "016x") == span_id


def test_ac20_a_child_span_shares_the_trace_and_has_its_own_span_id() -> None:
    with tracer("t").start_as_current_span("outer"):
        outer = (current_trace_id(), current_span_id())
        with tracer("t").start_as_current_span("inner"):
            inner = (current_trace_id(), current_span_id())
        assert (current_trace_id(), current_span_id()) == outer
    assert inner[0] == outer[0]
    assert inner[1] != outer[1]


def test_ac20_separate_root_spans_have_different_trace_ids() -> None:
    with tracer("t").start_as_current_span("one"):
        first = current_trace_id()
    with tracer("t").start_as_current_span("two"):
        second = current_trace_id()
    assert first != second


def test_ac20_ids_are_none_again_after_the_span_ends() -> None:
    with tracer("t").start_as_current_span("done"):
        pass
    assert current_trace_id() is None
    assert current_span_id() is None


# --- traceparent ---------------------------------------------------------------------------------


def test_ac20_traceparent_is_w3c_and_names_the_current_span() -> None:
    with tracer("t").start_as_current_span("tp"):
        header = current_traceparent()
        trace_id, span_id = current_trace_id(), current_span_id()
    assert header is not None
    assert TRACEPARENT.fullmatch(header)
    version, found_trace, found_span, flags = header.split("-")
    assert (version, found_trace, found_span) == ("00", trace_id, span_id)
    assert re.fullmatch(r"[0-9a-f]{2}", flags)


@pytest.mark.parametrize(
    "value",
    [
        REMOTE,
        f"00-{'0' * 31}1-{'0' * 15}1-00",
        f"00-{'f' * 32}-{'f' * 16}-ff",
    ],
)
def test_ac20_the_traceparent_pattern_accepts_w3c_headers(value: str) -> None:
    assert TRACEPARENT.fullmatch(value)


@pytest.mark.parametrize(
    "value",
    [
        "",
        "garbage",
        f"01-{REMOTE_TRACE}-{REMOTE_SPAN}-01",
        f"00-{REMOTE_TRACE.upper()}-{REMOTE_SPAN}-01",
        f"00-{REMOTE_TRACE[:-1]}-{REMOTE_SPAN}-01",
        f"00-{REMOTE_TRACE}-{REMOTE_SPAN[:-1]}-01",
        f"00-{REMOTE_TRACE}-{REMOTE_SPAN}-1",
        f"00-{REMOTE_TRACE}-{REMOTE_SPAN}-01-extra",
        f" 00-{REMOTE_TRACE}-{REMOTE_SPAN}-01",
    ],
)
def test_ac20_the_traceparent_pattern_rejects_other_strings(value: str) -> None:
    assert TRACEPARENT.fullmatch(value) is None


# --- continue_trace ------------------------------------------------------------------------------


def test_ac20_continue_trace_makes_new_spans_children_of_the_given_span(
    exporter: InMemorySpanExporter,
) -> None:
    with continue_trace(REMOTE):
        assert current_trace_id() == REMOTE_TRACE
        with tracer("t").start_as_current_span("continued"):
            assert current_trace_id() == REMOTE_TRACE
            assert current_span_id() != REMOTE_SPAN
    span = _span(exporter, "continued")
    assert span.context is not None
    assert format(span.context.trace_id, "032x") == REMOTE_TRACE
    assert span.parent is not None
    assert format(span.parent.span_id, "016x") == REMOTE_SPAN


def test_ac20_continue_trace_restores_the_outer_context_on_exit() -> None:
    assert current_trace_id() is None
    with continue_trace(REMOTE):
        pass
    assert current_trace_id() is None
    with tracer("t").start_as_current_span("outer"):
        outer = current_trace_id()
        with continue_trace(REMOTE):
            assert current_trace_id() == REMOTE_TRACE
        assert current_trace_id() == outer


def test_ac20_continue_trace_restores_the_context_when_the_block_raises() -> None:
    with pytest.raises(RuntimeError), continue_trace(REMOTE):
        raise RuntimeError("inside")
    assert current_trace_id() is None


def test_ac20_a_traceparent_round_trips_through_continue_trace() -> None:
    with tracer("t").start_as_current_span("source"):
        header = current_traceparent()
        source = current_trace_id()
    assert header is not None
    with continue_trace(header), tracer("t").start_as_current_span("far"):
        assert current_trace_id() == source


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        "garbage",
        f"00-{REMOTE_TRACE.upper()}-{REMOTE_SPAN}-01",
        f"00-{REMOTE_TRACE}-{REMOTE_SPAN}",
    ],
)
def test_ac20_continue_trace_is_a_no_op_for_none_or_a_malformed_value(
    value: str | None,
) -> None:
    with continue_trace(value):
        assert current_trace_id() is None
        with tracer("t").start_as_current_span("fresh"):
            fresh = current_trace_id()
    assert fresh is not None
    assert fresh != REMOTE_TRACE


def test_ac20_a_malformed_value_leaves_an_open_span_in_charge() -> None:
    with tracer("t").start_as_current_span("outer"):
        outer = (current_trace_id(), current_span_id())
        with continue_trace("not a traceparent"):
            assert (current_trace_id(), current_span_id()) == outer
        with continue_trace(None):
            assert (current_trace_id(), current_span_id()) == outer


# --- configure_tracing ---------------------------------------------------------------------------


def test_ac20_configure_tracing_keeps_one_provider_and_a_later_exporter_joins_it() -> None:
    first = configure_tracing("abacus-test")
    later = InMemorySpanExporter()
    second = configure_tracing("another-service", later)
    assert second is first
    with tracer("t").start_as_current_span("both"):
        pass
    assert [s.name for s in later.get_finished_spans()] == ["both"]


@pytest.fixture
def fresh_provider(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Forget the process's provider so `configure_tracing` builds a new one (the global OTel
    provider stays as it was: it can only be set once)."""
    monkeypatch.setattr("abacus.kernel.telemetry._provider", None)
    yield


def _resource(provider: TracerProvider) -> dict[str, object]:
    return dict(provider.resource.attributes)


@pytest.mark.usefixtures("fresh_provider")
def test_ac20_the_resource_names_the_service_and_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABACUS_ENVIRONMENT", "test")
    settings.cache_clear()
    attributes = _resource(configure_tracing("abacus-worker"))
    assert attributes["service.name"] == "abacus-worker"
    assert attributes["deployment.environment"] == "test"
    assert "service.version" not in attributes


@pytest.mark.usefixtures("fresh_provider")
def test_ac20_the_resource_carries_the_version_when_release_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABACUS_RELEASE", "2026.10.07-abc123")
    settings.cache_clear()
    attributes = _resource(configure_tracing("abacus-api"))
    assert attributes["service.version"] == "2026.10.07-abc123"
    assert attributes["service.name"] == "abacus-api"


class _Recording(SpanExporter):
    instances: ClassVar[list[_Recording]] = []

    def __init__(self, **options: object) -> None:
        self.options = options
        self.exported: list[ReadableSpan] = []
        _Recording.instances.append(self)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.exported.extend(spans)
        return SpanExportResult.SUCCESS


@pytest.mark.usefixtures("fresh_provider")
def test_ac20_nothing_is_exported_unless_an_endpoint_or_exporter_is_given(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _Recording.instances.clear()
    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter", _Recording
    )
    provider = configure_tracing("abacus-api")
    with provider.get_tracer("t").start_as_current_span("nowhere"):
        pass
    provider.force_flush()
    assert _Recording.instances == []


@pytest.mark.usefixtures("fresh_provider")
def test_ac20_an_otlp_endpoint_adds_an_otlp_exporter(monkeypatch: pytest.MonkeyPatch) -> None:
    _Recording.instances.clear()
    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter", _Recording
    )
    monkeypatch.setenv("ABACUS_OTLP_ENDPOINT", "http://collector.invalid:4318")
    settings.cache_clear()
    provider = configure_tracing("abacus-api")
    try:
        [created] = _Recording.instances
        assert str(created.options["endpoint"]).startswith("http://collector.invalid:4318")
        with provider.get_tracer("t").start_as_current_span("out"):
            pass
        provider.force_flush()
        assert [s.name for s in created.exported] == ["out"]
    finally:
        provider.shutdown()


@pytest.mark.usefixtures("fresh_provider")
def test_ac20_an_explicit_exporter_is_added_to_a_new_provider() -> None:
    memory = InMemorySpanExporter()
    provider = configure_tracing("abacus-test", memory)
    with provider.get_tracer("t").start_as_current_span("direct", attributes={"custom": "x"}):
        pass
    assert [s.name for s in memory.get_finished_spans()] == ["direct"]
