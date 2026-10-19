"""AC-20: the protected-path hooks block what they must, allow what they must, and fail closed.

Each test copies `.claude/hooks/` into a temporary project so real approval files never leak in,
and runs the hooks under every available interpreter — including the system `python3`, which is
what Claude Code invokes (on macOS it is 3.9; a crash there once disabled every hook silently).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[4]
HOOKS = REPO / ".claude" / "hooks"
SYSTEM_PYTHON = Path("/usr/bin/python3")
INTERPRETERS = [pytest.param(sys.executable, id="venv")] + (
    [pytest.param(str(SYSTEM_PYTHON), id="system")] if SYSTEM_PYTHON.exists() else []
)
APPROVAL = "task: TASK-T\napproved_by: founder\nexpires: 2999-01-01\npaths:\n{paths}"

Run = Callable[[str, dict[str, object]], int]


@pytest.fixture(params=INTERPRETERS)
def project(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Path, Run]:
    shutil.copytree(HOOKS, tmp_path / ".claude" / "hooks")
    (tmp_path / "AGENTS.md").write_text("constitution\n", encoding="utf-8")
    python = str(request.param)

    def run(hook: str, tool_input: dict[str, object]) -> int:
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)}
        result = subprocess.run(
            [python, str(tmp_path / ".claude" / "hooks" / hook)],
            input=json.dumps({"tool_input": tool_input}),
            capture_output=True,
            text=True,
            env=env,
            check=False,
        )
        return result.returncode

    return tmp_path, run


def _edit(project: tuple[Path, Run], rel: str) -> int:
    root, run = project
    return run("protect_paths.py", {"file_path": str(root / rel)})


def _bash(project: tuple[Path, Run], command: str) -> int:
    return project[1]("guard_bash.py", {"command": command})


def _approve(root: Path, *paths: str) -> None:
    approvals = root / "work" / "approvals"
    approvals.mkdir(parents=True, exist_ok=True)
    body = "".join(f"  - {p}\n" for p in paths)
    (approvals / "TASK-T.yaml").write_text(APPROVAL.format(paths=body), encoding="utf-8")


@pytest.mark.parametrize(
    "rel",
    [
        "AGENTS.md",
        "agents.md",
        "Makefile",
        "backend/Makefile",
        ".claude/settings.json",
        ".CLAUDE/settings.json",
        ".claude/hooks/_protected.py",
        ".github/CODEOWNERS",
        ".git/hooks/pre-commit",
        ".gitignore",
        "pnpm-workspace.yaml",
        "packages/ui/package.json",
        "apps/web/.npmrc",
        "backend/pyproject.toml",
        "backend/src/abacus_tools/quality/banned_patterns.py",
        "backend/tests/unit/quality/test_hooks.py",
        "backend/src/abacus/kernel/uow/core.py",
        "backend/src/abacus/modules/identity/authz/policy.py",
        "work/approvals/TASK-X.yaml",
        "docs/product/failure-taxonomy.md",
        "../outside.txt",
    ],
)
def test_ac20_protected_path_is_blocked(project: tuple[Path, Run], rel: str) -> None:
    assert _edit(project, rel) == 2


@pytest.mark.parametrize(
    "rel",
    [
        "backend/src/abacus/modules/sampling/service.py",
        "backend/src/abacus/kernel/outbox/relay.py",
        "docs/adr/ADR-200-new.md",
        "docs/adr/drafts/ADR-1.md",
        "docs/specs/SPEC-001-new.md",
        "..notes.md",
    ],
)
def test_ac20_unprotected_path_is_allowed(project: tuple[Path, Run], rel: str) -> None:
    assert _edit(project, rel) == 0


def test_ac20_existing_adr_is_immutable(project: tuple[Path, Run]) -> None:
    adr = project[0] / "docs" / "adr" / "ADR-001-x.md"
    adr.parent.mkdir(parents=True)
    adr.write_text("---\n", encoding="utf-8")
    assert _edit(project, "docs/adr/ADR-001-x.md") == 2


def test_ac20_symlink_to_protected_file_is_blocked(project: tuple[Path, Run]) -> None:
    root = project[0]
    (root / "notes.md").symlink_to(root / "AGENTS.md")
    assert _edit(project, "notes.md") == 2


def test_ac20_approval_unblocks_exactly_its_paths(project: tuple[Path, Run]) -> None:
    _approve(
        project[0], "AGENTS.md  # with a trailing comment", "backend/src/abacus/kernel/uow/**"
    )
    assert _edit(project, "AGENTS.md") == 0
    assert _edit(project, "backend/src/abacus/kernel/uow/deep/core.py") == 0
    assert _edit(project, "Makefile") == 2
    assert _edit(project, "backend/src/abacus/kernel/db/engine.py") == 2


@pytest.mark.parametrize(
    "approval",
    [
        "task: T\napproved_by: founder\nexpires: 2000-01-01\npaths:\n  - AGENTS.md\n",
        "task: T\napproved_by: founder\nexpires: never\npaths:\n  - AGENTS.md\n",
        "task: T\napproved_by: agent\nexpires: 2999-01-01\npaths:\n  - AGENTS.md\n",
        "task: T\napproved_by: founder\nexpires: 2999-01-01\npaths:\n  - '**'\n",
        "task: T\napproved_by: founder\nexpires: 2999-01-01\npaths:\n  - '*'\n",
        "task: T\napproved_by: founder\nexpires: 2999-01-01\nnotes:\n  - AGENTS.md\npaths:\n",
    ],
    ids=["expired", "not-a-date", "not-founder", "double-star", "star", "not-under-paths"],
)
def test_ac20_invalid_approval_does_not_unblock(project: tuple[Path, Run], approval: str) -> None:
    approvals = project[0] / "work" / "approvals"
    approvals.mkdir(parents=True)
    (approvals / "TASK-T.yaml").write_text(approval, encoding="utf-8")
    assert _edit(project, "AGENTS.md") == 2


def test_ac20_edit_hook_fails_closed_on_bad_input(project: tuple[Path, Run]) -> None:
    root = project[0]
    hook = root / ".claude" / "hooks" / "protect_paths.py"
    bad_json = subprocess.run(
        [sys.executable, str(hook)], input="{not json", capture_output=True, text=True, check=False
    )
    assert bad_json.returncode == 2


def test_ac20_edit_hook_fails_closed_when_rules_crash(project: tuple[Path, Run]) -> None:
    (project[0] / ".claude" / "hooks" / "_protected.py").write_text("def broken(:\n")
    assert _edit(project, "backend/src/abacus/modules/ledger/service.py") == 2


@pytest.mark.parametrize(
    "command",
    [
        "echo x > AGENTS.md",
        "echo x >> agents.md",
        "python3 -c \"open('AGENTS.md', 'w')\"",
        "perl -pi -e 's/a/b/' Makefile",
        "ln -s AGENTS.md notes.md",
        "git checkout -- .github/CODEOWNERS",
        "cp /tmp/x .git/hooks/pre-commit",
        "sed -i '' 's/a/b/' backend/src/abacus/kernel/uow/core.py",
        "git push --force origin feature",
        "git push --force origin main",
        "uv add requests",
        "git checkout --theirs packages/api-client/openapi.json",
        "git checkout --ours -- backend/src/abacus/kernel/_flags.py",
        "git checkout --theirs backend/tests/durations.json",
    ],
)
def test_ac20_risky_shell_command_is_blocked(project: tuple[Path, Run], command: str) -> None:
    assert _bash(project, command) == 2


@pytest.mark.parametrize(
    "command",
    [
        "ls -la",
        "make check-fast",
        "cat .github/CODEOWNERS",
        'git commit -m "routes -> service; Makefile untouched"',
        "git push -u origin task-001-scaffolding",
        # The founder pushes straight to main (2026-10-19); force pushes stay blocked.
        "git push origin main",
        "git push origin HEAD:refs/heads/main",
        "git checkout --theirs apps/web/src/router.tsx",
        "git clone https://github.com/x/abacus.git > /dev/null",
        "uv run pytest tests/unit",
    ],
)
def test_ac20_ordinary_shell_command_is_allowed(project: tuple[Path, Run], command: str) -> None:
    assert _bash(project, command) == 0


def test_ac20_bash_hook_fails_closed_on_bad_input(project: tuple[Path, Run]) -> None:
    hook = project[0] / ".claude" / "hooks" / "guard_bash.py"
    result = subprocess.run(
        [sys.executable, str(hook)], input="{not json", capture_output=True, text=True, check=False
    )
    assert result.returncode == 2


# --- generated files (F-01-T09) ---------------------------------------------------------------


@pytest.mark.parametrize(
    "rel",
    [
        "packages/api-client/openapi.json",
        "packages/api-client/src/sdk.gen.ts",
        "backend/src/abacus/modules/identity/authz/_matrix.py",
        "backend/src/abacus/kernel/_flags.py",
        "backend/src/abacus/kernel/_provider_terms.py",
        "backend/src/abacus/modules/agents/specs/_specs.py",
        "backend/src/abacus/ai_gateway/_eval_suites.py",
        "backend/tests/durations.json",
        "backend/tests/workflows/histories/retrieval-v1.json",
    ],
)
def test_a_generated_file_is_never_edited_by_hand(project: tuple[Path, Run], rel: str) -> None:
    _approve(project[0], rel)
    assert _edit(project, rel) == 2


@pytest.mark.parametrize(
    "rel",
    ["packages/api-client/package.json", "backend/src/abacus/kernel/flags.py"],
)
def test_a_generated_files_neighbour_is_not_generated(project: tuple[Path, Run], rel: str) -> None:
    root = project[0]
    message = subprocess.run(
        [sys.executable, str(root / ".claude" / "hooks" / "protect_paths.py")],
        input=json.dumps({"tool_input": {"file_path": str(root / rel)}}),
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(root)},
        check=False,
    ).stderr
    assert "generated" not in message


# --- session context (F-01-T09) ---------------------------------------------------------------


def _session(project: tuple[Path, Run], env: dict[str, str] | None = None) -> tuple[int, str]:
    root = project[0]
    result = subprocess.run(
        [sys.executable, str(root / ".claude" / "hooks" / "session_context.py")],
        capture_output=True,
        text=True,
        env={**os.environ, "CLAUDE_PROJECT_DIR": str(root), **(env or {})},
        check=False,
    )
    return result.returncode, result.stdout


def test_session_context_never_blocks_outside_a_repository(project: tuple[Path, Run]) -> None:
    code, out = _session(project)
    assert code == 0
    assert "git state unavailable" in out
    assert "port offset: 0" in out
    assert "HANDOFF_VERSION not set" in out


def test_session_context_names_the_branch_task_and_offset(project: tuple[Path, Run]) -> None:
    root = project[0]
    git = shutil.which("git")
    assert git is not None
    for args in (
        ["init", "-q", "-b", "task-123-thing"],
        [
            "-c",
            "user.email=t@example.com",
            "-c",
            "user.name=t",
            "commit",
            "-q",
            "--allow-empty",
            "-m",
            "x",
        ],
    ):
        subprocess.run([git, *args], cwd=root, check=True, capture_output=True)
    tasks = root / "work" / "tasks"
    tasks.mkdir(parents=True)
    (tasks / "TASK-123-thing.md").write_text("---\nid: TASK-123\nstatus: in-progress\n---\n")
    (root / ".worktree.env").write_text("COMPOSE_PROJECT_NAME=abacus-x\nABACUS_PORT_OFFSET=10\n")
    code, out = _session(project, {"ABACUS_PORT_OFFSET": ""})
    assert code == 0
    assert "branch: task-123-thing" in out
    assert "work/tasks/TASK-123-thing.md (status: in-progress)" in out
    assert "no origin/main ref" in out
    assert "port offset: 10" in out
