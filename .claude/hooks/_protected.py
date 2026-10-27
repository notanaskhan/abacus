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
import re
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
    ("**/_capabilities.py", "python -m abacus_tools.codegen.write_capabilities"),
    ("docs/operations/sub-processors.md", "python -m abacus_tools.codegen.sub_processors"),
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


# Mutation floors (Q-03-T027; QD-4; ADR-079): only ever raised. Mirrors
# abacus_tools.quality.mutation_floors.parse (kept in step by tests/unit/quality/test_mutation_floors.py).
FLOORS_FILE = "backend/mutation-thresholds.yaml"
_FLOOR_LINE = re.compile(r"^  ([a-z0-9_]+(?:/[a-z0-9_]+)*):\s*(\d{1,3})\s*(?:#.*)?$")
_TOP_LINE = re.compile(r"^([a-z_]+):\s*(\S.*)?$")


def parse_floors(text: str) -> dict:
    """{scope: percent} from the floors block; raises ValueError on anything else under it."""
    floors = {}
    inside = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        top = _TOP_LINE.match(line)
        if top is not None:
            inside = top.group(1) == "floors" and top.group(2) is None
            continue
        floor = _FLOOR_LINE.match(line) if inside else None
        if floor is None:
            raise ValueError("line %d: %r is not `  <scope>: <0-100>` under floors:" % (number, line))
        scope, value = floor.group(1), int(floor.group(2))
        if value > 100 or scope in floors:
            raise ValueError("line %d: %s is over 100 or listed twice" % (number, scope))
        floors[scope] = value
    if not floors:
        raise ValueError("no floors: the file needs a `floors:` block")
    return floors


def _floors_at_main() -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", ROOT, "show", "origin/main:" + FLOORS_FILE],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.decode("utf-8", "replace") if result.returncode == 0 else None


def floor_violation(path: str, new_text: str) -> str | None:
    """Refuse an edit that leaves the floors file unreadable, or lowers or drops a floor that the
    file on disk or on origin/main holds."""
    r = rel(path)
    if r.lower() != FLOORS_FILE:
        return None
    try:
        head = parse_floors(new_text)
    except ValueError as exc:
        return "%s would not parse (%s); keep its format." % (r, exc)
    on_disk = os.path.join(ROOT, r)
    bases = []
    if os.path.exists(on_disk):
        with open(on_disk, encoding="utf-8") as handle:
            bases.append(handle.read())
    main_text = _floors_at_main()
    if main_text is not None:
        bases.append(main_text)
    for base_text in bases:
        try:
            base = parse_floors(base_text)
        except ValueError:
            continue
        for scope in sorted(base):
            if scope not in head:
                return "%s: removing the %s floor lowers it; floors are only raised (QD-4)." % (r, scope)
            if head[scope] < base[scope]:
                return "%s: the %s floor would drop from %d to %d; floors are only raised (QD-4)." % (
                    r, scope, base[scope], head[scope])
    return None


# The mutation scope is protected with its floors (Q-03-T027; DEC-365): `[tool.mutmut]` in the
# backend's pyproject and `SCOPES` in the driver. An agent edit that changes either block is
# refused; a person widens the scope, and CI (`abacus_tools.quality.mutation_floors`) refuses any
# narrowing however it is made. A guardrail, not a boundary: the shell can still write these files.
SCOPE_BLOCKS = {
    "backend/pyproject.toml": (r"^\[tool\.mutmut\]\s*$", r"^\["),
    "backend/src/abacus_tools/quality/mutation.py": (r"^SCOPES\b", r"^\}\s*$"),
}
# Content checked by reading the edit's result: only these files are read by the edit hook.
CONTENT_CHECKED = frozenset([FLOORS_FILE, *SCOPE_BLOCKS])
# Human-only registers (Q-03-T029; DEC-366): a change could waive a finding's SLA.
HUMAN_ONLY = ["docs/quality/supply-chain-findings.yaml"]


def _block(text: str, start: str, end: str) -> str | None:
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if re.match(start, line):
            out = [line]
            for later in lines[i + 1:]:
                if re.match(end, later):
                    if end == r"^\}\s*$":
                        out.append(later)
                    break
                out.append(later)
            return "\n".join(out).rstrip()
    return None


def scope_violation(path: str, new_text: str) -> str | None:
    """Refuse an edit that changes the mutation scope block of the file on disk."""
    r = rel(path).lower()
    if r not in SCOPE_BLOCKS:
        return None
    on_disk = os.path.join(ROOT, r)
    if not os.path.exists(on_disk):
        return None
    with open(on_disk, encoding="utf-8") as handle:
        old_text = handle.read()
    start, end = SCOPE_BLOCKS[r]
    before = _block(old_text, start, end)
    if before is not None and _block(new_text, start, end) != before:
        return "%s: the mutation scope (%s) is protected with its floors; a person changes it (Q-03-T027)." % (
            r, "[tool.mutmut]" if r.endswith(".toml") else "SCOPES")
    return None


def violation(path: str) -> str | None:
    r = rel(path)
    if r == ".." or r.startswith("../"):
        return f"{path} is outside the project."
    for pattern, command in GENERATED:
        if _match(r, [pattern]):
            return f"{r} is generated; never edit it by hand. Regenerate it: {command} (or make regenerate)."
    if _match(r, HUMAN_ONLY):
        return f"{r} is the supply-chain findings register; a person records findings and waivers (Q-03-T029)."
    if _match(r, SECRETS) and not _match(r, SECRET_TEMPLATES):
        return f"{r} holds secrets; agents never write it. Edit it yourself, outside the session."
    if _match(r, IMMUTABLE_ON_MAIN) and os.path.exists(os.path.join(ROOT, r)) and on_main(r):
        return f"{r} is an applied migration on main and is immutable. Add a new migration instead."
    return None
