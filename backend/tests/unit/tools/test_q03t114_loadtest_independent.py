"""Q-03-T114 (TASK-2302; SPEC-541): acceptance tests for the load-test harness (Q-03-T035, T043),
written from the plan rows and the runbook rather than the harness's own tests.

- AC-1 `make loadtest PROFILE=smoke` plays a committed profile and reports p50/p95/p99 per
  endpoint group, nearest-rank on the client side.
- AC-2 it refuses to run while a hosted build or deploy holds the deploy lock, or while any
  database setting points at a hosted database, before it sends a request; a dry run still prints
  the plan.
- AC-3 the x1 smoke's own reports feed the trend, which posts to the quality report and opens a
  ticket past +20% over the 4-week median.

No network, no database, no AWS: the API is an `httpx.MockTransport` and the deploy lock a stub.
"""

from __future__ import annotations

import json
import re
from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from abacus.kernel.clock import system_now
from abacus_tools import deploy_lock
from abacus_tools.loadtest import run as harness
from abacus_tools.loadtest import trend as trends
from abacus_tools.loadtest.run import Report, run, write_report
from abacus_tools.loadtest.scenario import SCENARIOS, Scenario, load, profile
from abacus_tools.loadtest.stats import percentile
from abacus_tools.local import db_guard
from abacus_tools.quality.report import load_rows

REPO = Path(__file__).resolve().parents[4]
LOOPBACK = "http://127.0.0.1:8001"
VARS = {"engagement_id": "e-1", "client_id": "c-1"}
BEARER = "unit-bearer"  # the mock API only echoes it


def _api(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, json={"ok": True})


def _client() -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(_api), base_url=LOOPBACK)


def _short(name: str) -> Scenario:
    """A committed profile cut to a fraction of a second, everything else as committed."""
    found = profile(name)
    return found.model_copy(
        update={"duration_seconds": 0.3, "ramp_seconds": 0, "think_ms": 1, "users": 2}
    )


async def _play(scenario: Scenario) -> Report:
    tokens = {p.subject: BEARER for p in scenario.personas}
    async with _client() as client:
        return await run(scenario, client, token=BEARER, tokens=tokens, variables=VARS)


# --- AC-1: scenarios load, percentiles per endpoint group -------------------------------------


def test_ac1_every_committed_profile_loads_by_name_and_by_path() -> None:
    paths = sorted(SCENARIOS.glob("*.yaml"))
    assert {p.stem for p in paths} >= {"smoke", "x1_smoke"}
    for path in paths:
        assert profile(path.stem) == load(path)


def test_ac1_a_profile_with_an_unknown_field_or_name_is_refused(tmp_path: Path) -> None:
    bad = tmp_path / "bad.yaml"
    bad.write_text("name: bad\nduration_seconds: 1\nsurprise: true\n")
    with pytest.raises(ValidationError):
        load(bad)
    with pytest.raises(ValueError, match="smoke"):
        profile("no_such_profile")


def test_ac1_percentiles_are_nearest_rank() -> None:
    samples = [12.0, 3.0, 7.0, 20.0, 5.0, 9.0, 1.0, 15.0, 11.0, 4.0]  # sorted: 1 3 4 5 7 9 11 ...
    assert percentile(samples, 50) == 7.0  # rank ceil(5.0) = 5
    assert percentile(samples, 95) == 20.0  # rank ceil(9.5) = 10
    assert percentile(samples, 99) == 20.0
    assert percentile(samples, 10) == 1.0


async def test_ac1_smoke_reports_p50_p95_p99_for_every_endpoint_group(tmp_path: Path) -> None:
    smoke = _short("smoke")
    report = await _play(smoke.model_copy(update={"temporal": []}))
    names = {g.name for g in smoke.groups}
    assert names <= {g.name for g in report.groups}
    for group in report.groups:
        if group.name not in names:
            continue
        assert group.count > 0 and group.errors == 0
        assert group.p50_ms is not None and group.p95_ms is not None and group.p99_ms is not None
        assert group.p50_ms <= group.p95_ms <= group.p99_ms
    as_json, as_md = write_report(report, tmp_path)
    data = json.loads(as_json.read_text())
    assert all({"p50_ms", "p95_ms", "p99_ms"} <= set(g) for g in data["groups"])
    header = next(line for line in as_md.read_text().splitlines() if line.startswith("| Group"))
    assert re.search(r"p50 ms \| p95 ms \| p99 ms", header)


def test_ac1_make_loadtest_runs_the_harness_with_the_profile() -> None:
    recipe = (REPO / "Makefile").read_text().split("\nloadtest:", 1)[1].split("\n\n", 1)[0]
    assert "abacus_tools.loadtest.run --profile $(PROFILE)" in recipe
    assert "PROFILE ?= smoke" in (REPO / "Makefile").read_text()


# --- AC-2: never while a hosted build or deploy holds the lock ---------------------------------


