"""Q-03-T029 (DEC-366): the security stage adds bandit and the base-image scan, skips a
registered finding only while it is inside its SLA, and fails once one is past it; its actions are
pinned and it uses no secret."""

from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import yaml

REPO = Path(__file__).resolve().parents[4]
WORKFLOWS = REPO / ".github" / "workflows"

Job = dict[str, object]


def _load(name: str) -> dict[str, object]:
    return cast(dict[str, object], yaml.safe_load((WORKFLOWS / name).read_text()))


def _jobs(name: str) -> dict[str, Job]:
    return cast(dict[str, Job], _load(name)["jobs"])


def _steps(job: Job) -> list[dict[str, object]]:
    return cast(list[dict[str, object]], job.get("steps", []))


def _runs(job: Job) -> str:
    return "\n".join(str(s.get("run", "")) for s in _steps(job))


def _uses(job: Job) -> list[str]:
    return [str(s["uses"]) for s in _steps(job) if "uses" in s]


def test_t029_security_adds_bandit_the_base_image_and_the_sla_check() -> None:
    jobs = _jobs("security.yml")
    assert "uv run bandit -q -r src --severity-level high" in _runs(jobs["bandit"])
    image = jobs["trivy-image"]
    assert "ARG PYTHON_IMAGE=" in _runs(image)
    scan = next(s for s in _steps(image) if str(s.get("uses", "")).startswith("aquasecurity/"))
    settings = cast(dict[str, str], scan["with"])
    assert settings["scan-type"] == "image"
    assert settings["image-ref"] == "${{ steps.base.outputs.image }}"
    sla = _runs(jobs["findings-sla"])
    assert "supply_chain check" in sla
    assert 'supply_chain check --base-register "$REGISTER"' in sla


def test_t029_scanners_skip_only_registered_findings_inside_their_sla() -> None:
    jobs = _jobs("security.yml")
    pip = _runs(jobs["pip-audit"])
    assert 'supply_chain ignores --tool pip-audit --register "$REGISTER"' in pip
    assert "$PIP_AUDIT_IGNORES" in pip
    for name in ("trivy", "trivy-image"):
        job = jobs[name]
        assert 'supply_chain ignores --tool trivy --register "$REGISTER"' in _runs(job)
        scan = next(s for s in _steps(job) if str(s.get("uses", "")).startswith("aquasecurity/"))
        assert cast(dict[str, str], scan["with"])["trivyignores"] == (
            "${{ runner.temp }}/trivyignore"
        )


def test_security_scan_workflows_pin_actions_and_use_no_secrets() -> None:
    for name in (
        ("dast.yml", "security.yml") if (WORKFLOWS / "dast.yml").exists() else ("security.yml",)
    ):
        text = (WORKFLOWS / name).read_text()
        assert "secrets." not in text, name
        assert _load(name)["permissions"] == {"contents": "read"}, name
        for job in _jobs(name).values():
            for uses in _uses(job):
                assert re.fullmatch(r"[\w./-]+@[0-9a-f]{40}", uses), (name, uses)


def test_t029_on_a_pull_request_the_base_register_decides() -> None:
    jobs = _jobs("security.yml")
    for name in ("pip-audit", "trivy", "trivy-image", "findings-sla"):
        job = jobs[name]
        env = cast(dict[str, str], job["env"])
        assert env["BASE"].startswith("${{ github.event.pull_request.base.sha"), name
        checkout = _steps(job)[0]
        assert cast(dict[str, object], checkout["with"])["fetch-depth"] == 0, name
        runs = _runs(job)
        assert 'git show "$BASE:docs/quality/supply-chain-findings.yaml"' in runs, name
        assert "printf 'findings: []\\n'" in runs, name  # a base without one waives nothing
