"""F-05-T62: independent acceptance tests (ADR-078) for the CI frontend job (F-05-T17).

Written from the acceptance criteria, not from the implementation: "Tests prove a frontend-only
diff skips backend shards, an over-budget firm, portal or route chunk fails, and each compiled-CSS
rule rejects its deny case, and they pass unedited on main." This file is the path-filter half: it
runs `python -m abacus_tools.ci.paths <base> <head>` as CI does, over real commits in a scratch
repository, and reads `.github/workflows/ci.yml` to prove each backend shard is gated on the
`backend` output. The budget and compiled-CSS halves run the real scripts as processes in
`apps/web/src/lint/f05-t62-ci-frontend.test.ts`.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

import pytest
import yaml

REPO = Path(__file__).resolve().parents[4]
CI = REPO / ".github" / "workflows" / "ci.yml"
BACKEND_SRC = REPO / "backend" / "src"

Json = dict[str, Any]  # a parsed YAML mapping (ci.yml): its values are untyped by nature

# The stage 2 jobs that run backend suites, and the stage 2 job that runs the SPA's.
BACKEND_JOBS = ("unit", "integration", "contracts")
FRONTEND_JOB = "frontend"


def _git(repo: Path, *args: str) -> str:
    git = shutil.which("git")
    assert git is not None
    out = subprocess.run([git, *args], cwd=repo, capture_output=True, text=True, check=True)
    return out.stdout.strip()


def _outputs(repo: Path, base: str, head: str) -> dict[str, str]:
    """The `name=value` lines CI appends to $GITHUB_OUTPUT, from the module CI runs."""
    env = {**os.environ, "PYTHONPATH": str(BACKEND_SRC)}
    out = subprocess.run(
        [sys.executable, "-m", "abacus_tools.ci.paths", base, head],
        cwd=repo,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    return dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "t")
    (tmp_path / "README.md").write_text("base\n")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def _commit(repo: Path, files: dict[str, str]) -> tuple[str, str]:
    base = _git(repo, "rev-parse", "HEAD")
    for name, text in files.items():
        path = repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "change")
    return base, _git(repo, "rev-parse", "HEAD")


def test_a_frontend_only_diff_skips_the_backend_shards(repo: Path) -> None:
    base, head = _commit(
        repo,
        {
            "apps/web/src/screens/X/index.tsx": "export {};\n",
            "packages/ui/src/templates/x.tsx": "export {};\n",
        },
    )
    out = _outputs(repo, base, head)
    assert out["backend"] == "false"
    assert out["frontend"] == "true"
    assert out["gallery"] == "true"


def test_an_app_only_diff_runs_the_frontend_job_but_not_the_gallery(repo: Path) -> None:
    base, head = _commit(repo, {"apps/web/src/screens/X/copy.ts": "export {};\n"})
    out = _outputs(repo, base, head)
    assert (out["backend"], out["frontend"], out["gallery"]) == ("false", "true", "false")


@pytest.mark.parametrize(
    "path",
    ["backend/src/abacus/kernel/x.py", "infra/main.tf", "Makefile", "docs/product/x.yaml"],
)
def test_a_diff_touching_anything_else_runs_the_backend_shards(repo: Path, path: str) -> None:
    base, head = _commit(repo, {"apps/web/src/a.ts": "export {};\n", path: "x\n"})
    assert _outputs(repo, base, head)["backend"] == "true"


def test_an_unknown_base_runs_everything(repo: Path) -> None:
    out = _outputs(repo, "0" * 40, "HEAD")
    assert set(out.values()) == {"true"}


def _workflow() -> Json:
    return cast("dict[str, Any]", yaml.safe_load(CI.read_text()))


def _gated_on(job: Json, output: str) -> bool:
    """Every step that does work runs only when `output` is true; the others only say so."""
    steps = cast("list[dict[str, Any]]", job["steps"])
    on, off = (
        f"needs.changes.outputs.{output} == 'true'",
        f"needs.changes.outputs.{output} != 'true'",
    )
    working = [s for s in steps if "uses" in s or "run" in s]
    assert working, "a job with no steps"
    for step in working:
        cond = str(step.get("if", ""))
        if off in cond:
            assert "make" not in str(step.get("run", "")), "a skip step must not run a suite"
            continue
        if on not in cond:
            return False
    return True


@pytest.mark.parametrize("name", BACKEND_JOBS)
def test_each_backend_shard_runs_only_when_backend_paths_changed(name: str) -> None:
    jobs = cast("dict[str, Any]", _workflow()["jobs"])
    job = cast("dict[str, Any]", jobs[name])
    assert "changes" in job["needs"]
    assert _gated_on(job, "backend"), f"{name} runs a step without the backend gate"


def test_the_frontend_job_runs_the_spa_suites_when_frontend_paths_changed() -> None:
    jobs = cast("dict[str, Any]", _workflow()["jobs"])
    job = cast("dict[str, Any]", jobs[FRONTEND_JOB])
    assert _gated_on(job, "frontend")
    runs = " ".join(str(s.get("run", "")) for s in job["steps"])
    assert "make ci-frontend" in runs
    # The frontend job never needs a database or the backend's suites.
    assert "services" not in job
    assert "ci-unit" not in runs and "ci-integration" not in runs


def test_the_frontend_job_has_no_database() -> None:
    makefile = (REPO / "Makefile").read_text()
    recipe = makefile.split("\nci-frontend:\n", 1)[1].split("\n\n", 1)[0]
    assert "pytest" not in recipe and "migrate" not in recipe and "DATABASE" not in recipe


def test_the_gallery_job_runs_on_component_library_changes() -> None:
    jobs = cast("dict[str, Any]", _workflow()["jobs"])
    assert _gated_on(cast("dict[str, Any]", jobs["gallery"]), "gallery")