def _held() -> deploy_lock.Lock:
    return deploy_lock.Lock(
        holder="deploy-staging",
        run_ref="https://github.com/notanaskhan/abacus/actions/runs/1",
        git_sha="abc1234",
        taken_at=(system_now() - timedelta(minutes=4)).isoformat(),
        purpose="deploy",
    )


@pytest.fixture
def no_run(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Records any attempt to start the run; the guard must stop before it."""
    started: list[str] = []

    async def _main(args: object, scenario: Scenario) -> Report:
        started.append(scenario.name)
        raise AssertionError("the harness started a run")

    monkeypatch.setattr(harness, "_main", _main)
    return started


def test_ac2_a_held_deploy_lock_refuses_before_any_request(
    monkeypatch: pytest.MonkeyPatch, no_run: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ABACUS_DEPLOY_LOCK_ENV", "staging")
    asked: list[str] = []

    def held(env: str, params: object = None) -> deploy_lock.Lock:
        asked.append(env)
        return _held()

    monkeypatch.setattr(deploy_lock, "held", held)
    assert harness.main(["--profile", "smoke", "--base-url", LOOPBACK]) == 2
    assert asked == ["staging"] and no_run == []
    err = capsys.readouterr().err
    assert "deploy lock" in err and "deploy-staging" in err


def test_ac2_a_hosted_database_setting_refuses_before_any_request(
    monkeypatch: pytest.MonkeyPatch, no_run: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(db_guard, "violations", lambda: ["ABACUS_DATABASE_URL"])
    assert harness.main(["--profile", "smoke", "--base-url", LOOPBACK]) == 2
    assert no_run == []
    err = capsys.readouterr().err
    assert "ABACUS_DATABASE_URL" in err and "hosted" in err
    assert "postgres" not in err  # names the setting, never its value


def test_ac2_a_dry_run_still_prints_the_plan_while_the_lock_is_held(
    monkeypatch: pytest.MonkeyPatch, no_run: list[str], capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("ABACUS_DEPLOY_LOCK_ENV", "staging")
    monkeypatch.setattr(deploy_lock, "held", lambda env, params=None: _held())
    assert harness.main(["--profile", "smoke", "--dry-run"]) == 0
    assert no_run == [] and capsys.readouterr().out


def test_ac2_a_free_lock_lets_the_run_start(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ABACUS_DEPLOY_LOCK_ENV", "staging")
    monkeypatch.setattr(deploy_lock, "held", lambda env, params=None: None)
    monkeypatch.setattr(db_guard, "violations", list)
    started: list[str] = []

    async def _main(args: object, scenario: Scenario) -> Report:
        started.append(scenario.name)
        raise harness.Refused("stopped after the guard")

    monkeypatch.setattr(harness, "_main", _main)
    assert harness.main(["--profile", "smoke", "--base-url", LOOPBACK]) == 2
    assert started == ["smoke"]


# --- AC-3: the x1 smoke posts its trend --------------------------------------------------------


def _scaled(report: Report, factor: float, days: int) -> Report:
    at = (system_now() - timedelta(days=days)).isoformat()
    groups = [
        replace(g, p95_ms=None if g.p95_ms is None else g.p95_ms * factor) for g in report.groups
    ]
    return replace(report, started_at=at, groups=groups)


async def test_ac3_x1_smoke_reports_feed_the_trend_and_the_quality_report(tmp_path: Path) -> None:
    latest = await _play(_short("x1_smoke"))
    assert latest.scenario == "x1_smoke"
    history = tmp_path / "history"
    for days, factor in ((14, 10.0), (7, 10.0)):  # earlier runs were slower: no regression
        write_report(_scaled(latest, factor, days), history)
    write_report(latest, history)
    out = tmp_path / "loadtest-trend.json"
    assert trends.main(["--history", str(history), "--out", str(out)]) == 0
    posted = json.loads(out.read_text())
    assert posted["profile"] == "x1_smoke" and posted["regressed"] == []
    row = next(load_rows(posted))
    assert (row.area, row.status) == ("Ops", "ok")
    assert row.source == "loadtest-trend.json"


async def test_ac3_a_slower_x1_smoke_opens_a_ticket_and_posts_a_breach(tmp_path: Path) -> None:
    latest = await _play(_short("x1_smoke"))
    history = tmp_path / "history"
    for days in (21, 10):  # earlier runs were ten times faster: every group regressed
        write_report(_scaled(latest, 0.1, days), history)
    write_report(latest, history)
    out, ticket = tmp_path / "loadtest-trend.json", tmp_path / "ticket.md"
    code = trends.main(["--history", str(history), "--out", str(out), "--ticket", str(ticket)])
    assert code == 1
    posted = json.loads(out.read_text())
    assert set(posted["regressed"]) == {g.name for g in latest.groups if g.p95_ms}
    assert next(load_rows(posted)).status == "breach"
    body = ticket.read_text()
    assert "Load smoke regression: x1_smoke" in body
    assert "127.0.0.1" not in body and BEARER not in body  # results only
