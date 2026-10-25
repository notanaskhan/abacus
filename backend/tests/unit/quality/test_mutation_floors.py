"""Q-03-T027 (QD-4; ADR-079; DEC-365): a change lowering any mutation floor is refused by the hook
and by CI. The hook runs under every available interpreter, as in test_hooks.py: Claude Code
invokes the system `python3` (3.9 on macOS)."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from types import ModuleType

import pytest

from abacus_tools.quality import mutation_floors
from abacus_tools.quality.mutation import SCOPES

REPO = Path(__file__).resolve().parents[4]
HOOKS = REPO / ".claude" / "hooks"
SYSTEM_PYTHON = Path("/usr/bin/python3")
INTERPRETERS = [pytest.param(sys.executable, id="venv")] + (
    [pytest.param(str(SYSTEM_PYTHON), id="system")] if SYSTEM_PYTHON.exists() else []
)
REL = "backend/mutation-thresholds.yaml"
BASE = "schema: 1\nfloors:\n  identity/authz: 85\n  evidence: 75\n"

Run = Callable[[str, Mapping[str, object]], int]


def _hook_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("_protected_under_test", HOOKS / "_protected.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --- the guard (CI) -------------------------------------------------------------------------


def test_t027_the_committed_file_lists_every_scope_and_parses_in_both_parsers() -> None:
    text = mutation_floors.FILE.read_text(encoding="utf-8")
    floors = mutation_floors.parse(text)
    assert set(floors) == set(SCOPES)
    assert _hook_module().parse_floors(text) == floors


@pytest.mark.parametrize(
    "text",
    [
        BASE,
        BASE + "  # a comment\n\n  compute: 0  # trailing\n",
        "floors:\n  kernel/db: 100\n",
    ],
)
def test_t027_the_hook_parser_agrees_with_the_guard(text: str) -> None:
    assert _hook_module().parse_floors(text) == mutation_floors.parse(text)


@pytest.mark.parametrize(
    "text",
    [
        "schema: 1\n",
        "floors:\n  evidence: 101\n",
        "floors:\n  evidence: 75\n  evidence: 80\n",
        "floors:\n  evidence: 0.75\n",
        "floors:\n    evidence: 75\n",
        "floors: {evidence: 75}\n",
        "floors:\n  Evidence: 75\n",
    ],
)
def test_t027_both_parsers_refuse_a_file_outside_the_format(text: str) -> None:
    with pytest.raises(mutation_floors.FloorsInvalid):
        mutation_floors.parse(text)
    with pytest.raises(ValueError):
        _hook_module().parse_floors(text)


def test_t027_ci_refuses_a_lowered_floor() -> None:
    head = BASE.replace("evidence: 75", "evidence: 70")
    assert mutation_floors.check(head, BASE) == [f"{REL}: evidence: 75 lowered to 70"]


def test_t027_ci_refuses_a_removed_scope() -> None:
    head = "schema: 1\nfloors:\n  identity/authz: 85\n"
    assert mutation_floors.check(head, BASE) == [f"{REL}: evidence: the floor (75) was removed"]


def test_t027_ci_accepts_raised_floors_and_new_scopes() -> None:
    head = BASE.replace("75", "80") + "  compute: 10\n"
    assert mutation_floors.check(head, BASE) == []


def test_t027_ci_refuses_an_unreadable_head_and_checks_format_only_without_a_base() -> None:
    assert mutation_floors.check("floors:\n  evidence: lots\n", BASE)
    assert mutation_floors.check(BASE, None) == []


def test_t027_an_unreachable_explicit_base_fails(capsys: pytest.CaptureFixture[str]) -> None:
    assert mutation_floors.main(["--base", "0" * 40]) == 1
    assert "not reachable" in capsys.readouterr().out


# --- the hook ---------------------------------------------------------------------------------


@pytest.fixture(params=INTERPRETERS)
def project(request: pytest.FixtureRequest, tmp_path: Path) -> tuple[Path, Run]:
    shutil.copytree(HOOKS, tmp_path / ".claude" / "hooks")
    (tmp_path / "backend").mkdir()
    (tmp_path / REL).write_text(BASE, encoding="utf-8")
    python = str(request.param)

    def run(hook: str, tool_input: Mapping[str, object]) -> int:
        return subprocess.run(
            [python, str(tmp_path / ".claude" / "hooks" / hook)],
            input=json.dumps({"tool_input": tool_input}),
            capture_output=True,
            text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": str(tmp_path)},
            check=False,
        ).returncode

    return tmp_path, run


def _path(project: tuple[Path, Run]) -> str:
    return str(project[0] / REL)


def test_t027_the_hook_refuses_a_write_lowering_a_floor(project: tuple[Path, Run]) -> None:
    lowered = BASE.replace("identity/authz: 85", "identity/authz: 84")
    assert project[1]("protect_paths.py", {"file_path": _path(project), "content": lowered}) == 2


def test_t027_the_hook_refuses_an_edit_lowering_a_floor(project: tuple[Path, Run]) -> None:
    edit = {"file_path": _path(project), "old_string": "evidence: 75", "new_string": "evidence: 7"}
    assert project[1]("protect_paths.py", edit) == 2


def test_t027_the_hook_refuses_a_multiedit_removing_a_scope(project: tuple[Path, Run]) -> None:
    edits = [
        {"old_string": "identity/authz: 85", "new_string": "identity/authz: 90"},
        {"old_string": "  evidence: 75\n", "new_string": ""},
    ]
    assert project[1]("protect_paths.py", {"file_path": _path(project), "edits": edits}) == 2


def test_t027_the_hook_refuses_an_edit_that_breaks_the_format(project: tuple[Path, Run]) -> None:
    edit = {
        "file_path": _path(project),
        "old_string": "evidence: 75",
        "new_string": "evidence: hi",
    }
    assert project[1]("protect_paths.py", edit) == 2


def test_t027_the_hook_allows_raising_a_floor_and_adding_a_scope(
    project: tuple[Path, Run],
) -> None:
    raised = {
        "file_path": _path(project),
        "old_string": "evidence: 75",
        "new_string": "evidence: 80",
    }
    assert project[1]("protect_paths.py", raised) == 0
    added = {"file_path": _path(project), "content": BASE + "  compute: 5\n"}
    assert project[1]("protect_paths.py", added) == 0


def test_t027_the_hook_leaves_other_files_alone(project: tuple[Path, Run]) -> None:
    other = {"file_path": str(project[0] / "backend" / "other.yaml"), "content": "floors:\n"}
    assert project[1]("protect_paths.py", other) == 0


@pytest.mark.parametrize(
    "command",
    [
        "sed -i 's/85/80/' backend/mutation-thresholds.yaml",
        "echo 'floors:' > backend/mutation-thresholds.yaml",
        "cat x >> backend/mutation-thresholds.yaml",
        "cp /tmp/low.yaml backend/mutation-thresholds.yaml",
        "git checkout HEAD~3 -- backend/mutation-thresholds.yaml",
        'python3 -c \'open("backend/mutation-thresholds.yaml","w")\'',
        "cat backend/mutation-thresholds.yaml | tee backend/mutation-thresholds.yaml",
    ],
)
def test_t027_the_shell_hook_refuses_writes_to_the_floors(
    project: tuple[Path, Run], command: str
) -> None:
    assert project[1]("guard_bash.py", {"command": command}) == 2


@pytest.mark.parametrize(
    "command",
    [
        "cat backend/mutation-thresholds.yaml",
        "git diff origin/main -- backend/mutation-thresholds.yaml",
        "git add backend/mutation-thresholds.yaml && git status",
        "cd backend && uv run python -m abacus_tools.quality.mutation_floors",
    ],
)
def test_t027_the_shell_hook_lets_the_floors_be_read(
    project: tuple[Path, Run], command: str
) -> None:
    assert project[1]("guard_bash.py", {"command": command}) == 0
