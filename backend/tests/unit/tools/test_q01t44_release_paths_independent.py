"""Q-01-T44 (ADR-078): acceptance tests for the deploy, release, rollback and drill paths
(Q-01-T18, T34, T38), from the acceptance text: "Tests prove deploy-lock exclusion, digest-only
references, the staging-verified and Inspector gates, rollback to the previous digest and bundle,
and drill detection of planted mismatches." Same-session authorship in a solo lane (TASK-1236):
independence is nominal. The drill's database half is `tests/integration/test_drill_verify.py`."""

from __future__ import annotations

import re
import threading
import uuid
from collections.abc import Iterator

import pytest

from abacus.kernel.config import settings
from abacus_tools import deploy_lock, drill
from abacus_tools.local import db_guard
from abacus_tools.release import Refused, check, gate

from .workflow_shape import REPO, index, jobs, load, step, steps, text

SHA = "1" * 40
DIGEST = "sha256:" + "2" * 64
RELEASE: dict[str, object] = {
    "git_sha": SHA,
    "image_digest": DIGEST,
    "spa_manifest_sha256": "3" * 64,
    "alembic_head": "0157",
    "openapi_sha256": "4" * 64,
    "infra_sha": "5" * 40,
}
SCRIPT = (REPO / "deploy" / "scripts" / "release.sh").read_text()
CHANGING = (
    "deploy-staging.yml",
    "deploy-production.yml",
    "rollback.yml",
    "ops-task.yml",
    "drill.yml",
)


