"""AC-20: what an API request's spans export, inbound trace headers, and shutdown (TASK-013
contract revision 1, "Scrubbing exporter" and "API"; ADR-022, ADR-031)."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from abacus.api import create_app
from abacus.kernel.telemetry import test_exporter as shared_exporter

ALLOWED = {
    "http.route",
    "http.request.method",
    "http.method",
    "http.status_code",
    "http.response.status_code",
    "temporalWorkflowID",
    "temporalRunID",
    "temporalActivityID",
    "temporalActivityType",
    "temporalUpdateID",
}
PREFIXES = ("ai.", "outbox.", "tenant.")
MARKER = "API-MARKER-7415"
CALLER_TRACE = "ab" * 16
CALLER_SPAN = "cd" * 8


@pytest.fixture
def exporter() -> Iterator[InMemorySpanExporter]:
    memory = shared_exporter()
    memory.clear()
    yield memory
    memory.clear()


def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _app() -> FastAPI:
    app = create_app()

    async def ok(thing_id: str) -> dict[str, str]:
        return {"ok": thing_id}

    async def boom(thing_id: str) -> dict[str, str]:
        raise RuntimeError(f"ledger row {MARKER}")

    app.add_api_route("/probe/{thing_id}", ok, methods=["GET"])
    app.add_api_route("/boom/{thing_id}", boom, methods=["GET"])
    return app


def _trace(span: ReadableSpan) -> str:
    assert span.context is not None
    return format(span.context.trace_id, "032x")


async def test_ac20_exported_request_spans_hold_only_allowlisted_attributes(
    exporter: InMemorySpanExporter,
) -> None:
    async with _client(_app()) as client:
        await client.get(
            f"/probe/{MARKER}?q={MARKER}",
            headers={"User-Agent": f"agent/{MARKER}", "X-Forwarded-For": "10.9.8.7"},
        )
    spans = list(exporter.get_finished_spans())
    assert spans
    for span in spans:
        for key in span.attributes or {}:
            assert key in ALLOWED or key.startswith(PREFIXES), key
    [server] = [s for s in spans if s.parent is None]
    assert dict(server.attributes or {}).get("http.route") == "/probe/{thing_id}"
    assert MARKER not in repr([dict(s.attributes or {}) for s in spans])


async def test_ac20_a_failing_request_exports_no_exception_event_and_a_class_name_status(
    exporter: InMemorySpanExporter,
) -> None:
    async with _client(_app()) as client:
        response = await client.get("/boom/x")
    assert response.status_code == 500
    spans = list(exporter.get_finished_spans())
    assert spans
    for span in spans:
        assert [e for e in span.events if e.name == "exception"] == []
        description = span.status.description
        assert description is None or MARKER not in description
        assert description is None or ":" not in description
    assert MARKER not in repr([s.events for s in spans])


async def test_ac20_an_inbound_traceparent_does_not_choose_the_requests_trace(
    exporter: InMemorySpanExporter,
) -> None:
    header = f"00-{CALLER_TRACE}-{CALLER_SPAN}-01"
    async with _client(_app()) as client:
        await client.get(
            "/probe/a", headers={"traceparent": header, "tracestate": f"vendor={MARKER}"}
        )
    spans = list(exporter.get_finished_spans())
    assert spans
    for span in spans:
        assert _trace(span) != CALLER_TRACE
        assert span.parent is None or span.parent.span_id != int(CALLER_SPAN, 16)
    [server] = [s for s in spans if s.name.startswith("GET /probe")]
    assert server.parent is None
    assert MARKER not in repr([(s.context, s.attributes) for s in spans])


async def test_ac20_an_inbound_traceparent_never_reaches_an_audit_trace_id(
    exporter: InMemorySpanExporter,
) -> None:
    seen: list[str | None] = []

    async def where(thing_id: str) -> dict[str, str]:
        from abacus.kernel.telemetry import current_trace_id

        seen.append(current_trace_id())
        return {"ok": thing_id}

    app = create_app()
    app.add_api_route("/where/{thing_id}", where, methods=["GET"])
    async with _client(app) as client:
        await client.get(
            f"/where/{uuid.uuid4()}",
            headers={"traceparent": f"00-{CALLER_TRACE}-{CALLER_SPAN}-01"},
        )
    [trace_id] = seen
    assert trace_id is not None
    assert trace_id != CALLER_TRACE


async def test_ac20_requests_without_a_traceparent_each_start_a_trace(
    exporter: InMemorySpanExporter,
) -> None:
    async with _client(_app()) as client:
        await client.get("/probe/a")
        await client.get("/probe/b")
    servers = [s for s in exporter.get_finished_spans() if s.parent is None]
    assert len(servers) == 2
    assert _trace(servers[0]) != _trace(servers[1])


async def test_ac20_app_shutdown_flushes_traces_and_error_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    monkeypatch.setattr("abacus.api.app.shutdown_tracing", lambda: calls.append("tracing"))
    monkeypatch.setattr("abacus.api.app.flush_errors", lambda: calls.append("errors"))
    app = create_app()
    async with app.router.lifespan_context(app):
        assert calls == []
    assert sorted(calls) == ["errors", "tracing"]
