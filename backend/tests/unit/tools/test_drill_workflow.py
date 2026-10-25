"""Q-01-T38 (Q-01 F9): drill.yml's shape. It is dispatched by hand only; it shares the
environment's deploy concurrency group and takes the deploy lock before it restores; the restore
is a private, single-AZ instance named `abacus-drill-<run>` in the drill subnet; the verification
is `abacus_tools.drill verify` as an ops task; timings are recorded; and the instance is deleted
and the lock released on every path. Read from the file, never run."""

from __future__ import annotations

from typing import cast

from .workflow_shape import PINNED, index, jobs, load, runs, step, steps, text, triggers, uses

WORKFLOW = load("drill.yml")
JOB = jobs(WORKFLOW)["drill"]


def test_it_is_dispatched_by_hand_only() -> None:
    assert set(triggers(WORKFLOW)) == {"workflow_dispatch"}
    inputs = cast(
        dict[str, object],
        cast(dict[str, object], triggers(WORKFLOW)["workflow_dispatch"])["inputs"],
    )
    assert set(inputs) == {"environment", "restore_point"}


def test_it_never_overlaps_a_deploy_of_the_same_environment() -> None:
    concurrency = cast(dict[str, object], WORKFLOW["concurrency"])
    assert concurrency == {
        "group": "deploy-${{ inputs.environment }}",
        "cancel-in-progress": False,
    }
    lock = step(JOB, "Take the deploy lock")
    assert "abacus_tools.deploy_lock take" in str(lock["run"])
    assert "--purpose ops-task" in str(lock["run"])
    assert index(JOB, "Take the deploy lock") < index(JOB, "Restore into the drill subnet")


def test_the_restore_is_private_and_in_the_drill_subnet() -> None:
    script = str(step(JOB, "Restore into the drill subnet")["run"])
    for flag in (
        "restore-db-instance-to-point-in-time",
        '--target-db-instance-identifier "$INSTANCE"',
        '--db-subnet-group-name "$DRILL_SUBNET_GROUP"',
        "--no-publicly-accessible",
        "--no-multi-az",
    ):
        assert flag in script
    env = cast(dict[str, str], JOB["env"])
    assert env["INSTANCE"] == "abacus-drill-${{ github.run_id }}"


def test_a_random_point_in_the_last_seven_days_no_later_than_the_latest_restorable() -> None:
    script = str(step(JOB, "Choose the restore point")["run"])
    assert "LatestRestorableTime" in script and "7 * 86400" in script and "shuf" in script
    assert "rpo_lag_seconds" in script


def test_verification_is_the_drill_tool_as_an_ops_task() -> None:
    script = str(step(JOB, "Verify as an ops task")["run"])
    assert "aws ecs run-task" in script and '"abacus_tools.drill"' in script
    assert (
        '"verify"' in script and '"--restored-host"' in script and '"--rpo-lag-seconds"' in script
    )
    assert "assignPublicIp=DISABLED" in script


def test_timings_are_recorded_without_data() -> None:
    record = step(JOB, "Record the timings")
    assert str(record["if"]).startswith("always()")
    script = str(record["run"])
    for field in ("restore_started_at", "available_at", "verified_at", "rpo_lag_seconds"):
        assert field in script
    assert "GITHUB_STEP_SUMMARY" in script


def test_the_instance_is_deleted_and_the_lock_released_on_every_path() -> None:
    delete = step(JOB, "Delete the drill instance")
    assert str(delete["if"]) == "always() && steps.restore.outputs.created == 'true'"
    assert "abacus-drill-*" in str(delete["run"])  # never anything else
    assert "--skip-final-snapshot" in str(delete["run"])
    release = step(JOB, "Release the deploy lock")
    assert str(release["if"]) == "always() && steps.lock.outputs.taken == 'true'"
    assert "abacus_tools.deploy_lock release" in str(release["run"])
    assert index(JOB, "Delete the drill instance") < index(JOB, "Release the deploy lock")


def test_a_failed_verification_fails_the_run() -> None:
    names = [s.get("name") for s in steps(JOB)]
    assert names[-1] == "The drill passed"
    assert 'EXIT_CODE" != "0"' in str(step(JOB, "The drill passed")["run"])


def test_no_secret_no_terraform_and_every_action_pinned() -> None:
    assert "secrets." not in text("drill.yml")
    assert "terraform" not in runs(JOB)
    assert all(PINNED.match(u) for u in uses(WORKFLOW)), uses(WORKFLOW)
    assert cast(dict[str, str], JOB["permissions"]) == {"contents": "read", "id-token": "write"}
