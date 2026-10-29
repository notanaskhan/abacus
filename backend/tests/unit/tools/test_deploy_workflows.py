"""Q-01-T11, T18, T34 (SPEC-050 AC-19, AC-26): the build, deploy, rollback and ops-task
workflows' shape, read from the files (never run): what triggers each, the order of the steps,
the gates before the lock, the lock released on every path, and the shared deploy script's SPA
order and digest-only images."""

from __future__ import annotations

from typing import cast

from abacus_tools.release import OPS_COMMANDS

from .workflow_shape import (
    PINNED,
    REPO,
    Mapping,
    index,
    jobs,
    load,
    runs,
    step,
    steps,
    text,
    triggers,
    uses,
)

SCRIPT = (REPO / "deploy" / "scripts" / "release.sh").read_text()
DEPLOYS = ("deploy-staging.yml", "deploy-production.yml", "rollback.yml", "ops-task.yml")


def _job(name: str) -> Mapping:
    return next(iter(jobs(load(name)).values()))


def _function(name: str) -> str:
    start = SCRIPT.index(f"{name}() {{")
    return SCRIPT[start : SCRIPT.index("\n}\n", start)]


# --- build.yml (Q-01-T11) ----------------------------------------------------------------------


def test_build_runs_on_dispatch_and_weekly_for_the_base_refresh() -> None:
    """DEC-1007 (amends SPEC-050 AC-19): a push never builds; a dispatch on main builds once per
    batch, and the weekly schedule checks the base image."""
    build = load("build.yml")
    on = triggers(build)
    assert set(on) == {"schedule", "workflow_dispatch"}
    main = "github.ref == 'refs/heads/main'"
    assert jobs(build)["base-refresh"]["if"] == f"{main} && github.event_name == 'schedule'"
    assert jobs(build)["image"]["if"] == f"{main} && github.event_name != 'schedule'"


def test_build_reuses_the_digest_of_a_sha_already_built() -> None:
    image = jobs(load("build.yml"))["image"]
    assert index(image, "Existing digest for this SHA?") < index(image, "Build and push once")
    build = step(image, "Build and push once")
    assert "steps.existing.outputs.digest == ''" in str(build["if"])
    script = str(build["run"])
    for flag in (
        '--tag "$ECR_REPOSITORY:$GITHUB_SHA"',
        "--provenance=mode=max",
        "--sbom=true",
        "--push",
    ):
        assert flag in script
    assert "containerimage.digest" in script


def test_build_records_inspector_the_spa_manifest_and_release_json() -> None:
    build = jobs(load("build.yml"))
    assert "abacus_tools.release inspector" in runs(build["inspector"])
    assert "releases/$GITHUB_SHA/inspector.json" in runs(build["inspector"])
    spa = runs(build["spa"])
    assert "pnpm -C apps/web build" in spa and "build:portal" in spa
    assert "abacus_tools.release manifest" in spa
    assert "web/$GITHUB_SHA/" in spa and "already uploaded" in spa
    record = runs(build["record"])
    assert 'git rev-parse "HEAD:infra"' in record
    assert "abacus_tools.release record" in record
    assert "releases/$GITHUB_SHA/release.json" in record


def test_build_deploys_nothing() -> None:
    body = text("build.yml")
    for forbidden in ("update-service", "run-task", "deploy_lock", "terraform apply"):
        assert forbidden not in body


# --- deploy-staging.yml (Q-01-T18) -------------------------------------------------------------


def test_staging_is_dispatched_never_on_a_merge_or_a_schedule() -> None:
    staging = load("deploy-staging.yml")
    assert set(triggers(staging)) == {"workflow_dispatch"}
    assert staging["concurrency"] == {"group": "deploy-staging", "cancel-in-progress": False}


def test_staging_runs_the_sequence_in_order() -> None:
    staging = jobs(load("deploy-staging.yml"))
    job = staging["deploy"]
    order = [
        "The release record",
        "Take the deploy lock",
        "Pre-flight",
        "Migrate",
        "Ensure the platform-job Schedules",
        "Roll the workers",
        "Roll the API",
        "Publish the SPA",
        "Release the deploy lock",
    ]
    positions = [index(job, name) for name in order]
    assert positions == sorted(positions)
    # Then the smoke (its own job), then the record (after a green smoke).
    assert staging["smoke"]["needs"] == "deploy"
    assert staging["record"]["needs"] == ["deploy", "smoke"]
    preflight = str(step(job, "Pre-flight")["run"])
    assert "alembic heads" in preflight and "pytest tests/workflows" in preflight
    assert "infra_applied" in preflight  # a changed infra_sha stops until applied by hand
    assert 'run_task "$MIGRATE_TASK_DEFINITION" migrate migrate' in str(
        step(job, "Migrate")["run"]
    )
    assert "staging-verified.json" in str(step(staging["record"], "Record the release")["run"])
    assert "--project=deploy-smoke" in str(step(staging["smoke"], "Deploy smoke")["run"])
    # The smoke never checks out the dispatched SHA (CodeQL: untrusted checkout, cache poisoning).
    checkout = next(s for s in steps(staging["smoke"]) if "checkout" in str(s.get("uses", "")))
    assert "ref" not in cast(Mapping, checkout.get("with", {}))


