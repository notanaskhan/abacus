"""Tracing (ADR-022; TASK-013 design §1-2). One trace ID from the API request through workflows,
activities, the outbox and model calls.

    configure_tracing("abacus-api")          # once, at process start
    with tracer(__name__).start_as_current_span("outbox.publish"): ...
    current_trace_id()                       # for logs and audit rows

Spans carry identifiers and outcomes only, never request bodies, prompts, model output or client
data (ADR-031). Export is over OTLP when `otlp_endpoint` is set; otherwise spans are kept in
process only (tests install their own exporter). Trace context crosses process boundaries as a
W3C `traceparent` string (`current_traceparent`, `continue_trace`).
"""

from __future__ import annotations

import re
from collections.abc import Generator
from contextlib import contextmanager

from opentelemetry import context, trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from abacus.kernel.config import settings

TRACEPARENT = re.compile(r"00-[0-9a-f]{32}-[0-9a-f]{16}-[0-9a-f]{2}")
_propagator = TraceContextTextMapPropagator()
_provider: TracerProvider | None = None


def configure_tracing(service: str, exporter: SpanExporter | None = None) -> TracerProvider:
    """Install the process's tracer provider (idempotent: the first call wins, except that a
    test may add its exporter to the existing provider)."""
    global _provider
    if _provider is None:
        s = settings()
        attributes = {"service.name": service, "deployment.environment": s.environment}
        if s.release is not None:
            attributes["service.version"] = s.release
        _provider = TracerProvider(resource=Resource.create(attributes))
        if s.otlp_endpoint is not None:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (  # export only
                OTLPSpanExporter,
            )

            _provider.add_span_processor(
                BatchSpanProcessor(OTLPSpanExporter(endpoint=f"{s.otlp_endpoint}/v1/traces"))
            )
        trace.set_tracer_provider(_provider)
    if exporter is not None:
        _provider.add_span_processor(SimpleSpanProcessor(exporter))
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
