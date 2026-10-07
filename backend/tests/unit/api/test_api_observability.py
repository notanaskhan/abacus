"""AC-20: API spans and unhandled-error reporting (TASK-013 interface contract, "API"; ADR-022).

One server span per request, named by route template, with no headers and no bodies as
attributes. An unhandled route error answers the fixed 500, logs the class name only and reports
the error with the route template. The provider is global, so these tests add an in-memory
exporter to it, clear it per test and read only the spans of the request they made.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator

import httpx
import pytest
from fastapi import FastAPI
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from abacus.api import create_app
from abacus.kernel.telemetry import test_exporter as shared_exporter

AUTH_HEADER = "Bearer FAKE-BEARER-VALUE-5521-MARKER"
BODY_MARKER = "REQUEST-BODY-MARKER-9023"
QUERY_MARKER = "QUERY-MARKER-3318"
RESPONSE_MARKER = "RESPONSE-BODY-MARKER-1187"


@pytest.fixture(scope="module")
def exporter() -> InMemorySpanExporter:
    return shared_exporter()


@pytest.fixture(autouse=True)
def clean(exporter: InMemorySpanExporter) -> Iterator[None]:
    exporter.clear()
    yield
    exporter.clear()


def _client(app: FastAPI) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


def _server_spans(exporter: InMemorySpanExporter) -> list[ReadableSpan]:
    return [s for s in exporter.get_finished_spans() if s.parent is None]


def _everything(spans: list[ReadableSpan]) -> str:
    """All names, attributes and events of the spans, as one string to search."""
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


def _extended() -> FastAPI:
    app = create_app()

    async def ok(thing_id: str) -> dict[str, str]:
        return {"detail": RESPONSE_MARKER}

    async def boom(thing_id: str) -> dict[str, str]:
        raise RuntimeError(f"customer ledger row {BODY_MARKER}")

    app.add_api_route("/probe/{thing_id}", ok, methods=["GET", "POST"])
    app.add_api_route("/boom/{thing_id}", boom, methods=["GET"])
    return app


# --- spans ---------------------------------------------------------------------------------------


async def test_ac20_a_request_makes_one_server_span_named_by_route_template(
    exporter: InMemorySpanExporter,
) -> None:
    engagement = uuid.uuid4()
    async with _client(create_app()) as client:
        response = await client.get(f"/v1/engagements/{engagement}/request-items")
    assert response.status_code == 401
    [span] = _server_spans(exporter)
    assert span.name == "GET /v1/engagements/{engagement_id}/request-items"
    assert str(engagement) not in span.name


async def test_ac20_the_span_is_named_by_method_and_template_for_other_routes(
    exporter: InMemorySpanExporter,
) -> None:
    async with _client(_extended()) as client:
        await client.get("/probe/first-id")
        await client.post("/probe/second-id", json={"x": 1})
    names = sorted(s.name for s in _server_spans(exporter))
    assert names == ["GET /probe/{thing_id}", "POST /probe/{thing_id}"]


async def test_ac20_no_headers_and_no_bodies_are_recorded_on_any_span(
    exporter: InMemorySpanExporter,
) -> None:
    async with _client(_extended()) as client:
        await client.post(
            "/probe/abc",
            json={"balance": BODY_MARKER},
            headers={
                "Authorization": AUTH_HEADER,
                "Cookie": f"sid={BODY_MARKER}",
                "X-Custom": "hdr",
            },
        )
    spans = list(exporter.get_finished_spans())
    assert spans
    everything = _everything(spans)
    for hidden in (AUTH_HEADER, AUTH_HEADER.split()[1], BODY_MARKER, RESPONSE_MARKER):
        assert hidden not in everything
    for span in spans:
        for key in span.attributes or {}:
            assert "header" not in key.lower()
            assert "body" not in key.lower()
            assert "cookie" not in key.lower()


async def test_ac20_the_authorization_value_appears_in_no_span_attribute_on_a_rejected_call(
    exporter: InMemorySpanExporter,
) -> None:
    async with _client(create_app()) as client:
        response = await client.get("/v1/me", headers={"Authorization": AUTH_HEADER})
    assert response.status_code == 401
    spans = list(exporter.get_finished_spans())
    assert spans
    assert AUTH_HEADER not in _everything(spans)
    assert AUTH_HEADER.split()[1] not in _everything(spans)


async def test_ac20_the_query_string_is_not_recorded(exporter: InMemorySpanExporter) -> None:
    async with _client(_extended()) as client:
        await client.get(f"/probe/abc?token={QUERY_MARKER}")
    assert QUERY_MARKER not in _everything(list(exporter.get_finished_spans()))


async def test_ac20_each_request_is_its_own_trace(exporter: InMemorySpanExporter) -> None:
    async with _client(_extended()) as client:
        await client.get("/probe/a")
        await client.get("/probe/b")
    first, second = _server_spans(exporter)
    assert first.context is not None
    assert second.context is not None
    assert first.context.trace_id != second.context.trace_id


# --- unhandled errors ----------------------------------------------------------------------------


@pytest.fixture
def reported(monkeypatch: pytest.MonkeyPatch) -> list[tuple[BaseException, dict[str, object]]]:
    seen: list[tuple[BaseException, dict[str, object]]] = []

    def fake(exc: BaseException, **tags: object) -> None:
        seen.append((exc, tags))

    monkeypatch.setattr("abacus.api.app.report", fake)
    return seen


async def test_ac20_an_unhandled_route_error_answers_the_fixed_500_body(
    reported: list[tuple[BaseException, dict[str, object]]],
) -> None:
    async with _client(_extended()) as client:
        response = await client.get("/boom/some-id")
    assert response.status_code == 500
    assert response.json() == {"detail": "internal error"}
    assert BODY_MARKER not in response.text


async def test_ac20_an_unhandled_route_error_is_reported_with_the_route_template(
    reported: list[tuple[BaseException, dict[str, object]]],
) -> None:
    async with _client(_extended()) as client:
        await client.get("/boom/some-id")
    [(exc, tags)] = reported
    assert isinstance(exc, RuntimeError)
    assert tags == {"route": "/boom/{thing_id}"}


async def test_ac20_an_unhandled_route_error_logs_the_class_name_only(
    reported: list[tuple[BaseException, dict[str, object]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    async with _client(_extended()) as client:
        await client.get("/boom/some-id")
    output = capsys.readouterr()
    assert BODY_MARKER not in output.out + output.err
    lines = [json.loads(x) for x in output.out.splitlines() if x.startswith("{")]
    [line] = [x for x in lines if x.get("event") == "api.unexpected_error"]
    assert line["error"] == "RuntimeError"
    assert line["level"] == "error"


async def test_ac20_a_failing_request_still_makes_a_server_span_without_the_message(
    exporter: InMemorySpanExporter,
    reported: list[tuple[BaseException, dict[str, object]]],
) -> None:
    async with _client(_extended()) as client:
        await client.get("/boom/some-id")
    [span] = _server_spans(exporter)
    assert span.name == "GET /boom/{thing_id}"


async def test_ac20_a_handled_error_is_not_reported(
    reported: list[tuple[BaseException, dict[str, object]]],
) -> None:
    async with _client(create_app()) as client:
        response = await client.get(f"/v1/engagements/{uuid.uuid4()}/request-items")
    assert response.status_code == 401
    assert reported == []
