"""Shared protected-path rules for hooks. Mirrors docs/architecture/protected-paths.md.

Runs under whatever `python3` is first on PATH (macOS ships 3.9): keep it 3.9-compatible.
Matching is case-insensitive (APFS is) and segment-aware: `*` never crosses `/`; `**` spans
zero or more directories.
"""
from __future__ import annotations

import datetime
import fnmatch
import glob
import os
import re

ROOT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

# Always protected: any edit or creation requires an approval file.
PROTECTED = [
    "AGENTS.md", "CLAUDE.md", "**/Makefile",
    ".claude/**",
    ".github/**",
    ".git/**",
    "**/.gitignore",
    "infra/**",
    "**/*compose*.y*ml",
    "work/approvals/**",
    "docs/architecture/permission-matrix.yaml",
    "docs/architecture/protected-paths.md",
    "docs/architecture/dependency-allowlist.yaml",
    "docs/product/glossary.md",
    "docs/product/failure-taxonomy.md",
    "**/pyproject.toml", "backend/uv.lock",
    "**/package.json", "pnpm-lock.yaml", "pnpm-workspace.yaml", "**/.npmrc",
    "backend/src/abacus_tools/quality/**",
    "backend/tests/unit/quality/**",
    "backend/src/abacus/modules/identity/authz/**",
    "backend/src/abacus/kernel/db/**",
    "backend/alembic.ini", "backend/migrations/env.py", "backend/migrations/bootstrap.sql",
    "backend/src/abacus/kernel/uow/**",
    "backend/src/abacus/kernel/crypto/**",
    "backend/src/abacus/modules/audit_trail/**",
]
# Protected only once they exist: new files allowed, edits to existing files need approval.
PROTECTED_IF_EXISTS = ["docs/adr/ADR-*.md", "backend/migrations/versions/*"]

_TOP_KEY = re.compile(r"^([A-Za-z_]+):\s*(.*)$")
_LIST_ITEM = re.compile(r"^\s+-\s+(.+)$")


def rel(path: str) -> str:
    """Repo-relative path with symlinks resolved, so a link cannot launder a protected target."""
    p = os.path.realpath(path if os.path.isabs(path) else os.path.join(ROOT, path))
    return os.path.relpath(p, ROOT).replace(os.sep, "/")


def _segments_match(parts: list[str], pattern: list[str]) -> bool:
    if not pattern:
        return not parts
    head, rest = pattern[0], pattern[1:]
    if head == "**":
        return any(_segments_match(parts[i:], rest) for i in range(len(parts) + 1))
    return bool(parts) and fnmatch.fnmatchcase(parts[0], head) and _segments_match(parts[1:], rest)


def _match(r: str, patterns: list[str]) -> bool:
    parts = r.lower().split("/")
    return any(_segments_match(parts, p.lower().split("/")) for p in patterns)


def _acceptable_pattern(pattern: str) -> bool:
    """Approval patterns must name a concrete top-level directory or file: no `*`, `**/*`."""
    first = pattern.split("/")[0]
    return bool(first) and "*" not in first and "?" not in first and ".." not in pattern.split("/")


def parse_approval(text: str) -> tuple[dict[str, str], list[str]]:
    """Top-level `key: value` pairs and the items under `paths:` (comments stripped)."""
    keys: dict[str, str] = {}
    paths: list[str] = []
    in_paths = False
    for raw in text.splitlines():
        line = raw.split(" #", 1)[0].rstrip()
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        top = _TOP_KEY.match(line)
        if top:
            keys[top.group(1)] = top.group(2).strip()
            in_paths = top.group(1) == "paths"
            continue
        item = _LIST_ITEM.match(line)
        if in_paths and item:
            paths.append(item.group(1).strip().strip("'\""))
    return keys, paths


def _valid_until(expires: str) -> bool:
    try:
        return datetime.date.fromisoformat(expires) >= datetime.date.today()
    except ValueError:
        return False


def approved(r: str) -> bool:
    """An approval file in work/approvals/*.yaml written by the founder:
       task: TASK-012
       approved_by: founder
       expires: 2026-12-31
       paths:
         - backend/src/abacus/kernel/uow/**
    """
    for f in glob.glob(os.path.join(ROOT, "work/approvals/*.yaml")):
        try:
            with open(f, encoding="utf-8") as fh:
                keys, paths = parse_approval(fh.read())
        except (OSError, UnicodeDecodeError):
            continue
        if keys.get("approved_by") != "founder" or not _valid_until(keys.get("expires", "")):
            continue
        if _match(r, [p for p in paths if _acceptable_pattern(p)]):
            return True
    return False


def violation(path: str) -> str | None:
    r = rel(path)
    if r == ".." or r.startswith("../"):
        return f"{path} is outside the project."
    if _match(r, ["work/approvals/**"]):
        return "Approval files can only be created by the founder, by hand."
    if _match(r, PROTECTED) and not approved(r):
        return f"{r} is a protected path. Ask the founder for an approval file in work/approvals/."
    if _match(r, PROTECTED_IF_EXISTS) and os.path.exists(os.path.join(ROOT, r)) and not approved(r):
        return f"{r} already exists and is immutable (accepted ADR or applied migration). Create a new file instead, or ask for approval."
    return None
