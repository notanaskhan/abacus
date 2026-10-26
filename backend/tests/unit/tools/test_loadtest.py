"""Q-03-T035 (TASK-1288; Q-03 E1): the load-test harness plays YAML scenarios on httpx and
asyncio and reports p50/p95/p99 per endpoint group; it runs against local stacks only.

No network: the API is an `httpx.MockTransport` and the Temporal client a stub operation.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from abacus_tools.loadtest import run as harness
from abacus_tools.loadtest.run import Refused, check_local, markdown, run, write_report
from abacus_tools.loadtest.scenario import SCENARIOS, Scenario, TemporalOp, load, profile
from abacus_tools.loadtest.stats import GroupResult, percentile, verdict

BEARER = "unit-bearer"  # the mock API only echoes it


def _scenario(**overrides: object) -> Scenario:
    raw: dict[str, object] = {
        "name": "unit",
        "duration_seconds": 0.3,
        "users": 2,
        "think_ms": 5,
        "groups": [
            {"name": "health", "steps": [{"path": "/healthz", "auth": False}]},
            {
                "name": "records",
                "weight": 2,
                "p95_ms": 10_000,
                "steps": [{"path": "/v1/engagements/{engagement_id}"}, {"path": "/v1/missing"}],
            },
        ],
        "streams": [{"name": "feed", "path": "/v1/stream", "count": 2, "hold_seconds": 0.2}],
        "temporal": [{"name": "visibility", "kind": "count_workflows", "rate_per_second": 20}],
    }
    raw.update(overrides)
    return Scenario.model_validate(raw)


class Api:
    """A local API stand-in: records what it was asked and answers like the app."""

    def __init__(self) -> None:
        self.seen: list[tuple[str, str | None]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append((request.url.path, request.headers.get("authorization")))
        if request.url.path == "/v1/stream":
            body = b": comment\n\nevent: ping\ndata: {}\n\n"
            return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=body)
        if request.url.path == "/v1/missing":
            return httpx.Response(404)
        return httpx.Response(200, json={"ok": True})


def _client(api: Api) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(api), base_url="http://127.0.0.1:8001")


# --- scenarios -----------------------------------------------------------------------------------


def test_e1_every_committed_profile_loads_and_smoke_is_short_and_light() -> None:
    for path in sorted(SCENARIOS.glob("*.yaml")):
        load(path)
    smoke = profile("smoke")
    assert smoke.duration_seconds <= 10 and smoke.users <= 5
    assert {g.name for g in smoke.groups} >= {"health", "me", "record_lists"}
    assert all(s.method == "GET" for g in smoke.groups for s in g.steps)  # read-only


@pytest.mark.parametrize(
    "change",
    [
        {"groups": [], "streams": [], "temporal": []},
        {"streams": [{"name": "health", "path": "/x"}]},
        {"temporal": [{"name": "t", "kind": "start_workflow"}]},
        {"surprise": 1},
        {"duration_seconds": 0},
        {"groups": [{"name": "Bad Name", "steps": [{"path": "/x"}]}]},
        {"groups": [{"name": "g", "steps": [{"path": "https://elsewhere.example/x"}]}]},
    ],
)
def test_e1_an_invalid_scenario_is_refused(change: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _scenario(**change)


def test_e1_an_unknown_profile_names_the_known_ones() -> None:
    with pytest.raises(ValueError, match="smoke"):
        profile("nope")
    with pytest.raises(ValueError, match="not a name"):
        profile("../etc")


# --- statistics ----------------------------------------------------------------------------------


def test_e1_percentiles_are_nearest_rank_on_the_client_side() -> None:
    samples = [float(n) for n in range(100, 0, -1)]
    assert (percentile(samples, 50), percentile(samples, 95), percentile(samples, 99)) == (
        50.0,
        95.0,
        99.0,
    )
    assert percentile([7.0], 99) == 7.0
    assert percentile([], 50) is None
    with pytest.raises(ValueError):
        percentile(samples, 0)


def _group(name: str, *, count: int, errors: int, p95: float, target: float | None) -> GroupResult:
    passed = target is None or p95 <= target
    return GroupResult(name, "http", count, errors, {}, 1.0, p95, p95, p95, 1.0, target, passed)


def test_e2_the_pass_rule_holds_targets_and_the_error_ceiling() -> None:
    fine = _group("a", count=2000, errors=1, p95=120, target=300)
    assert verdict([fine], 0.001).passed
    slow = _group("b", count=10, errors=0, p95=450, target=300)
    assert verdict([fine, slow], 0.001).reasons == ["b: p95 450 ms over 300 ms"]
    erring = _group("c", count=100, errors=1, p95=10, target=None)
    found = verdict([erring], 0.001)
    assert not found.passed and found.error_rate == 0.01
    assert not verdict([], 0.001).passed


# --- the runner ----------------------------------------------------------------------------------


async def test_e1_a_run_reports_p50_p95_p99_per_endpoint_group() -> None:
    api = Api()
    ops: list[TemporalOp] = []

    async def temporal(op: TemporalOp) -> object:
        ops.append(op)
        return 0

    async with _client(api) as client:
        report = await run(
            _scenario(),
            client,
            token=BEARER,
            temporal=temporal,
            variables={"engagement_id": "e1"},
        )
    by_name = {g.name: g for g in report.groups}
    assert set(by_name) == {"health", "records", "feed", "visibility"}
    for g in report.groups:
        assert g.count > 0
        p50, p95, p99, top = g.p50_ms, g.p95_ms, g.p99_ms, g.max_ms
        assert p50 is not None and p95 is not None and p99 is not None and top is not None
        assert p50 <= p95 <= p99 <= top
    records = by_name["records"]
    assert records.errors * 2 == records.count and records.error_codes == {"404": records.errors}
    assert (by_name["feed"].kind, by_name["feed"].count, by_name["feed"].errors) == ("sse", 2, 0)
    assert by_name["visibility"].kind == "temporal" and ops
    assert ("/v1/engagements/e1", f"Bearer {BEARER}") in api.seen
    assert all(auth is None for path, auth in api.seen if path == "/healthz")
    assert not report.verdict.passed  # the 404s break the error ceiling
    assert any("error rate" in r for r in report.verdict.reasons)


async def test_e1_a_missing_variable_is_refused_before_anything_runs() -> None:
    api = Api()
    async with _client(api) as client:
        with pytest.raises(ValueError, match="engagement_id"):
            await run(_scenario(temporal=[]), client)
    assert api.seen == []


async def test_e1_a_stream_without_events_is_an_error() -> None:
    def quiet(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": "text/event-stream"}, content=b"")

    scenario = _scenario(groups=[], temporal=[])
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(quiet), base_url="http://127.0.0.1:8001"
    ) as client:
        report = await run(scenario, client)
    [feed] = report.groups
    assert (feed.count, feed.errors, feed.error_codes) == (2, 2, {"no_event": 2})


# --- local only, and the report --------------------------------------------------------------


@pytest.mark.parametrize(
    ("base", "temporal"),
    [
        ("https://staging.example.com", None),
        ("http://10.0.0.5:8001", None),
        ("http://127.0.0.1:8001", "temporal.example.com:7233"),
        ("127.0.0.1:8001", None),
    ],
)
def test_e1_only_loopback_targets_are_load_tested(base: str, temporal: str | None) -> None:
    with pytest.raises(Refused):
        check_local(base, temporal)


def test_e1_a_local_stack_is_accepted() -> None:
    check_local("http://127.0.0.1:8011", "127.0.0.1:7243")
    check_local("http://localhost:8001", None)


def test_e1_main_refuses_a_hosted_target_without_calling_it(
    capsys: pytest.CaptureFixture[str],
) -> None:
    code = harness.main(["--profile", "smoke", "--base-url", "https://staging.example.com"])
    assert code == 2
    assert "not a loopback address" in capsys.readouterr().err


async def test_e1_the_report_is_written_as_json_and_markdown(tmp_path: Path) -> None:
    async with _client(Api()) as client:
        report = await run(
            _scenario(streams=[], temporal=[]), client, variables={"engagement_id": "e"}
        )
    as_json, as_md = write_report(report, tmp_path)
    data = json.loads(as_json.read_text())
    assert {g["name"] for g in data["groups"]} == {"health", "records"}
    assert all({"p50_ms", "p95_ms", "p99_ms"} <= set(g) for g in data["groups"])
    assert as_md.read_text() == markdown(report)
    assert "| records | http |" in as_md.read_text()


def test_e1_start_workflow_runs_only_in_the_local_default_namespace(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Security review (DEC-397): starting workflows is load only a local namespace takes."""
    scenario = tmp_path / "starts.yaml"
    scenario.write_text(
        "name: starts\nduration_seconds: 1\ntemporal:\n"
        "  - {name: starts, kind: start_workflow, workflow: canary, task_queue: q}\n"
    )
    code = harness.main(
        ["--scenario", str(scenario), "--base-url", "http://127.0.0.1:8001", "--namespace", "prod"]
    )
    assert code == 2
    assert "namespace" in capsys.readouterr().err
    with pytest.raises(Refused):
        check_local("http://127.0.0.1:8001", "127.0.0.1:7233", starts_in="staging")
    check_local("http://127.0.0.1:8001", "127.0.0.1:7233", starts_in="default")
