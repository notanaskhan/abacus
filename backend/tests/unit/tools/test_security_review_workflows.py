"""Security review of the S8 wave B deploy path (independent read-only review), as workflow shape:
- MED 2: every workflow that assumes an AWS role on a dispatch runs only from `main`;
- MED 3: the Inspector gate fails unless the scan completed;
- MED 4: no job that holds AWS credentials installs or runs Node packages (the smokes run in a
  job without an OIDC token);
- MED 5: production's gate compares the PR's record with the build's record for the SHA;
- LOW 6: a rollback has its own concurrency group, so a later deploy dispatch cannot drop it."""

from __future__ import annotations

from typing import cast

import pytest

from .workflow_shape import Mapping, jobs, load, runs, step, steps

MAIN_ONLY = "github.ref == 'refs/heads/main'"
ROLE_WORKFLOWS = (
    "build.yml",
    "deploy-staging.yml",
    "deploy-production.yml",
    "rollback.yml",
    "drill.yml",
    "ops-task.yml",
    "git-bundle-backup.yml",  # Q-01-T07: the weekly source backup
)


def _assumes_a_role(job: Mapping) -> bool:
    return any(
        str(s.get("uses", "")).startswith("aws-actions/configure-aws-credentials@")
        for s in steps(job)
    )


def _runs_node(job: Mapping) -> bool:
    code = runs(job)
    return any(tool in code for tool in ("pnpm", "npm ", "npx ", "playwright", "corepack"))


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_med2_jobs_that_assume_a_role_run_only_from_main(name: str) -> None:
    for job_name, job in jobs(load(name)).items():
        if _assumes_a_role(job) or "id-token" in cast(Mapping, job.get("permissions", {})):
            assert MAIN_ONLY in str(job.get("if", "")), (name, job_name)


def test_med3_the_inspector_gate_fails_when_the_scan_never_completed() -> None:
    script = runs(jobs(load("build.yml"))["inspector"])
    assert 'case "$status" in COMPLETE|ACTIVE)' in script
    assert "::error title=inspector scan incomplete::" in script


@pytest.mark.parametrize("name", ROLE_WORKFLOWS)
def test_med4_no_job_holding_aws_credentials_installs_or_runs_node_packages(name: str) -> None:
    for job_name, job in jobs(load(name)).items():
        if _assumes_a_role(job):
            assert not _runs_node(job) or (name == "build.yml" and job_name == "spa"), (
                name,
                job_name,
            )


@pytest.mark.parametrize(
    ("name", "project"),
    [("deploy-staging.yml", "deploy-smoke"), ("deploy-production.yml", "canary-smoke")],
)
def test_med4_the_smoke_runs_in_its_own_job_without_a_token(name: str, project: str) -> None:
    workflow = jobs(load(name))
    smoke = workflow["smoke"]
    assert cast(Mapping, smoke["permissions"]) == {"contents": "read"}
    assert not _assumes_a_role(smoke)
    assert f"--project={project}" in runs(smoke)
    assert "--ignore-scripts" in runs(smoke)
    assert smoke["needs"] == "deploy"
    assert workflow["record"]["needs"] == ["deploy", "smoke"]
    assert "Record the release" in [s.get("name") for s in steps(workflow["record"])]


def test_med4_the_spa_build_installs_before_it_assumes_the_role() -> None:
    spa = jobs(load("build.yml"))["spa"]
    names = [s.get("name") for s in steps(spa)]
    role = next(i for i, s in enumerate(steps(spa)) if _assumes_a_role({"steps": [s]}))
    assert names.index("Install") < role and names.index("Build each entry present") < role
    assert "--ignore-scripts" in str(step(spa, "Install")["run"])


def test_med5_production_compares_the_pr_record_with_the_build_record() -> None:
    gates = str(step(jobs(load("deploy-production.yml"))["deploy"], "Gates")["run"])
    assert 's3://$ARTIFACTS/releases/$sha/release.json" build-release.json' in gates
    assert "--build-record ../build-release.json" in gates


def test_low6_a_rollback_is_never_dropped_by_a_later_deploy_dispatch() -> None:
    concurrency = cast(Mapping, load("rollback.yml")["concurrency"])
    assert concurrency == {
        "group": "rollback-${{ inputs.environment }}",
        "cancel-in-progress": False,
    }
    take = str(step(jobs(load("rollback.yml"))["rollback"], "Take the deploy lock")["run"])
    assert "--wait-seconds" in take  # a running deploy is excluded by the SSM lock instead
