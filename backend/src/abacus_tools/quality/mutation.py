"""Mutation testing driver (Q-03-T026; ADR-079; DEC-365).

Run from backend/: python -m abacus_tools.quality.mutation <command>

- `plan nightly [--since-hours 24]`: the red files changed on this branch in the last 24 hours.
- `plan weekly --shard I --shards N`: shard I of N over every red file, balanced by line count.
- `narrow PLAN`: point `[tool.mutmut] only_mutate` in pyproject.toml at the plan's files. The
  workflows run it on the runner's checkout only; the committed list is the whole red scope.
- `prepare`: link the repository's top-level entries into backend/, so a test that finds the
  repository as `Path(__file__).parents[n]` still finds it from mutmut's `mutants/` copy.
- `summarise [--enforce-floors]`: killed, survived and the survivors per scope from mutmut's
  `mutants/**/*.meta` files, as JSON and Markdown; with `--enforce-floors`, exit 1 when a scope
  that ran is under its floor in `backend/mutation-thresholds.yaml`.

mutmut itself (3.8.0, allowlisted) runs only in `mutation-nightly.yml` and `mutation-weekly.yml`
through `uv run --with`; this module never imports it.
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, cast

from abacus_tools.quality.mutation_floors import FILE as FLOORS_FILE
from abacus_tools.quality.mutation_floors import parse as parse_floors

BACKEND = Path(__file__).resolve().parents[3]
GIT = shutil.which("git") or "/usr/bin/git"
REPO = BACKEND.parent
PYPROJECT = BACKEND / "pyproject.toml"

# Q-03 C1: the red scopes, as globs on backend-relative paths (`*` crosses `/`, as in mutmut).
SCOPES: Final[dict[str, tuple[str, ...]]] = {
    "identity/authz": ("src/abacus/modules/identity/authz/*.py",),
    "kernel/db": ("src/abacus/kernel/db/*.py",),
    "kernel/uow": ("src/abacus/kernel/uow/*.py",),
    "kernel/crypto": ("src/abacus/kernel/crypto/*.py",),
    "evidence": ("src/abacus/modules/evidence/*.py",),
    "ai_gateway": ("src/abacus/ai_gateway/*.py",),
    "audit_trail": ("src/abacus/modules/audit_trail/*.py",),
    "compute": ("src/abacus/*/compute/*.py",),
    "signatures": ("src/abacus/modules/signatures/*.py",),  # N-02-T47 (ADR-079)
}
# Generated files are regenerated, never mutated.
GENERATED: Final = (
    "_matrix.py",
    "_flags.py",
    "_specs.py",
    "_statuses.py",
    "_eval_suites.py",
    "_human_only_actions.py",
    "_provider_terms.py",
)
NIGHTLY_BUDGET_MINUTES: Final = 60
WEEKLY_BUDGET_MINUTES: Final = 240
WEEKLY_SHARDS: Final = 4

KILLED: Final = frozenset({1, 3})
TIMEOUT: Final = frozenset({36, -24, 24, 152, 255})
SURVIVED: Final = frozenset({0})
NO_TESTS: Final = frozenset({5, 33})
NOT_RUN: Final = frozenset({34, 37, 2})  # skipped, caught by type check, interrupted


def scope_of(path: str) -> str | None:
    """The red scope a backend-relative path belongs to, or None."""
    if Path(path).name in GENERATED or not path.endswith(".py"):
        return None
    for scope, globs in SCOPES.items():
        if any(fnmatch.fnmatch(path, glob) for glob in globs):
            return scope
    return None


def red_files(backend: Path = BACKEND) -> list[str]:
    """Every red file on disk, backend-relative and sorted."""
    found = (p.relative_to(backend).as_posix() for p in (backend / "src").rglob("*.py"))
    return sorted(p for p in found if scope_of(p) is not None)


def changed_red_files(changed: Iterable[str], backend: Path = BACKEND) -> list[str]:
    """The red files among repository-relative changed paths that still exist."""
    out: set[str] = set()
    for path in changed:
        if not path.startswith("backend/"):
            continue
        rel = path.removeprefix("backend/")
        if scope_of(rel) is not None and (backend / rel).is_file():
            out.add(rel)
    return sorted(out)


def _git_changed_since(hours: int) -> list[str]:
    result = subprocess.run(
        [
            GIT,
            "-C",
            str(REPO),
            "log",
            f"--since={hours} hours ago",
            "--name-only",
            "--pretty=format:",
            "--",
            "backend/src",
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _lines(backend: Path, rel: str) -> int:
    return sum(1 for _ in (backend / rel).open(encoding="utf-8"))


def shards(files: Sequence[str], count: int, weight: dict[str, int]) -> list[list[str]]:
    """`count` shards with every file in exactly one, balanced greedily by weight (heaviest
    first into the lightest shard); each shard's files sorted."""
    if count < 1:
        raise ValueError("at least one shard")
    buckets: list[list[str]] = [[] for _ in range(count)]
    loads = [0] * count
    for rel in sorted(files, key=lambda f: (-weight.get(f, 0), f)):
        lightest = loads.index(min(loads))
        buckets[lightest].append(rel)
        loads[lightest] += weight.get(rel, 0)
    return [sorted(b) for b in buckets]