class AtomicSsm:
    """SSM's PutParameter without overwrite: an atomic create, as the real service is."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._guard = threading.Lock()

    def create(self, name: str, value: str) -> bool:
        with self._guard:
            if name in self._values:
                return False
            self._values[name] = value
            return True

    def read(self, name: str) -> str | None:
        return self._values.get(name)

    def delete(self, name: str) -> None:
        with self._guard:
            self._values.pop(name, None)


# --- Deploy-lock exclusion ---------------------------------------------------------------------


def test_ac_of_two_deploys_racing_for_the_lock_exactly_one_holds_it() -> None:
    ssm = AtomicSsm()
    results: dict[str, bool] = {}
    barrier = threading.Barrier(8)

    def contend(run: str) -> None:
        barrier.wait()
        taken, _ = deploy_lock.take(
            ssm, "staging", holder="deploy-staging", run_ref=run, git_sha=SHA, purpose="deploy"
        )
        results[run] = taken

    threads = [threading.Thread(target=contend, args=(f"run-{n}",)) for n in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(results.values()) == 1
    winner = next(run for run, taken in results.items() if taken)
    held = deploy_lock.current(ssm, "staging")
    assert held is not None and held.run_ref == winner


def test_ac_a_loser_cannot_release_the_winners_lock() -> None:
    ssm = AtomicSsm()
    deploy_lock.take(ssm, "production", holder="a", run_ref="run-a", git_sha=SHA, purpose="deploy")
    assert deploy_lock.release(ssm, "production", run_ref="run-b") is False
    assert deploy_lock.current(ssm, "production") is not None


@pytest.fixture
def local_urls(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for name in db_guard.URLS:
        monkeypatch.setenv(
            f"ABACUS_{name.upper()}", "postgresql+asyncpg://u:p@127.0.0.1:55432/abacus"
        )
    settings.cache_clear()
    yield
    monkeypatch.undo()
    settings.cache_clear()


def test_ac_a_held_lock_stops_db_guard_and_a_free_one_does_not(
    local_urls: None, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    ssm = AtomicSsm()
    monkeypatch.setattr(deploy_lock, "_ssm", lambda: ssm)
    monkeypatch.setenv("ABACUS_DEPLOY_LOCK_ENV", "staging")
    assert db_guard.main() == 0
    deploy_lock.take(
        ssm, "staging", holder="deploy-staging", run_ref="run-1", git_sha=SHA, purpose="deploy"
    )
    assert db_guard.main() == 1
    assert "deploy-staging" in capsys.readouterr().err
    deploy_lock.release(ssm, "staging", run_ref="run-1")
    assert db_guard.main() == 0


def test_ac_each_workflow_that_changes_an_environment_locks_before_its_first_change() -> None:
    first_change = {
        "deploy-staging.yml": "Migrate",
        "deploy-production.yml": "Migrate",
        "rollback.yml": "Re-point the workers",
        "ops-task.yml": "Run each request on the current release image",
        "drill.yml": "Restore into the drill subnet",
    }
    for name in CHANGING:
        job = next(iter(jobs(load(name)).values()))
        assert index(job, "Take the deploy lock") < index(job, first_change[name]), name
        assert str(step(job, "Release the deploy lock")["if"]).startswith("always()"), name
        concurrency = load(name)["concurrency"]
        assert "deploy-" in str(concurrency) and "'cancel-in-progress': False" in str(
            concurrency
        ), name


# --- Digest-only references --------------------------------------------------------------------

_TAG_REFERENCE = re.compile(r"\$ECR_REPOSITORY:[^\s\"']+|abacus-backend:[\w.-]+|:latest\b")


def test_ac_no_deploy_input_names_an_image_by_tag() -> None:
    for name in CHANGING:
        assert not _TAG_REFERENCE.search(text(name)), name
    assert not _TAG_REFERENCE.search(SCRIPT)
    assert '"$ECR_REPOSITORY@$DIGEST"' in SCRIPT
    # The only tag is the build's own immutable `<sha>` tag, used to find a digest already built.
    assert '--tag "$ECR_REPOSITORY:$GITHUB_SHA"' in text("build.yml")


@pytest.mark.parametrize(
    "image",
    [
        "abacus-backend:latest",
        "abacus-backend:" + SHA,
        "000000000000.dkr.ecr.us-east-2.amazonaws.com/abacus-backend:v1",
        "sha256:abc",
    ],
)
def test_ac_a_release_naming_an_image_by_tag_is_refused(image: str) -> None:
    with pytest.raises(Refused):
        check({**RELEASE, "image_digest": image})


# --- The staging-verified and Inspector gates --------------------------------------------------


def _decide(**overrides: object) -> list[str]:
    facts: dict[str, object] = {
        "staging_verified": {"git_sha": SHA, "image_digest": DIGEST, "smoke": "passed"},
        "replay": {"git_sha": SHA, "passed": True},
        "inspector_record": {"image_digest": DIGEST, "promotable": True, "finding_ids": []},
        "current_infra_sha": RELEASE["infra_sha"],
    }
    facts.update(overrides)
    return gate(RELEASE, **facts)  # type: ignore[arg-type]  # test facts


def test_ac_production_refuses_a_release_staging_has_not_verified() -> None:
    assert _decide() == []
    assert "staging_not_verified" in _decide(staging_verified=None)
    # Staging verified the same SHA built into another image: not this release.
    other = {"git_sha": SHA, "image_digest": "sha256:" + "9" * 64, "smoke": "passed"}
    assert "staging_not_verified" in _decide(staging_verified=other)
    red = {"git_sha": SHA, "image_digest": DIGEST, "smoke": "failed"}
    assert "staging_not_verified" in _decide(staging_verified=red)


def test_ac_production_refuses_a_fixable_critical_finding_without_a_recorded_exception() -> None:
    dirty = {"image_digest": DIGEST, "promotable": False, "finding_ids": ["CVE-x"]}
    assert _decide(inspector_record=dirty) == ["inspector_unpromotable"]
    assert _decide(inspector_record=None) == ["inspector_missing"]
    excepted = {
        **RELEASE,
        "inspector_exception": {
            "reason": "no exploit path in our image",
            "finding_ids": ["CVE-x"],
        },
    }
    assert (
        gate(
            excepted,
            staging_verified={"git_sha": SHA, "image_digest": DIGEST, "smoke": "passed"},
            replay={"git_sha": SHA, "passed": True},
            inspector_record=dirty,
            current_infra_sha=None,
        )
        == []
    )


def test_ac_the_production_workflow_runs_the_gate_before_anything_changes() -> None:
    job = next(iter(jobs(load("deploy-production.yml")).values()))
    assert index(job, "Gates") < index(job, "Take the deploy lock") < index(job, "Migrate")
    assert "abacus_tools.release gate" in str(step(job, "Gates")["run"])


# --- Rollback to the previous digest and bundle --------------------------------------------------


def test_ac_rollback_restores_the_previous_digest_and_bundle_without_a_migration() -> None:
    job = next(iter(jobs(load("rollback.yml")).values()))
    previous = str(step(job, "The previous release")["run"])
    assert '"/abacus/$ENV_NAME/release-previous"' in previous
    assert 'echo "digest=$(jq -r .image_digest release.json)"' in previous
    for name in ("Re-point the workers", "Re-point the API"):
        assert step(job, name)["env"] == {"DIGEST": "${{ steps.previous.outputs.digest }}"}
    assert step(job, "Re-point the SPA")["env"] == {
        "GIT_SHA": "${{ steps.previous.outputs.git_sha }}"
    }
    assert 'publish_spa "$GIT_SHA"' in str(step(job, "Re-point the SPA")["run"])
    code = "\n".join(str(s.get("run", "")) for s in steps(job))
    assert "migrate" not in code.lower() and "alembic" not in code.replace("alembic_head", "")
    assert job["timeout-minutes"] == 15
    # The previous bundle still works: deploys never delete hashed assets.
    assert "--delete" not in SCRIPT


# --- Drill detection of planted mismatches -----------------------------------------------------


def test_ac_the_drill_names_a_planted_row_count_mismatch() -> None:
    tenant = uuid.uuid4()
    source = drill.Facts(counts={("evidence_versions", tenant): 3, ("audit_events", tenant): 9})
    restored = drill.Facts(counts={("evidence_versions", tenant): 2, ("audit_events", tenant): 9})
    assert drill.count_mismatches(source, restored) == [
        drill.CountMismatch("evidence_versions", str(tenant), 3, 2)
    ]
    assert drill.count_mismatches(source, source) == []


def test_ac_any_planted_mismatch_fails_the_drill() -> None:
    def report() -> drill.DrillReport:
        return drill.DrillReport(
            "production", "2026-12-08T03:14:00+00:00", "2026-12-08T03:09:00+00:00"
        )

    assert report().passed
    fingerprint = report()
    fingerprint.evidence_mismatches.append(drill.EvidenceMismatch("t", "v", "IntegrityError"))
    gap = report()
    gap.sequence_gaps.append(drill.SequenceGap("t", 41, 1))
    assert not fingerprint.passed and not gap.passed
