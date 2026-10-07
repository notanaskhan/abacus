"""Tracing (ADR-022; TASK-013 design §1-2). One trace ID from the API request through workflows,
activities, the outbox and model calls.

    configure_tracing("abacus-api")          # once, at process start
    with tracer(__name__).start_as_current_span("outbox.publish"): ...
    current_trace_id()                       # for logs and audit rows

Spans carry identifiers and outcomes only, never request bodies, prompts, model output or client
data (ADR-031). Every exporter is wrapped in `ScrubbingExporter`, the backstop for spans we don't
write ourselves (FastAPI, Temporal): only allowlisted attributes leave the process; exception
events (message and stack trace) are dropped; status descriptions are cut to a class name.
Export is over OTLP when `otlp_endpoint` is set; otherwise spans are kept in process only (tests
install their own exporter). Trace context crosses process boundaries as a W3C `traceparent`
string (`current_traceparent`, `continue_trace`).
"""

from __future__ import annotations

import re
from collections.abc import Generator, Sequence
from contextlib import contextmanager

from opentelemetry import context, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import Event, ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.sdk.trace.sampling import ALWAYS_ON, ParentBased
from opentelemetry.trace import Status, StatusCode
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from abacus.kernel.config import settings

TRACEPARENT = re.compile(r"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}")
_propagator = TraceContextTextMapPropagator()
_provider: TracerProvider | None = None

# What may leave the process on a span (everything else is dropped): the HTTP route template,
# method and status (never URL, query, client address or user agent), Temporal's IDs, and our own
# `ai.`, `outbox.` and `tenant.` attributes (identifiers and outcomes by construction).
_ATTRIBUTES = frozenset(
    {"http.route", "http.request.method", "http.method"}
    | {"http.status_code", "http.response.status_code"}
    | {"temporalWorkflowID", "temporalRunID", "temporalActivityID", "temporalActivityType"}
    | {"temporalUpdateID"}
)
_PREFIXES = ("ai.", "outbox.", "tenant.")
_EVENT_ATTRIBUTES = frozenset({"outcome", "input_tokens", "output_tokens", "cost_usd"})
_CLASS_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_.]{0,99}")


def _allowed(key: str) -> bool:
    return key in _ATTRIBUTES or key.startswith(_PREFIXES)


def _status(status: Status) -> Status:
    if status.status_code is not StatusCode.ERROR or status.description is None:
        return status
    # "ValueError: <message>" (Temporal, SDK defaults): keep the class name only.
    name = status.description.split(":", 1)[0].strip()
    return Status(StatusCode.ERROR, name if _CLASS_NAME.fullmatch(name) else "error")


def scrubbed(span: ReadableSpan) -> ReadableSpan:
    """A copy of `span` holding only what may leave the process (see `_ATTRIBUTES`)."""
    attributes = {k: v for k, v in (span.attributes or {}).items() if _allowed(k)}
    events = [
        Event(
            e.name,
            {k: v for k, v in (e.attributes or {}).items() if k in _EVENT_ATTRIBUTES},
            e.timestamp,
        )
        for e in span.events
        if e.name != "exception"  # message and stack trace: never exported
    ]
    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=attributes,
        events=events,
        links=span.links,
        kind=span.kind,
        status=_status(span.status),
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class ScrubbingExporter(SpanExporter):
    """Exports through `inner` only the scrubbed copy of each span."""

    def __init__(self, inner: SpanExporter) -> None:
        self._inner = inner

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self._inner.export([scrubbed(span) for span in spans])

    def shutdown(self) -> None:
        self._inner.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._inner.force_flush(timeout_millis)


def _endpoint(raw: str, environment: str) -> str:
    endpoint = raw.rstrip("/")
    if environment not in ("local", "test") and not endpoint.startswith("https://"):
        raise RuntimeError("otlp_endpoint must use https outside local and test")
    return f"{endpoint}/v1/traces"


def configure_tracing(service: str, exporter: SpanExporter | None = None) -> TracerProvider:
    """Install the process's tracer provider (idempotent: the first call wins, except that a
    test may add its exporter to the existing provider)."""
    global _provider
    if _provider is None:
        s = settings()
        attributes = {"service.name": service, "deployment.environment": s.environment}
        if s.release is not None:
            attributes["service.version"] = s.release
        _provider = TracerProvider(
            resource=Resource.create(attributes), sampler=ParentBased(ALWAYS_ON)
        )
        if s.otlp_endpoint is not None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # export only
                OTLPSpanExporter,
            )

            exporter_ = OTLPSpanExporter(endpoint=_endpoint(s.otlp_endpoint, s.environment))
            _provider.add_span_processor(BatchSpanProcessor(ScrubbingExporter(exporter_)))
        trace.set_tracer_provider(_provider)
    if exporter is not None:
        _provider.add_span_processor(SimpleSpanProcessor(ScrubbingExporter(exporter)))
    return _provider


def tracer(name: str) -> trace.Tracer:
    return trace.get_tracer(name)


def current_trace_id() -> str | None:
    """The current trace's ID (32 hex digits), or None outside a recorded span."""
    span_context = trace.get_current_span().get_span_context()
    return format(span_context.trace_id, "032x") if span_context.is_valid else None


def current_span_id() -> str | None:
    span_context = trace.get_current_span().get_span_context()
    return format(span_context.span_id, "016x") if span_context.is_valid else None


def current_traceparent() -> str | None:
    """The current span as a W3C `traceparent`, to carry across a process boundary."""
    carrier: dict[str, str] = {}
    _propagator.inject(carrier)
    value = carrier.get("traceparent")
    return value if value is not None and TRACEPARENT.fullmatch(value) else None


@contextmanager
def continue_trace(traceparent: str | None) -> Generator[None]:
    """Run the block as part of the trace `traceparent` names (no-op for None or malformed)."""
    if traceparent is None or not TRACEPARENT.fullmatch(traceparent):
        yield
        return
    token = context.attach(_propagator.extract({"traceparent": traceparent}))
    try:
        yield
    finally:
        context.detach(token)


def shutdown_tracing() -> None:
    """Export what is buffered and stop (process shutdown)."""
    if _provider is not None:
        _provider.force_flush()
        _provider.shutdown()


_test_exporter: InMemorySpanExporter | None = None


def test_exporter() -> InMemorySpanExporter:
    """One in-memory exporter for the test process, behind the scrubber (attach once; clear it per
    test). The provider is process-global, so tests share this rather than adding their own."""
    global _test_exporter
    if settings().environment not in ("local", "test"):
        raise RuntimeError("the in-memory span exporter is for tests only")
    if _test_exporter is None:
        _test_exporter = InMemorySpanExporter()
        configure_tracing("abacus-test", _test_exporter)
    return _test_exporter
