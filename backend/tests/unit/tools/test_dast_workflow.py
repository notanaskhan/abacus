"""Q-03-T004 (QD-9; DEC-366): the weekly DAST baseline scans staging with the allowlisted,
digest-pinned ZAP image, never while a staging deploy is in flight, under the deploy lock; it
prints counts only, keeps the report encrypted, and a high alert opens a SEV3 ticket."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

from abacus_tools.quality.check_dependencies import (
    _PINNED,  # pyright: ignore[reportPrivateUsage]  # the checker's own digest pin
)

REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"

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


def _uses(job: Job) -> list[str]:
    return [str(s["uses"]) for s in _steps(job) if "uses" in s]


def test_t004_the_zap_image_is_allowlisted_and_pinned_by_digest() -> None:
    image = cast(dict[str, str], _load("dast.yml")["env"])["ZAP_IMAGE"]
    pinned = _PINNED.match(image)
    assert pinned is not None, image
    allowlist = cast(
        dict[str, object],
        yaml.safe_load((REPO / "docs/architecture/dependency-allowlist.yaml").read_text()),
    )
    assert cast(dict[str, str], allowlist["containers"])[pinned["name"]] == "approved"


def test_t004_dast_runs_weekly_on_staging_only_when_turned_on() -> None:
    assert _triggers("dast.yml")["schedule"] == [{"cron": "0 10 * * 2"}]
    jobs = _jobs("dast.yml")
    assert jobs["preflight"]["if"] == "vars.STAGING_DAST == 'on'"
    job = jobs["baseline"]
    assert job["needs"] == ["preflight"]
    assert job["if"] == "needs.preflight.outputs.proceed == 'true'"
    env = cast(dict[str, str], job["env"])
    assert env["TARGET"] == "${{ vars.ABACUS_STAGING_URL }}"
    assert 'zap-baseline.py -t "$TARGET"' in _runs(job)
    for forbidden in ("zap-full-scan", "zap-api-scan", "make seed", "migrate", "secrets."):
        assert forbidden not in (WORKFLOWS / "dast.yml").read_text(), forbidden


def test_t004_dast_never_runs_during_a_deploy_and_holds_the_deploy_lock() -> None:
    raw = _load("dast.yml")
    # The lock is the scan job's, never the workflow's: a run that is off, or that finds a deploy
    # running or queued, never joins the group (where it could replace a queued deploy).
    assert "concurrency" not in raw
    jobs = _jobs("dast.yml")
    assert "concurrency" not in jobs["preflight"]
    assert jobs["baseline"]["concurrency"] == {
        "group": "staging-deploy",
        "cancel-in-progress": False,
    }
    check = _runs(jobs["preflight"])
    assert "set -euo pipefail" in check
    assert "gh run list" in check and "deploy-staging.yml" in check
    assert "|| echo" not in check  # a failed lookup stops the scan (fails closed)
    assert 'echo "proceed=true"' in check
    outputs = cast(dict[str, str], jobs["preflight"]["outputs"])
    assert outputs["proceed"] == "${{ steps.lock.outputs.proceed }}"


def test_t004_only_counts_are_public_and_the_report_is_encrypted() -> None:
    job = _jobs("dast.yml")["baseline"]
    runs = _runs(job)
    assert '> "$WRK/zap.log" 2>&1' in runs  # ZAP's own output never reaches the public log
    assert "python -m abacus_tools.quality.dast" in runs
    assert "gpg --batch" in runs and "--encrypt" in runs
    assert 'rm -rf "$RUNNER_TEMP/zap"' in runs
    uploads = [s for s in _steps(job) if str(s.get("uses", "")).startswith("actions/upload")]
    assert [cast(dict[str, str], s["with"])["path"] for s in uploads] == [
        "${{ runner.temp }}/dast-report"
    ]


def test_t004_a_high_alert_opens_a_sev3_ticket_and_fails_the_run() -> None:
    jobs = _jobs("dast.yml")
    baseline = jobs["baseline"]
    assert cast(dict[str, str], baseline["outputs"])["high"] == "${{ steps.triage.outputs.high }}"
    last = _steps(baseline)[-1]
    assert "exit 1" in str(last["run"])
    # Step outputs reach the shell through env, never interpolated into the script.
    assert "${{" not in str(last["run"])
    assert cast(dict[str, str], last["env"])["HIGH"] == "${{ steps.triage.outputs.high }}"
    ticket = jobs["sev3"]
    assert ticket["needs"] == ["baseline"]
    assert ticket["permissions"] == {"issues": "write"}
    runs = _runs(ticket)
    assert "--label sev3" in runs and "gh issue comment" in runs
    assert "$HIGH" in runs and "$RUN_URL" in runs
    assert cast(dict[str, str], _steps(ticket)[0]["env"])["HIGH"] == (
        "${{ needs.baseline.outputs.high }}"
    )


def test_t004_dast_pins_its_actions_and_uses_no_secrets() -> None:
    assert "secrets." not in (WORKFLOWS / "dast.yml").read_text()
    assert _load("dast.yml")["permissions"] == {"contents": "read"}
    for job in _jobs("dast.yml").values():
        for uses in _uses(job):
            assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", uses), uses