_ONLY_MUTATE = re.compile(r"(?ms)^only_mutate = \[\n.*?^\]\n")


def narrow(pyproject_text: str, files: Sequence[str]) -> str:
    """pyproject.toml with `[tool.mutmut] only_mutate` replaced by exactly these files."""
    if _ONLY_MUTATE.search(pyproject_text) is None:
        raise ValueError("pyproject.toml has no multi-line `only_mutate = [` in [tool.mutmut]")
    body = "".join(f'    "{f}",\n' for f in files)
    return _ONLY_MUTATE.sub(lambda _m: f"only_mutate = [\n{body}]\n", pyproject_text, count=1)


def prepare(backend: Path = BACKEND) -> list[str]:
    """Link each top-level repository entry into backend/ (skipping names backend/ already has);
    the runner's checkout only. Returns the names linked.

    `backend/backend` links to backend/ itself (Q-03-T147): from mutmut's copy a tool's
    `Path(__file__).parents[n]` lands on backend/ where it expects the repository, so a
    `REPO / "backend" / ...` path must still resolve. pathlib's `rglob` and `os.walk` follow no
    directory symlinks, so the loop is never walked."""
    linked: list[str] = []
    for entry in sorted(backend.parent.iterdir()):
        target = backend / entry.name
        if entry == backend or entry.name == ".git" or target.exists() or target.is_symlink():
            continue
        target.symlink_to(Path("..") / entry.name)
        linked.append(entry.name)
    itself = backend / backend.name
    if not itself.exists() and not itself.is_symlink():
        itself.symlink_to(Path("."))
        linked.append(backend.name)
    return linked


@dataclass
class ScopeResult:
    killed: int = 0
    timeout: int = 0
    survived: int = 0
    no_tests: int = 0
    not_run: int = 0
    suspicious: int = 0
    survivors: list[str] = field(default_factory=lambda: list[str]())

    @property
    def ran(self) -> int:
        return self.killed + self.timeout + self.survived + self.no_tests + self.suspicious

    @property
    def score(self) -> float | None:
        """Killed and timed out over every mutant that ran, in percent."""
        return None if self.ran == 0 else round(100 * (self.killed + self.timeout) / self.ran, 1)


def tally(metas: dict[str, dict[str, object]]) -> dict[str, ScopeResult]:
    """Per scope, from {backend-relative source path: parsed .meta JSON}."""
    out: dict[str, ScopeResult] = {}
    for source, meta in sorted(metas.items()):
        scope = scope_of(source)
        if scope is None:
            continue
        result = out.setdefault(scope, ScopeResult())
        codes = cast(dict[str, int | None], meta.get("exit_code_by_key") or {})
        for mutant, code in sorted(codes.items()):
            if code is None or code in NOT_RUN:
                result.not_run += 1
            elif code in KILLED:
                result.killed += 1
            elif code in TIMEOUT:
                result.timeout += 1
            elif code in SURVIVED:
                result.survived += 1
                result.survivors.append(mutant)
            elif code in NO_TESTS:
                result.no_tests += 1
                result.survivors.append(mutant)
            else:
                result.suspicious += 1
    return out


def read_metas(mutants: Path) -> dict[str, dict[str, object]]:
    """mutmut keeps one `<source path>.meta` JSON per mutated file under `mutants/`."""
    metas: dict[str, dict[str, object]] = {}
    for meta in sorted(mutants.rglob("*.py.meta")):
        source = meta.relative_to(mutants).as_posix().removesuffix(".meta")
        metas[source] = cast(dict[str, object], json.loads(meta.read_text(encoding="utf-8")))
    return metas


def under_floor(results: dict[str, ScopeResult], floors: dict[str, int]) -> list[str]:
    found: list[str] = []
    for scope, result in sorted(results.items()):
        score, floor = result.score, floors.get(scope, 0)
        if score is not None and score < floor:
            found.append(f"{scope}: {score}% is under its floor of {floor}%")
    return found


