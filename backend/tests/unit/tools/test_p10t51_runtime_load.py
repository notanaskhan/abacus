"""P-10-T51 (TASK-7422; DEC-4412): the runtime v2 and SSE load test's own parts, offline.

Row: "1,500 concurrent streams, 50 parallel engagement runs, commit to SSE p95 at or under 2 s, RDS
connections under 70%; SSE delivery SLO alarm; RB-28 rehearsed". The staging run and the RB-28
rehearsal need staging. Here: the scenario, the stream subjects under the API's 6-per-person
cap, the budgets and the connection ceiling, and the runner signing each stream as its subject.
"""

from __future__ import annotations

from collections import Counter
from decimal import Decimal

import httpx
import pytest

from abacus.kernel.realtime import MAX_STREAMS_PER_USER
from abacus_tools.loadtest import p10_budgets as budgets
from abacus_tools.loadtest.run import run
from abacus_tools.loadtest.scenario import STREAMS_PER_SUBJECT, Scenario, Stream, profile

BEARER = "unit-bearer"  # the mock API only echoes it


def test_the_runtime_scenario_holds_1500_streams_beside_50_engagement_run_users() -> None:
    found = profile("runtime_v2")
    (stream,) = found.streams
    assert stream.count == budgets.RUNTIME_STREAMS == 1500
    assert found.users == budgets.RUNTIME_ENGAGEMENT_RUNS == 50
    assert stream.path.startswith("/v1/events?topics=")
    assert stream.p95_first_event_ms == 500
    start = next(g for g in found.groups if g.name == "start_engagement_run")
    (step,) = start.steps
    assert (step.method, step.expect, step.idempotency) == ("POST", (202,), True)
    assert step.path == "/v1/engagements/{engagement_id}/runs"


def test_streams_spread_over_subjects_at_the_apis_cap() -> None:
    assert STREAMS_PER_SUBJECT == MAX_STREAMS_PER_USER
    (stream,) = profile("runtime_v2").streams
    held = Counter(stream.subjects())
    assert len(held) == 250
    assert max(held.values()) == MAX_STREAMS_PER_USER
    assert next(iter(held)) == "loadtest-stream-0000"
    assert Stream(name="s", path="/v1/events", count=3).subjects() == []


@pytest.mark.parametrize("prefix", ["Upper", "1lead", "has space", "x" * 61])
def test_a_bad_subject_prefix_is_refused(prefix: str) -> None:
    with pytest.raises(ValueError, match="subject_prefix"):
        Stream(name="s", path="/v1/events", subject_prefix=prefix)


def test_the_commit_to_sse_budget_is_two_seconds() -> None:
    named = {b.name: b.p95_ms for b in budgets.BUDGETS}
    assert named["sse_commit_to_event"] == Decimal(2000)
    assert {"stream_first_byte", "sse_commit_to_event"} == budgets.RUNTIME_BUDGETS


def test_a_run_meeting_every_target_reports_nothing() -> None:
    measured = {"stream_first_byte": Decimal(480), "sse_commit_to_event": Decimal(1999)}
    assert budgets.runtime_report(measured, peak_connections=60, max_connections=87) == []


def test_each_missed_target_is_named() -> None:
    measured = {"stream_first_byte": Decimal(501)}
    found = budgets.runtime_report(measured, peak_connections=61, max_connections=87)
    assert found == [
        "stream_first_byte: p95 501 ms > 500 ms",
        "sse_commit_to_event: not measured",
        "db_connections: peak 61 of 87 >= 70%",
    ]


@pytest.mark.parametrize(
    ("peak", "limit", "breach"),
    [(60, 87, False), (61, 87, True), (69, 100, False), (70, 100, True), (1, 0, True)],
)
def test_the_connection_ceiling_is_strictly_under_70_percent(
    peak: int, limit: int, breach: bool
) -> None:
    assert (budgets.connection_breach(peak, limit) is not None) is breach


def _scenario(prefix: str | None) -> Scenario:
    return Scenario.model_validate(
        {
            "name": "unit",
            "duration_seconds": 0.2,
            "persona": "scenario-hannah-leclerc",
            "streams": [
                {
                    "name": "feed",
                    "path": "/v1/events",
                    "count": 8,
                    "hold_seconds": 0.1,
                    "subject_prefix": prefix,
                }
            ],
        }
    )


async def test_each_stream_signs_in_as_its_subject() -> None:
    seen: list[str | None] = []

    def api(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("authorization"))
        body = b"event: stream\ndata: {}\n\n"
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)

    scenario = _scenario("loadtest-stream")
    tokens = {s: f"t-{s[-1]}" for s in scenario.streams[0].subjects()}
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(api), base_url="http://127.0.0.1:8001"
    ) as client:
        report = await run(scenario, client, token=BEARER, stream_tokens=tokens)
    assert Counter(seen) == {"Bearer t-0": 6, "Bearer t-1": 2}
    assert report.groups[0].errors == 0


async def test_a_stream_subject_without_a_token_is_refused_before_anything_runs() -> None:
    def api(request: httpx.Request) -> httpx.Response:  # pragma: no cover - never called
        raise AssertionError(request.url)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(api), base_url="http://127.0.0.1:8001"
    ) as client:
        with pytest.raises(ValueError, match="loadtest-stream-0001"):
            await run(
                _scenario("loadtest-stream"),
                client,
                stream_tokens={"loadtest-stream-0000": "t"},
            )
