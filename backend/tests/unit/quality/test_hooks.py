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
        "backend/src/abacus/modules/ledger/service.py",
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
        "git push origin main",
        "git push origin HEAD:refs/heads/main",
        "git push --force origin feature",
        "uv add requests",
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
