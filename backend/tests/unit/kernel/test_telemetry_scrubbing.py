"""AC-20: the scrubbing span exporter and the test exporter (TASK-013 contract revision 1,
"Scrubbing exporter", "Test exporter", "OTLP"; ADR-022, ADR-031).

Every exporter sits behind `ScrubbingExporter`: only allowlisted attributes leave the process,
`exception` events never do, other events keep four numeric/outcome fields, and an error status
is cut to a class name. Spans here come from a throwaway provider, so nothing is global.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import ClassVar

import pytest
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ParentBased
from opentelemetry.trace import Status, StatusCode
from opentelemetry.util.types import AttributeValue

from abacus.kernel.config import settings
from abacus.kernel.telemetry import ScrubbingExporter, configure_tracing, scrubbed, tracer
from abacus.kernel.telemetry import test_exporter as shared_exporter

MARKER = "SPAN-MARKER-6204"
ALLOWED: dict[str, AttributeValue] = {
    "http.route": "/v1/engagements/{engagement_id}",
    "http.request.method": "GET",
    "http.method": "GET",
    "http.status_code": 200,
    "http.response.status_code": 200,
    "temporalWorkflowID": "screening:t:v",
    "temporalRunID": "run-1",
    "temporalActivityID": "1",
    "temporalActivityType": "screen",
    "temporalUpdateID": "u-1",
    "ai.prompt": "evidence.screen@v0",
    "ai.anything_else": "kept",
    "outbox.event_type": "x.y",
    "tenant.id": "t-1",
}
DROPPED: dict[str, AttributeValue] = {
    "http.url": f"https://api.example.invalid/v1/clients/{MARKER}?q={MARKER}",
    "http.target": f"/v1/clients/{MARKER}?q={MARKER}",
    "url.full": f"https://x.invalid/{MARKER}",
    "url.query": f"q={MARKER}",
    "http.user_agent": f"agent/{MARKER}",
    "user_agent.original": MARKER,
    "net.peer.ip": "10.0.0.9",
    "client.address": "10.0.0.9",
    "http.request.header.authorization": MARKER,
    "http.request.body": MARKER,
    "db.statement": f"SELECT {MARKER}",
    "custom": MARKER,
    "aix.near_miss": MARKER,
    "tenants.near_miss": MARKER,
}


def _export(
    attributes: dict[str, AttributeValue] | None = None,
    *,
    status: Status | None = None,
    events: list[tuple[str, dict[str, AttributeValue]]] | None = None,
    exception: BaseException | None = None,
) -> ReadableSpan:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(ScrubbingExporter(memory)))
    with provider.get_tracer("t").start_span("work", attributes=attributes) as span:
        for name, event_attributes in events or []:
            span.add_event(name, event_attributes)
        if exception is not None:
            span.record_exception(exception)
        if status is not None:
            span.set_status(status)
    [exported] = memory.get_finished_spans()
    return exported


def test_ac20_allowlisted_attributes_are_exported() -> None:
    assert dict(_export(ALLOWED).attributes or {}) == ALLOWED


def test_ac20_every_other_attribute_is_dropped() -> None:
    exported = _export({**ALLOWED, **DROPPED})
    assert dict(exported.attributes or {}) == ALLOWED
    assert MARKER not in json.dumps(dict(exported.attributes or {}))


def test_ac20_the_span_keeps_its_identity_name_and_parent() -> None:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(ScrubbingExporter(memory)))
    t = provider.get_tracer("t")
    with t.start_as_current_span("outer"), t.start_as_current_span("inner"):
        pass
    inner, outer = memory.get_finished_spans()
    assert (inner.name, outer.name) == ("inner", "outer")
    assert inner.parent is not None
    assert outer.context is not None
    assert inner.parent.span_id == outer.context.span_id


def test_ac20_exception_events_are_never_exported() -> None:
    exported = _export(exception=ValueError(f"cell {MARKER}"))
    assert [e.name for e in exported.events] == []
    assert MARKER not in repr(exported.events)


def test_ac20_other_events_keep_only_outcome_tokens_and_cost() -> None:
    exported = _export(
        events=[
            (
                "ai.attempt",
                {
                    "outcome": "ok",
                    "input_tokens": 12,
                    "output_tokens": 3,
                    "cost_usd": "0.000100",
                    "prompt": MARKER,
                    "text": MARKER,
                },
            )
        ]
    )
    [event] = exported.events
    assert event.name == "ai.attempt"
    assert dict(event.attributes or {}) == {
        "outcome": "ok",
        "input_tokens": 12,
        "output_tokens": 3,
        "cost_usd": "0.000100",
    }


def test_ac20_an_exception_event_is_dropped_but_its_siblings_stay() -> None:
    exported = _export(events=[("ai.attempt", {"outcome": "ok"})], exception=RuntimeError(MARKER))
    assert [e.name for e in exported.events] == ["ai.attempt"]


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        (f"ValueError: cell {MARKER}", "ValueError"),
        ("ApplicationError: boom: more", "ApplicationError"),
        ("temporalio.exceptions.ApplicationError: x", "temporalio.exceptions.ApplicationError"),
        ("RuntimeError", "RuntimeError"),
        (f"not a class name {MARKER}", "error"),
        (f"{MARKER} with spaces: tail", "error"),
        ("", "error"),
    ],
)
def test_ac20_an_error_status_description_is_cut_to_a_class_name(
    description: str, expected: str
) -> None:
    exported = _export(status=Status(StatusCode.ERROR, description))
    assert exported.status.status_code is StatusCode.ERROR
    assert exported.status.description == expected
    assert MARKER not in (exported.status.description or "")


def test_ac20_an_ok_or_unset_status_is_left_alone() -> None:
    assert _export().status.status_code is StatusCode.UNSET
    assert _export(status=Status(StatusCode.OK)).status.status_code is StatusCode.OK


def test_ac20_scrubbed_returns_a_copy_and_leaves_the_span_alone() -> None:
    memory = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(memory))
    with provider.get_tracer("t").start_span("raw", attributes={**ALLOWED, **DROPPED}):
        pass
    [raw] = memory.get_finished_spans()
    copy = scrubbed(raw)
    assert copy is not raw
    assert dict(raw.attributes or {}) == {**ALLOWED, **DROPPED}
    assert dict(copy.attributes or {}) == ALLOWED


class _Capture(SpanExporter):
    def __init__(self) -> None:
        self.batches: list[list[ReadableSpan]] = []
        self.calls: list[str] = []

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.batches.append(list(spans))
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:
        self.calls.append("shutdown")

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        self.calls.append("flush")
        return True


def test_ac20_the_scrubbing_exporter_hands_its_inner_exporter_only_scrubbed_spans() -> None:
    inner = _Capture()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(ScrubbingExporter(inner)))
    with provider.get_tracer("t").start_span("w", attributes={**ALLOWED, **DROPPED}):
        pass
    [[span]] = inner.batches
    assert dict(span.attributes or {}) == ALLOWED


def test_ac20_the_scrubbing_exporter_passes_flush_and_shutdown_through() -> None:
    inner = _Capture()
    wrapped = ScrubbingExporter(inner)
    assert wrapped.force_flush() is True
    wrapped.shutdown()
    assert inner.calls == ["flush", "shutdown"]


# --- the process's own exporters -----------------------------------------------------------------


def test_ac20_the_test_exporter_is_one_shared_instance() -> None:
    assert shared_exporter() is shared_exporter()


def test_ac20_the_test_exporter_receives_scrubbed_spans() -> None:
    memory = shared_exporter()
    memory.clear()
    with tracer("t").start_as_current_span(
        "via-global", attributes={"http.route": "/r", "http.url": f"/x/{MARKER}"}
    ):
        pass
    [span] = [s for s in memory.get_finished_spans() if s.name == "via-global"]
    assert dict(span.attributes or {}) == {"http.route": "/r"}
    memory.clear()


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_the_test_exporter_is_refused_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr("abacus.kernel.telemetry.settings", lambda: _Env(environment))
    with pytest.raises(RuntimeError):
        shared_exporter()


class _Env:
    def __init__(self, environment: str) -> None:
        self.environment = environment


# --- OTLP ----------------------------------------------------------------------------------------


class _Recording(SpanExporter):
    instances: ClassVar[list[_Recording]] = []

    def __init__(self, **options: object) -> None:
        self.options = options
        self.exported: list[ReadableSpan] = []
        _Recording.instances.append(self)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        self.exported.extend(spans)
        return SpanExportResult.SUCCESS


@pytest.fixture
def otlp(monkeypatch: pytest.MonkeyPatch) -> list[_Recording]:
    _Recording.instances.clear()
    monkeypatch.setattr("abacus.kernel.telemetry._provider", None)
    monkeypatch.setattr(
        "opentelemetry.exporter.otlp.proto.http.trace_exporter.OTLPSpanExporter", _Recording
    )
    return _Recording.instances


def _configure(monkeypatch: pytest.MonkeyPatch, environment: str, endpoint: str) -> TracerProvider:
    monkeypatch.setenv("ABACUS_OTLP_ENDPOINT", endpoint)
    monkeypatch.setenv("ABACUS_ENVIRONMENT", environment)
    settings.cache_clear()
    try:
        return configure_tracing("abacus-api")
    finally:
        monkeypatch.undo()
        settings.cache_clear()


@pytest.mark.parametrize("environment", ["staging", "production"])
@pytest.mark.parametrize("endpoint", ["http://collector.invalid:4318", "ftp://collector.invalid"])
def test_ac20_outside_local_and_test_a_non_https_otlp_endpoint_is_refused(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording], environment: str, endpoint: str
) -> None:
    monkeypatch.setattr(
        "abacus.kernel.telemetry.settings", lambda: _Settings(environment, endpoint)
    )
    with pytest.raises(RuntimeError):
        configure_tracing("abacus-api")
    assert otlp == []


class _Settings:
    release = None

    def __init__(self, environment: str, endpoint: str | None) -> None:
        self.environment = environment
        self.otlp_endpoint = endpoint


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac20_an_https_otlp_endpoint_is_accepted_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording], environment: str
) -> None:
    monkeypatch.setattr(
        "abacus.kernel.telemetry.settings",
        lambda: _Settings(environment, "https://collector.invalid"),
    )
    provider = configure_tracing("abacus-api")
    try:
        [created] = otlp
        assert created.options["endpoint"] == "https://collector.invalid/v1/traces"
    finally:
        provider.shutdown()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac20_http_is_fine_in_local_and_test(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording], environment: str
) -> None:
    provider = _configure(monkeypatch, environment, "http://localhost:4318")
    try:
        [created] = otlp
        assert created.options["endpoint"] == "http://localhost:4318/v1/traces"
    finally:
        provider.shutdown()


@pytest.mark.parametrize("endpoint", ["https://c.invalid/", "https://c.invalid///"])
def test_ac20_a_trailing_slash_is_normalised_in_the_otlp_url(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording], endpoint: str
) -> None:
    provider = _configure(monkeypatch, "test", endpoint)
    try:
        [created] = otlp
        assert created.options["endpoint"] == "https://c.invalid/v1/traces"
    finally:
        provider.shutdown()


def test_ac20_the_otlp_exporter_is_wrapped_in_the_scrubber(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording]
) -> None:
    provider = _configure(monkeypatch, "test", "https://c.invalid")
    try:
        with provider.get_tracer("t").start_as_current_span(
            "out", attributes={"http.route": "/r", "http.url": f"/x/{MARKER}"}
        ):
            pass
        provider.force_flush()
        [created] = otlp
        [exported] = created.exported
        assert dict(exported.attributes or {}) == {"http.route": "/r"}
    finally:
        provider.shutdown()


def test_ac20_the_sampler_follows_the_parent_and_samples_roots(
    monkeypatch: pytest.MonkeyPatch, otlp: list[_Recording]
) -> None:
    monkeypatch.setattr("abacus.kernel.telemetry._provider", None)
    provider = configure_tracing("abacus-api")
    assert isinstance(provider.sampler, ParentBased)
