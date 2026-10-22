"""Shared path rules for hooks. Mirrors docs/architecture/protected-paths.md.

Solo edition (SU-06): no approval files. The hooks keep only what protects data and correctness:
secret files are never written by an agent, generated files are regenerated rather than edited,
and a migration already on origin/main is never edited.

Runs under whatever `python3` is first on PATH (macOS ships 3.9): keep it 3.9-compatible.
Matching is case-insensitive (APFS is) and segment-aware: `*` never crosses `/`; `**` spans
zero or more directories.
"""
from __future__ import annotations

import fnmatch
import os
import subprocess

ROOT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))

# Secrets: never written by an agent. Templates (.env.example, .env.sample) are fine.
SECRETS = [
    "**/.env", "**/.env.*",
    "**/*.pem", "**/*.key", "**/*.p12", "**/*.pfx",
    "**/secrets/**",
    "**/credentials", "**/credentials.*",
]
SECRET_TEMPLATES = ["**/.env.example", "**/.env.sample", "**/.env.template"]

# Immutable once on origin/main: an applied migration is replaced by a new one, never edited.
IMMUTABLE_ON_MAIN = ["backend/migrations/versions/*"]

# Generated: never hand-edited; regenerate instead (F-01-T09).
# (pattern, the command that regenerates it)
GENERATED = [
    ("packages/api-client/openapi.json", "make generate"),
    ("packages/api-client/src/**", "make generate"),
    ("**/_matrix.py", "python -m abacus_tools.codegen.permission_matrix"),
    ("**/_flags.py", "python -m abacus_tools.codegen.feature_flags"),
    ("**/_provider_terms.py", "python -m abacus_tools.codegen.provider_terms"),
    ("**/_human_only_actions.py", "python -m abacus_tools.codegen.human_only_actions"),
    ("**/_specs.py", "python -m abacus_tools.codegen.agent_specs"),
    ("**/_eval_suites.py", "python -m abacus_tools.codegen.eval_suites"),
    ("backend/tests/durations.json", "python -m abacus_tools.ci.shard --record <report>"),
    ("backend/tests/workflows/histories/*.json", "the workflow's replay recorder (abacus_tools.workflows)"),
]


def rel(path: str) -> str:
    """Repo-relative path with symlinks resolved, so a link cannot launder a guarded target."""
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


def on_main(r: str) -> bool:
    """True when the path exists on origin/main. Without git or origin/main, a file that exists
    on disk counts as on main (fail closed)."""
    try:
        result = subprocess.run(
            ["git", "-C", ROOT, "cat-file", "-e", "origin/main:" + r],
            capture_output=True,
            timeout=5,
            check=False,
        )
        known = subprocess.run(
            ["git", "-C", ROOT, "rev-parse", "--verify", "--quiet", "origin/main"],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return True
    if known.returncode != 0:
        return True
    return result.returncode == 0


def violation(path: str) -> str | None:
    r = rel(path)
    if r == ".." or r.startswith("../"):
        return f"{path} is outside the project."
    for pattern, command in GENERATED:
        if _match(r, [pattern]):
            return f"{r} is generated; never edit it by hand. Regenerate it: {command} (or make regenerate)."
    if _match(r, SECRETS) and not _match(r, SECRET_TEMPLATES):
        return f"{r} holds secrets; agents never write it. Edit it yourself, outside the session."
    if _match(r, IMMUTABLE_ON_MAIN) and os.path.exists(os.path.join(ROOT, r)) and on_main(r):
        return f"{r} is an applied migration on main and is immutable. Add a new migration instead."
    return None
