"""Q-03-T043 (TASK-1362; Q-03 E1, E2): the chapter 10 section 10.11.3 scenarios and the x1 smoke's
p95 trend.

- Each scenario exists as a profile, with chapter 10 section 10.11.1's targets on the groups it
  covers; the sign-in wave ramps; the fairness profile puts its targets on the second firm.
- `--dry-run` prints the plan and sends nothing, whatever the target.
- The trend compares the newest x1 smoke with the 4-week median of the runs before it, opens a
  ticket past +20%, and posts to the quality report.

No network and no database.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

from abacus_tools.loadtest import run as harness
from abacus_tools.loadtest import trend as trends
from abacus_tools.loadtest.journey_vars import journey_vars
from abacus_tools.loadtest.run import dry_run, start_offset
from abacus_tools.loadtest.scenario import Scenario, profile
from abacus_tools.quality.report import load_rows

SCENARIOS = (
    "monday_9am",
    "deadline_surge",
    "pbc_import_fairness",
    "sse_soak",
    "backfill_business_hours",
    "failure_under_load",
)
TARGETS = {300.0, 500.0}  # 10.11.1: record read p95 300 ms; list with counts p95 500 ms
WRITES = {"/v1/portal/auth/start"}  # every other write is the named PBC import


# --- the scenarios -----------------------------------------------------------------------------


@pytest.mark.parametrize("name", [*SCENARIOS, "x1_smoke"])
def test_ac_each_scenario_is_a_profile_with_chapter_10_targets(name: str) -> None:
    found = profile(name)
    assert found.name == name and found.max_error_rate == 0.001  # E2: under 0.1%
    targets = {g.p95_ms for g in found.groups if g.p95_ms is not None}
    assert targets and targets <= TARGETS
    for group in found.groups:
        for step in group.steps:
            if step.method != "GET":
                assert step.path in WRITES or step.body == "pbc_import_300", (name, step.path)


def test_ac_monday_9am_is_a_sign_in_wave_into_lists_and_records() -> None:
    monday = profile("monday_9am")
    assert monday.ramp_seconds >= 300 and monday.users == 46  # x1's 46 firm users
    names = {g.name for g in monday.groups}
    assert {"sign_in_shell", "home_waiting_on_you", "lists_with_counts", "record_reads"} == names


def test_ac_fairness_targets_sit_on_the_other_firm_and_the_burst_is_one_firm() -> None:
    fair = profile("pbc_import_fairness")
    other = {g.name: g for g in fair.groups if g.name.startswith("other_firm_")}
    assert other and all(g.p95_ms == 500 for g in other.values())
    for persona in fair.personas:
        fleet = persona.subject.startswith("fleet-001-")
        assert fleet == all(g.startswith("other_firm_") for g in persona.groups)
    paths = [s.path for g in other.values() for s in g.steps]
    assert all("{engagement_id}" not in p for p in paths)  # never the burst firm's engagement
    assert "fleet_engagement_id" in journey_vars()


def test_ac_no_profile_starts_a_workflow_or_holds_a_stream_it_cannot_reach() -> None:
    for name in SCENARIOS:
        found = profile(name)
        assert all(op.kind == "count_workflows" for op in found.temporal)
        assert found.streams == ()  # no stream route yet (P-15); the soak polls


def test_ac_the_x1_smoke_is_five_minutes_and_read_only() -> None:
    smoke = profile("x1_smoke")
    assert smoke.duration_seconds == 300
    assert all(s.method == "GET" for g in smoke.groups for s in g.steps)


# --- ramp and dry run --------------------------------------------------------------------------


def _scenario(**overrides: object) -> Scenario:
    raw: dict[str, object] = {
        "name": "unit",
        "duration_seconds": 10,
        "users": 4,
        "ramp_seconds": 2,
        "groups": [{"name": "g", "p95_ms": 300, "steps": [{"path": "/v1/x/{engagement_id}"}]}],
    }
    raw.update(overrides)
    return Scenario.model_validate(raw)


def test_ac_users_start_evenly_over_the_ramp() -> None:
    found = _scenario()
    assert [start_offset(found, n) for n in range(4)] == [0.0, 0.5, 1.0, 1.5]
    assert start_offset(_scenario(ramp_seconds=0), 3) == 0.0
    with pytest.raises(ValidationError):
        _scenario(ramp_seconds=10)


def test_ac_a_dry_run_fills_every_placeholder_and_names_targets() -> None:
    text = dry_run(_scenario(), {"engagement_id": "e1"})
    assert "GET /v1/x/e1" in text and "300 ms" in text and "No request is sent." in text
    with pytest.raises(ValueError, match="engagement_id"):
        dry_run(_scenario(), {})


def test_ac_main_dry_run_sends_nothing_even_at_a_hosted_url(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(*_: object, **__: object) -> httpx.AsyncClient:
        raise AssertionError("a dry run opened a client")

    monkeypatch.setattr(harness.httpx, "AsyncClient", refuse)
    variables = [a for k, v in journey_vars().items() for a in ("--var", f"{k}={v}")]
    code = harness.main(
        [
            "--profile",
            "pbc_import_fairness",
            "--dry-run",
            "--base-url",
            "https://staging.example",
            *variables,
        ]
    )
    assert code == 0
    assert "other_firm_reads" in capsys.readouterr().out


# --- the trend ---------------------------------------------------------------------------------

T0 = datetime(2027, 3, 1, 15, tzinfo=UTC)


def _report(
    at: datetime, p95: dict[str, float | None], name: str = "x1_smoke"
) -> dict[str, object]:
    return {
        "scenario": name,
        "started_at": at.isoformat(),
        "groups": [{"name": g, "p95_ms": v} for g, v in p95.items()],
    }


def test_ac_a_rise_over_20_percent_of_the_4_week_median_regresses() -> None:
    history = [
        _report(T0 - timedelta(days=d), {"home": 100.0, "reads": 200.0}) for d in (21, 14, 7)
    ]
    latest = _report(T0, {"home": 125.0, "reads": 230.0})
    found = trends.trend([*history, latest])
    assert found is not None
    by = {g.name: g for g in found.groups}
    assert (by["home"].median_p95_ms, by["home"].rise, by["home"].regressed) == (100.0, 0.25, True)
    assert (by["reads"].rise, by["reads"].regressed) == (0.15, False)
    assert [g.name for g in found.regressed] == ["home"]
    assert "| home | 125.0 | 100.0 | 25% | 3 |" in trends.ticket(found)


def test_ac_runs_older_than_4_weeks_or_of_another_profile_are_not_the_median() -> None:
    old = [_report(T0 - timedelta(days=d), {"home": 10.0}) for d in (40, 35)]
    other = [_report(T0 - timedelta(days=d), {"home": 10.0}, "journeys") for d in (3, 2)]
    recent = [_report(T0 - timedelta(days=d), {"home": 100.0}) for d in (5, 3)]
    found = trends.trend([*old, *other, *recent, _report(T0, {"home": 110.0})])
    assert found is not None
    [home] = found.groups
    assert (home.median_p95_ms, home.runs_in_median, home.regressed) == (100.0, 2, False)


def test_ac_without_enough_history_a_group_has_no_median_and_never_passes_silently() -> None:
    found = trends.trend(
        [_report(T0 - timedelta(days=1), {"home": 1.0}), _report(T0, {"home": 9.0})]
    )
    assert found is not None
    [home] = found.groups
    assert (home.median_p95_ms, home.rise, home.regressed) == (None, None, False)
    assert next(load_rows(json.loads(json.dumps(_trend_json(found))))).status == "reported"


def _trend_json(found: trends.Trend) -> dict[str, object]:
    from dataclasses import asdict

    return {**asdict(found), "regressed": [g.name for g in found.regressed]}


def test_ac_main_writes_the_trend_and_a_ticket_and_exits_1_on_a_regression(tmp_path: Path) -> None:
    history = tmp_path / "history"
    history.mkdir()
    for d, p95 in ((14, 100.0), (7, 100.0), (0, 200.0)):
        at = T0 - timedelta(days=d)
        (history / f"x1_smoke-{d}.json").write_text(json.dumps(_report(at, {"home": p95})))
    out, ticket = tmp_path / "loadtest-trend.json", tmp_path / "ticket.md"
    assert (
        trends.main(["--history", str(history), "--out", str(out), "--ticket", str(ticket)]) == 1
    )
    assert json.loads(out.read_text())["regressed"] == ["home"]
    assert "Load smoke regression" in ticket.read_text()
    assert trends.main(["--history", str(tmp_path / "empty-nowhere")]) == 2


def test_ac_the_quality_report_posts_the_trend() -> None:
    assert next(load_rows(None)).value == "no data"
    history = [_report(T0 - timedelta(days=d), {"home": 100.0}) for d in (14, 7)]
    found = trends.trend([*history, _report(T0, {"home": 150.0})])
    assert found is not None
    row = next(load_rows(_trend_json(found)))
    assert (row.area, row.status) == ("Ops", "breach")
    assert "home" in row.value
