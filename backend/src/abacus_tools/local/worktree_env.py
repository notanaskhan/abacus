"""Give this checkout its own local stack: compose project and port offset (F-01-T09).

Run: python -m abacus_tools.local.worktree_env      (or `make worktree-env`)

Writes the git-ignored `.worktree.env` at the checkout's root:
    COMPOSE_PROJECT_NAME=abacus-<slug>
    ABACUS_PORT_OFFSET=<n>
The primary checkout keeps project `abacus` and offset 0, so its volumes and ports don't change.
A linked worktree takes the next free slot of 10 (10, 20, …) not used by another worktree's
`.worktree.env`. Every local port (5173, 8001, 9000, 55432, 7070, 7233, 8233) adds the offset.
An existing file is kept, so a checkout's ports never move under it.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

FILE = ".worktree.env"
STEP = 10
MAX_OFFSET = 90
_OFFSET = re.compile(r"^ABACUS_PORT_OFFSET=(\d+)\s*$", re.MULTILINE)


def port_offset() -> int:
    """This checkout's offset from `ABACUS_PORT_OFFSET` (exported by the Makefile); 0 if unset."""
    raw = os.environ.get("ABACUS_PORT_OFFSET", "").strip() or "0"
    if not raw.isdigit() or int(raw) % STEP or int(raw) > MAX_OFFSET:
        raise ValueError(f"ABACUS_PORT_OFFSET must be 0, 10, … {MAX_OFFSET}")
    return int(raw)


def _git(cwd: Path, *args: str) -> str:
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("git is required")
    return subprocess.run(
        [git, *args], cwd=cwd, capture_output=True, text=True, check=True
    ).stdout.strip()


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "worktree"


def used_offsets(worktrees: list[Path]) -> set[int]:
    used: set[int] = set()
    for tree in worktrees:
        env = tree / FILE
        if env.is_file():
            match = _OFFSET.search(env.read_text(encoding="utf-8"))
            if match:
                used.add(int(match.group(1)))
    return used


def next_offset(used: set[int]) -> int:
    for offset in range(STEP, MAX_OFFSET + 1, STEP):
        if offset not in used:
            return offset
    raise RuntimeError(f"every port slot up to {MAX_OFFSET} is taken: remove an old worktree")


def contents(project: str, offset: int) -> str:
    return f"COMPOSE_PROJECT_NAME={project}\nABACUS_PORT_OFFSET={offset}\n"


def plan(root: Path, primary: bool, worktrees: list[Path]) -> str:
    if primary:
        return contents("abacus", 0)
    others = [t for t in worktrees if t.resolve() != root.resolve()]
    return contents(f"abacus-{slug(root.name)}", next_offset(used_offsets(others)))


def main() -> int:
    root = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel"))
    target = root / FILE
    if target.exists():
        print(target.read_text(encoding="utf-8"), end="")
        return 0
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir"))
    common = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    listing = _git(root, "worktree", "list", "--porcelain")
    worktrees = [Path(line[9:]) for line in listing.splitlines() if line.startswith("worktree ")]
    text = plan(root, git_dir.resolve() == common.resolve(), worktrees)
    target.write_text(text, encoding="utf-8")
    print(text, end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
