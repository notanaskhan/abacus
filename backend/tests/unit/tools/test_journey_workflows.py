"""F-04-T28 (F-04.32; AGENTS non-negotiable 17): the journey jobs. Pull requests run the fixture
journeys when what they walk changes; the nightly runs the full-stack journeys on the runner's own
stack; the staging job stays off until staging exists; every job publishes traces and the report;
and no job points a local build, migration or seed at a hosted database."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"

Job = dict[str, object]


def _jobs(name: str) -> dict[str, Job]:
    raw = cast(dict[str, object], yaml.safe_load((WORKFLOWS / name).read_text()))
    return cast(dict[str, Job], raw["jobs"])


def _steps(job: Job) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], job.get("steps", []))


def _runs(job: Job) -> str:
    return "\n".join(str(s.get("run", "")) for s in _steps(job))


def _publishes_traces_and_report(job: Job) -> bool:
    for step in _steps(job):
        uses = str(step.get("uses", ""))
        path = str(cast(dict[str, object], step.get("with", {})).get("path", ""))
        if (
            uses.startswith("actions/upload-artifact@")
            and "always()" in str(step.get("if", ""))
            and "apps/web/playwright-report" in path
            and "apps/web/test-results" in path
        ):
            return True
    return False


def test_t28_pull_requests_run_the_fixture_journeys_when_what_they_walk_changes() -> None:
    ci = _jobs("ci.yml")
    changes = cast(dict[str, str], ci["changes"]["outputs"])
    assert changes["journeys"] == "${{ steps.paths.outputs.journeys }}"
    job = ci["journeys"]
    assert job["needs"] == ["changes"]
    run_steps = [s for s in _steps(job) if "run" in s]
    gated = [s for s in run_steps if "needs.changes.outputs.journeys == 'true'" in str(s["if"])]
    assert any("make journeys JOURNEY_ARGS=--trace=on" in str(s["run"]) for s in gated)
    assert _publishes_traces_and_report(job)
    assert "journeys" in cast(list[str], ci["stage-2"]["needs"])


def test_t28_the_nightly_runs_the_full_stack_journeys_on_its_own_stack() -> None:
    job = _jobs("e2e.yml")["fullstack"]
    runs = _runs(job)
    order = [runs.index(s) for s in ("make dev", "make seed-demo", "make journeys-full")]
    assert order == sorted(order)
    assert "HOLDOUT=fairhaven_ebp" in runs  # J02-audit-core creates Fairhaven (F-04.11)
    assert "--trace=on" in runs
    assert _publishes_traces_and_report(job)
    assert "fullstack" in cast(list[str], _jobs("e2e.yml")["nightly-red"]["needs"])


def test_t28_the_staging_job_is_off_until_staging_exists() -> None:
    job = _jobs("e2e.yml")["staging"]
    assert job["if"] == "vars.STAGING_JOURNEYS == 'on'"
    runs = _runs(job)
    assert "--project=staging" in runs
    # A browser at the hosted URL and nothing else.
    for forbidden in ("make dev", "make seed", "seed-demo", "seed-staging", "migrate", "alembic"):
        assert forbidden not in runs
    assert _publishes_traces_and_report(job)


def test_t28_no_job_points_a_build_or_seed_at_a_hosted_database() -> None:
    for path in (WORKFLOWS / "ci.yml", WORKFLOWS / "e2e.yml"):
        text = path.read_text()
        assert "seed-staging" not in text, path.name  # the runbook's ECS task, never CI
        for name, job in cast(dict[str, Job], yaml.safe_load(text)["jobs"]).items():
            env = {
                **cast(dict[str, str], job.get("env", {}) or {}),
                **{
                    k: v
                    for s in _steps(job)
                    for k, v in cast(dict[str, str], s.get("env", {}) or {}).items()
                },
            }
            for key, value in env.items():
                if re.search(r"DATABASE|DSN|PG(HOST|URL)", key):
                    assert re.search(r"(127\.0\.0\.1|localhost|::1)", str(value)), (
                        path.name,
                        name,
                        key,
                    )
            assert "secrets." not in yaml.safe_dump(job), (path.name, name)
