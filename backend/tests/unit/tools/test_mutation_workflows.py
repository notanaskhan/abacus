"""Q-03-T026 and T027 (ADR-079; DEC-365): the mutation jobs' shape. The nightly mutates the red
files changed in 24 hours inside 60 minutes; the weekly runs every red scope on Sundays in shards
under 4 hours and enforces the floors; both publish survivors per module; the floors job compares
with the pull request's base. mutmut is the allowlisted, pinned version and never enters the lock;
actions are pinned by SHA; the token stays read-only and no secret is used."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"
MUTMUT = "uv run --with mutmut==3.8.0 mutmut run"

Job = dict[str, object]


def _load(name: str) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load((WORKFLOWS / name).read_text()))


def _jobs(name: str) -> dict[str, Job]:
    return cast(dict[str, Job], _load(name)["jobs"])


def _triggers(name: str) -> dict[str, object]:
    raw = cast(dict[object, object], _load(name))
    return cast(dict[str, object], raw.get("on", raw.get(True)))  # PyYAML reads `on` as True


def _steps(job: Job) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], job.get("steps", []))


def _runs(job: Job) -> str:
    return "\n".join(str(s.get("run", "")) for s in _steps(job))


def _uploads(job: Job) -> list[dict[str, object]]:
    return [
        s for s in _steps(job) if str(s.get("uses", "")).startswith("actions/upload-artifact@")
    ]


def test_t026_nightly_mutates_changed_red_files_inside_60_minutes() -> None:
    assert _triggers("mutation-nightly.yml")["schedule"] == [{"cron": "17 7 * * *"}]
    job = _jobs("mutation-nightly.yml")["incremental"]
    runs = _runs(job)
    assert "mutation plan nightly --since-hours 24" in runs
    assert f"timeout --signal=INT 60m {MUTMUT}" in runs
    assert cast(int, job["timeout-minutes"]) <= 80
    checkout = _steps(job)[0]
    assert cast(dict[str, object], checkout["with"])["fetch-depth"] == 0
    order = [runs.index(s) for s in ("mutation narrow", "mutation prepare", MUTMUT)]
    assert order == sorted(order)


def test_t026_weekly_runs_every_scope_on_sunday_in_shards_under_4_hours() -> None:
    assert _triggers("mutation-weekly.yml")["schedule"] == [{"cron": "0 6 * * 0"}]
    jobs = _jobs("mutation-weekly.yml")
    shard = jobs["shard"]
    matrix = cast(dict[str, object], cast(dict[str, object], shard["strategy"])["matrix"])
    assert matrix["shard"] == [1, 2, 3, 4]
    runs = _runs(shard)
    assert "mutation plan weekly" in runs and "--shards 4" in runs
    assert f"timeout --signal=INT 230m {MUTMUT}" in runs
    assert cast(int, shard["timeout-minutes"]) <= 250
    floors = jobs["floors"]
    assert floors["needs"] == ["shard"] and floors["if"] == "always()"
    assert "--enforce-floors" in _runs(floors)


def test_t026_both_jobs_publish_survivors_per_module() -> None:
    for name, job_name in (
        ("mutation-nightly.yml", "incremental"),
        ("mutation-weekly.yml", "floors"),
    ):
        job = _jobs(name)[job_name]
        runs = _runs(job)
        assert "mutation summarise" in runs
        assert 'cat "$OUT/mutation-survivors.md" >> "$GITHUB_STEP_SUMMARY"' in runs
        paths = [str(cast(dict[str, object], s["with"])["path"]) for s in _uploads(job)]
        assert "${{ runner.temp }}/mutation-report" in paths, name
        assert all("always()" in str(s.get("if", "")) for s in _uploads(job)), name


def test_t027_the_floors_job_compares_with_the_pull_requests_base() -> None:
    triggers = _triggers("mutation-floors.yml")
    assert set(triggers) == {"pull_request", "merge_group"}
    job = _jobs("mutation-floors.yml")["floors"]
    assert cast(dict[str, object], _steps(job)[0]["with"])["fetch-depth"] == 0
    assert 'python3 -m abacus_tools.quality.mutation_floors --base "$BASE"' in _runs(job)
    makefile = (REPO / "Makefile").read_text()
    check_fast = makefile.split("check-fast:", 1)[1].split("\n\n", 1)[0]
    assert "abacus_tools.quality.mutation_floors" in check_fast


def test_mutation_workflows_pin_actions_stay_read_only_and_use_no_secrets() -> None:
    for name in ("mutation-nightly.yml", "mutation-weekly.yml", "mutation-floors.yml"):
        raw = _load(name)
        text = (WORKFLOWS / name).read_text()
        assert raw["permissions"] == {"contents": "read"}, name
        assert "secrets." not in text, name
        for job in cast(dict[str, Job], raw["jobs"]).values():
            assert "permissions" not in job
            for step in _steps(job):
                uses = str(step.get("uses", ""))
                if uses:
                    assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", uses), (name, uses)
                checkout = uses.startswith("actions/checkout@")
                if checkout:
                    assert cast(dict[str, object], step["with"])["persist-credentials"] is False
        for line in text.splitlines():
            if "mutmut" in line and "uv run" in line:
                assert "--with mutmut==3.8.0" in line, line
    lock = (REPO / "backend" / "uv.lock").read_text()
    assert 'name = "mutmut"' not in lock  # run beside the lock, never in it