# --- deploy-production.yml and rollback.yml (Q-01-T34) -----------------------------------------


def test_production_runs_only_on_a_merged_release_record() -> None:
    production = load("deploy-production.yml")
    push = cast(Mapping, triggers(production)["push"])
    assert set(triggers(production)) == {"push"}
    assert push == {"branches": ["main"], "paths": ["deploy/production/release.json"]}
    job = _job("deploy-production.yml")
    gates = str(step(job, "Gates")["run"])
    assert "abacus_tools.release gate" in gates
    for record in ("staging-verified", "replay", "inspector"):
        assert record in gates
    assert index(job, "Gates") < index(job, "Take the deploy lock") < index(job, "Migrate")
    production_jobs = jobs(production)
    assert "--project=canary-smoke" in runs(production_jobs["smoke"])
    assert production_jobs["record"]["needs"] == ["deploy", "smoke"]
    assert "placeholder" in str(step(job, "Production configured and a release named?")["run"])


def test_rollback_repoints_the_previous_release_and_never_migrates() -> None:
    job = _job("rollback.yml")
    assert job["timeout-minutes"] == 15
    assert "release-previous" in str(step(job, "The previous release")["run"])
    assert "migrate" not in runs(job).lower()
    assert "alembic upgrade" not in runs(job) and "alembic downgrade" not in runs(job)
    assert "MIGRATE_TASK_DEFINITION" not in text("rollback.yml")
    for name in ("Re-point the workers", "Re-point the API", "Re-point the SPA"):
        assert "steps.previous.outputs" in str(cast(Mapping, step(job, name)["env"]))


def test_ops_tasks_are_the_contracts_allowlist() -> None:
    ops = load("ops-task.yml")
    dispatch = cast(Mapping, triggers(ops)["workflow_dispatch"])
    options = cast(Mapping, cast(Mapping, dispatch["inputs"])["command"])["options"]
    assert set(cast(list[str], options)) == OPS_COMMANDS
    assert cast(Mapping, triggers(ops)["push"])["paths"] == [
        "deploy/production/ops-requests/*.yaml"
    ]
    job = _job("ops-task.yml")
    assert "abacus_tools.release ops-request" in str(step(job, "The requests")["run"])
    assert index(job, "The requests") < index(job, "Take the deploy lock")


# --- Every deploy ------------------------------------------------------------------------------


def test_every_deploy_releases_the_lock_on_every_path_and_never_applies_terraform() -> None:
    for name in DEPLOYS:
        job = _job(name)
        release = step(job, "Release the deploy lock")
        assert str(release["if"]) == "always() && steps.lock.outputs.taken == 'true'", name
        assert "abacus_tools.deploy_lock release" in str(release["run"]), name
        assert "terraform" not in text(name), name


def test_every_action_is_pinned_and_no_long_lived_cloud_secret_is_used() -> None:
    for name in ("build.yml", *DEPLOYS):
        workflow = load(name)
        assert all(PINNED.match(u) for u in uses(workflow)), (name, uses(workflow))
        assert "AWS_SECRET_ACCESS_KEY" not in text(name) and "aws_access_key" not in text(name)


# --- The shared script --------------------------------------------------------------------------


def test_the_spa_goes_assets_then_entry_then_config_then_three_paths() -> None:
    publish = _function("publish_spa")
    assets = publish.index('"$source/firm/assets/"')
    entry = publish.index('"$source/firm/index.html"')
    config = publish.index('runtime-config.json "s3://$WEB_BUCKET/runtime-config.json"')
    invalidate = publish.index("create-invalidation")
    assert assets < entry < config < invalidate
    assert '--paths "/index.html" "/" "/runtime-config.json"' in publish
    assert "--delete" not in publish  # the previous bundle's assets stay for rollback


def test_images_are_named_by_digest_and_services_roll_with_the_circuit_breaker() -> None:
    assert '"$ECR_REPOSITORY@$DIGEST"' in _function("render_task_definition")
    roll = _function("roll_service")
    assert "deploymentCircuitBreaker={enable=true,rollback=true}" in roll
    assert "alarms={alarmNames=[$alarms],enable=true,rollback=true}" in roll
    assert "rolled back" in roll