def unmeasured(
    results: dict[str, ScopeResult], floors: dict[str, int], files: list[str]
) -> list[str]:
    """A floored scope the weekly run did not measure fails it (fail closed): one excluded through
    `do_not_mutate`, dropped from `SCOPES` or lost to a shard that stopped would otherwise pass."""
    on_disk = {scope_of(f) for f in files}
    found: list[str] = []
    for scope, floor in sorted(floors.items()):
        ran = results[scope].ran if scope in results else 0
        if scope not in SCOPES:
            found.append(f"{scope}: has a floor but is not a mutation scope (SCOPES)")
        elif ran == 0 and (floor > 0 or scope in on_disk):
            found.append(f"{scope}: no mutant ran (floor {floor}%); the scope went unmeasured")
    return found


def markdown(results: dict[str, ScopeResult], floors: dict[str, int], title: str) -> str:
    rows = [
        f"## {title}",
        "",
        "| Scope | Score | Floor | Killed | Timeout | Survived | No tests | Not run |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for scope, r in sorted(results.items()):
        score = "n/a" if r.score is None else f"{r.score}%"
        rows.append(
            f"| {scope} | {score} | {floors.get(scope, 0)}% | {r.killed} | {r.timeout} "
            f"| {r.survived} | {r.no_tests} | {r.not_run} |"
        )
    if not results:
        rows.append("| (no red file mutated) | | | | | | | |")
    rows.append("")
    for scope, r in sorted(results.items()):
        if r.survivors:
            rows += [f"<details><summary>{scope}: {len(r.survivors)} survivors</summary>", ""]
            rows += [f"- `{name}`" for name in r.survivors]
            rows += ["", "</details>", ""]
    return "\n".join(rows) + "\n"


def _plan(args: argparse.Namespace) -> int:
    if args.kind == "nightly":
        files = changed_red_files(_git_changed_since(cast(int, args.since_hours)))
    else:
        every = red_files()
        weight = {f: _lines(BACKEND, f) for f in every}
        shard, count = cast(int, args.shard), cast(int, args.shards)
        files = shards(every, count, weight)[shard - 1]
    Path(args.out).write_text(json.dumps({"files": files}, indent=2) + "\n", encoding="utf-8")
    print(f"mutation plan ({args.kind}): {len(files)} red files")
    return 0


def _narrow(args: argparse.Namespace) -> int:
    files = cast(list[str], json.loads(Path(args.plan).read_text(encoding="utf-8"))["files"])
    if not files:
        print("mutation plan is empty: nothing to narrow")
        return 0
    PYPROJECT.write_text(narrow(PYPROJECT.read_text(encoding="utf-8"), files), encoding="utf-8")
    print(f"only_mutate narrowed to {len(files)} files")
    return 0


def _summarise(args: argparse.Namespace) -> int:
    floors = parse_floors(FLOORS_FILE.read_text(encoding="utf-8"))
    mutants = Path(args.mutants)
    results = tally(read_metas(mutants)) if mutants.is_dir() else {}
    payload = {
        scope: {
            "score": r.score,
            "floor": floors.get(scope, 0),
            "killed": r.killed,
            "timeout": r.timeout,
            "survived": r.survived,
            "no_tests": r.no_tests,
            "not_run": r.not_run,
            "suspicious": r.suspicious,
            "survivors": r.survivors,
        }
        for scope, r in sorted(results.items())
    }
    Path(args.json).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    Path(args.markdown).write_text(markdown(results, floors, args.title), encoding="utf-8")
    problems = (
        under_floor(results, floors) + unmeasured(results, floors, red_files())
        if args.enforce_floors
        else []
    )
    for problem in problems:
        print(problem)
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    plan = commands.add_parser("plan")
    plan.add_argument("kind", choices=["nightly", "weekly"])
    plan.add_argument("--since-hours", type=int, default=24)
    plan.add_argument("--shard", type=int, default=1)
    plan.add_argument("--shards", type=int, default=WEEKLY_SHARDS)
    plan.add_argument("--out", default="mutation-plan.json")
    narrowed = commands.add_parser("narrow")
    narrowed.add_argument("plan")
    commands.add_parser("prepare")
    summary = commands.add_parser("summarise")
    summary.add_argument("--mutants", default="mutants")
    summary.add_argument("--json", default="mutation-survivors.json")
    summary.add_argument("--markdown", default="mutation-survivors.md")
    summary.add_argument("--title", default="Mutation survivors per module")
    summary.add_argument("--enforce-floors", action="store_true")
    args = parser.parse_args(argv)
    if args.command == "plan":
        if args.kind == "weekly" and not 1 <= args.shard <= args.shards:
            parser.error("--shard must be within 1..--shards")
        return _plan(args)
    if args.command == "narrow":
        return _narrow(args)
    if args.command == "prepare":
        print("linked into backend/: " + ", ".join(prepare()))
        return 0
    return _summarise(args)


if __name__ == "__main__":
    sys.exit(main())
