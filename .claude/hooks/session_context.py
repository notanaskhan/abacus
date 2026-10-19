#!/usr/bin/env python3
"""SessionStart hook: what this checkout is working on (F-01-T09). Its output joins the context.

Never blocks: any failure prints a warning and exits 0. Runs under the system `python3` (3.9 on
macOS): keep it 3.9-compatible. Reads only; never fetches, so "behind" is as of the last fetch.
"""
from __future__ import annotations

import glob
import os
import re
import subprocess
import sys

ROOT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
TASK_BRANCH = re.compile(r"^task-(\d{3})\b", re.IGNORECASE)
STATUS = re.compile(r"^status:\s*(\S+)", re.MULTILINE)


def git(*args: str) -> str:
    out = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=3, check=True
    )
    return out.stdout.strip()


def task_line(branch: str) -> str:
    match = TASK_BRANCH.match(branch)
    if not match:
        return "task: none linked (branch is not task-NNN-…)"
    files = sorted(glob.glob(os.path.join(ROOT, "work", "tasks", f"TASK-{match.group(1)}-*.md")))
    if not files:
        return f"task: TASK-{match.group(1)} has no task file yet"
    with open(files[0], encoding="utf-8") as fh:
        status = STATUS.search(fh.read())
    rel = os.path.relpath(files[0], ROOT)
    return f"task: {rel} (status: {status.group(1) if status else 'unknown'})"


def port_offset() -> str:
    if os.environ.get("ABACUS_PORT_OFFSET"):
        return os.environ["ABACUS_PORT_OFFSET"]
    path = os.path.join(ROOT, ".worktree.env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("ABACUS_PORT_OFFSET="):
                    return line.split("=", 1)[1].strip()
    return "0"


def handoff_version() -> str:
    path = os.path.join(ROOT, "docs", "design", "HANDOFF_VERSION")
    if not os.path.exists(path):
        return "HANDOFF_VERSION not set"
    with open(path, encoding="utf-8") as fh:
        return fh.read().strip() or "HANDOFF_VERSION empty"


def main() -> None:
    lines = []
    try:
        branch = git("rev-parse", "--abbrev-ref", "HEAD")
        lines.append(f"branch: {branch}")
        lines.append(task_line(branch))
        try:
            behind = git("rev-list", "--count", "HEAD..origin/main")
            lines.append(f"behind origin/main: {behind} commit(s) (as of the last fetch)")
        except (subprocess.SubprocessError, OSError):
            lines.append("behind origin/main: unknown (no origin/main ref)")
    except Exception as exc:  # noqa: BLE001 — never block a session
        lines.append(f"warning: git state unavailable ({type(exc).__name__})")
    try:
        lines.append(f"port offset: {port_offset()}")
        lines.append(f"design handoff: {handoff_version()}")
    except Exception as exc:  # noqa: BLE001 — never block a session
        lines.append(f"warning: session context incomplete ({type(exc).__name__})")
    print("Abacus session context\n" + "\n".join(f"- {line}" for line in lines))


try:
    main()
except Exception as exc:  # noqa: BLE001 — never block a session
    print(f"warning: session context hook failed ({type(exc).__name__}: {exc})")
sys.exit(0)
