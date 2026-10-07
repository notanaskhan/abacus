"""Span capture shared by the TASK-013 integration tests.

The tracer provider is global and set once per process; `telemetry.test_exporter()` is its one
in-memory exporter (behind the scrubber). Tests clear it and read only the spans of their trace.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterable

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from abacus.kernel.telemetry import test_exporter


def install() -> InMemorySpanExporter:
    return test_exporter()


def trace_hex(span: ReadableSpan) -> str:
    assert span.context is not None
    return format(span.context.trace_id, "032x")


def span_hex(span: ReadableSpan) -> str:
    assert span.context is not None
    return format(span.context.span_id, "016x")


def spans_of(trace_id: str) -> list[ReadableSpan]:
    return [s for s in test_exporter().get_finished_spans() if trace_hex(s) == trace_id]


async def until_spans(
    trace_id: str, ready: Callable[[list[ReadableSpan]], bool], timeout: float = 15.0
) -> list[ReadableSpan]:
    """Spans of a trace once `ready` holds (workflow spans end a moment after the result)."""
    import asyncio
    import time

    deadline = time.monotonic() + timeout
    while True:
        found = spans_of(trace_id)
        if ready(found) or time.monotonic() > deadline:
            return found
        await asyncio.sleep(0.05)


def everything(spans: Iterable[ReadableSpan]) -> str:
    """Every name, attribute, event and status text of the spans, as one searchable string."""
    return json.dumps(
        [
            {
                "name": s.name,
                "attributes": dict(s.attributes or {}),
                "events": [(e.name, dict(e.attributes or {})) for e in s.events],
                "status": s.status.description,
            }
            for s in spans
        ],
        default=str,
    )
