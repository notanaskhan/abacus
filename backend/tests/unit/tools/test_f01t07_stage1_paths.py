"""F-01-T07 (TASK-7823): stage 1 runs only the gates a diff can affect.

Acceptance (the row): "A frontend-only PR completes required checks in 6 minutes or less without
running backend shards, while agent-path diffs still trigger evals-fast." Stage 2's shards already
report success without running on a frontend-only diff (F-05-T62's tests); this file holds stage 1
to the same classifier: `make check-fast` (17.5 minutes on PR #1801) runs only when the diff has a
backend or unknown path, a frontend-only diff runs `make check-fast-frontend` and the docs checks,
and a prose-only diff runs the docs checks. The timing itself is measured on the next frontend-only
pull request.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, cast

import yaml

REPO = Path(__file__).resolve().parents[4]
CI = REPO / ".github" / "workflows" / "ci.yml"
MAKEFILE = REPO / "Makefile"
Json = dict[str, Any]  # a parsed YAML mapping (ci.yml): its values are untyped by nature


def _stage1_steps() -> list[Json]:
    jobs = cast(Json, yaml.safe_load(CI.read_text(encoding="utf-8")))["jobs"]
    return cast(list[Json], jobs["stage-1"]["steps"])


def _gate(run: str) -> str:
    [step] = [s for s in _stage1_steps() if s.get("run") == run]
    return str(step.get("if", ""))


def _target(name: str) -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    found = re.search(rf"^{re.escape(name)}:.*?\n((?:\t.*\n|#.*\n)+)", text, re.MULTILINE)
    assert found is not None, name
    return found.group(1)


def test_ac_stage1_classifies_the_diff_with_the_stage2_classifier() -> None:
    [paths] = [s for s in _stage1_steps() if s.get("id") == "paths"]
    assert "abacus_tools.ci.paths" in str(paths["run"])
    assert "GITHUB_OUTPUT" in str(paths["run"])
    # Fail closed (TASK-7828): bash is -eo pipefail, so a crashed classifier fails the step.
    assert paths["shell"] == "bash"
    base = str(cast(Json, paths["env"])["BASE"])
    assert "pull_request.base.sha" in base and "merge_group.base_sha" in base
    assert "event.before" in base


def test_ac_backend_gates_run_only_for_a_backend_or_unknown_diff() -> None:
    # Only an explicit `backend=false` skips them: empty (a crashed classifier) runs everything.
    assert _gate("make check-fast") == "steps.paths.outputs.backend != 'false'"
    assert _gate("make setup") == "steps.paths.outputs.backend != 'false'"


def test_ac_a_frontend_only_diff_runs_the_frontend_half_and_the_docs() -> None:
    frontend = "steps.paths.outputs.backend == 'false' && steps.paths.outputs.frontend == 'true'"
    assert _gate("make check-fast-frontend") == frontend
    assert _gate("pnpm install --frozen-lockfile && pnpm -C packages/api-client build:types") == (
        frontend
    )
    assert _gate("make check-docs") == "steps.paths.outputs.backend == 'false'"
    assert _gate("cd backend && uv sync --frozen") == "steps.paths.outputs.backend == 'false'"


def test_ac_check_fast_still_runs_the_frontend_half() -> None:
    assert "$(MAKE) check-fast-frontend" in _target("check-fast")
    half = _target("check-fast-frontend")
    for gate in (
        "pnpm -C apps/web exec tsc --noEmit",
        "pnpm -C packages/ui exec tsc --noEmit",
        "vite build",
        "check-compiled-css.js",
        "bundle-budget.mjs",
    ):
        assert gate in half, gate
    docs = _target("check-docs")
    # TASK-7828: the gates a frontend or prose file can trip run whenever check-fast does not.
    for gate in (
        "abacus_tools.quality.validate_docs",
        "abacus_tools.quality.register_ids",
        "abacus_tools.quality.secrets_scan",
        "abacus_tools.quality.seed_contamination",
        "abacus_tools.quality.scope_guards",
        "abacus_tools.quality.quarantine",
        "$(MAKE) check-generated",
    ):
        assert gate in docs, gate
        assert gate in _target("check-fast") or gate == "$(MAKE) check-generated", gate
    assert "abacus_tools.quality.validate_docs" in _target("check-fast")


def test_stage2_classifier_also_fails_closed() -> None:
    jobs = cast(Json, yaml.safe_load(CI.read_text(encoding="utf-8")))["jobs"]
    [paths] = [s for s in cast(list[Json], jobs["changes"]["steps"]) if s.get("id") == "paths"]
    assert paths["shell"] == "bash"
