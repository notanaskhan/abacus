"""Mutation testing driver (Q-03-T026; ADR-079; DEC-365).

Run from backend/: python -m abacus_tools.quality.mutation <command>

- `plan nightly [--since-hours 24]`: the red files changed on this branch in the last 24 hours.
- `plan weekly --shard I --shards N`: shard I of N over every red file, balanced by line count;
  the measured outliers in `WEEKLY_HEAVY` are weighted by their cost, and a file with `parts` > 1
  has its mutants split across that many shards by the last digit of the mutant number. A shard
  holding such a part writes mutmut's mutant-name globs into the plan (`mutants`), and the
  workflow passes them to `mutmut run`.
- `narrow PLAN`: point `[tool.mutmut] only_mutate` in pyproject.toml at the plan's files. The
  workflows run it on the runner's checkout only; the committed list is the whole red scope.
- `prepare`: link the repository's top-level entries into backend/, so a test that finds the
  repository as `Path(__file__).parents[n]` still finds it from mutmut's `mutants/` copy.
- `summarise [--mutants DIR ...] [--enforce-floors]`: killed, survived and the survivors per scope
  from mutmut's `**/*.meta` files, as JSON and Markdown; with `--enforce-floors`, exit 1 when a
  scope that ran is under its floor in `backend/mutation-thresholds.yaml`. Given one folder per
  shard, the shards' `.meta` files for one source are merged first: a result from any shard wins
  over a mutant another shard did not run.

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
from collections.abc import Callable, Iterable, Sequence
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
    # T-04-T53 (ADR-079; DEC-4513): the individual return's compute engines and the tax tools,
    # matched before the broad `compute` glob so they carry their own floor.
    "tax/individual": (
        "src/abacus/modules/tax/compute/individual/*.py",
        "src/abacus/modules/tax/tools.py",
        "src/abacus/modules/tax/agent_tools.py",
    ),
    "compute": ("src/abacus/*/compute/*.py",),
    "signatures": ("src/abacus/modules/signatures/*.py",),  # N-02-T47 (ADR-079)
    "review": ("src/abacus/modules/review/*.py",),  # P-04-T59 (ADR-079; DEC-2065)
    # A-07-T45 (ADR-079): release, the archive gate and the lock's seal; evidence/archive.py is in
    # `evidence` and archived_guard()'s registry in `kernel/db` already.
    "assurance/release_archive": (
        "src/abacus/modules/assurance/release.py",
        "src/abacus/modules/assurance/archive_gate.py",
        "src/abacus/modules/assurance/archive_lock.py",
        "src/abacus/modules/assurance/archive_seal.py",
        "src/abacus/modules/assurance/archive_additions.py",
    ),
    # P-10-T52 (ADR-079): runtime v2, the plan rules, the workflow and its activities, waits,
    # commands, the approved write and undo, session turns, the harness and C17's runtime.
    "agents/runtime": (  # literal: the floor check reads SCOPES from source
        "src/abacus/modules/agents/run_plan.py",
        "src/abacus/modules/agents/run_workflow.py",
        "src/abacus/modules/agents/run_activities.py",
        "src/abacus/modules/agents/run_waits.py",
        "src/abacus/modules/agents/run_commands.py",
        "src/abacus/modules/agents/commands.py",
        "src/abacus/modules/agents/approved_writes.py",
        "src/abacus/modules/agents/approved_write_workflow.py",
        "src/abacus/modules/agents/proposal_undo.py",
        "src/abacus/modules/agents/session_turns.py",
        "src/abacus/modules/agents/harness.py",
        "src/abacus/modules/agents/tools/runtime.py",
    ),
    # P-10-T52 (ADR-079): the SSE stream, its slots, frames, topics and invalidations.
    "kernel/realtime": ("src/abacus/kernel/realtime.py",),
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
WEEKLY_SHARDS: Final = (
    8  # Q-03-T205 six; Q-03-T147 eight: shard 4 of six ran out at 15,308 of 16,196
)


@dataclass(frozen=True)
class Heavy:
    """A red file whose mutants cost far more than its line count says."""

    seconds_per_line: float  # CPU seconds of mutants per line, measured on a weekly run
    parts: int = 1  # shards its mutants are split across (a divisor of 10: by last digit)


# TASK-7818, TASK-7832 (DEC-4816, DEC-4825): a shard's time is its setup (mutmut's stats pass and
# clean tests over the whole unit suite, slowed by every mutated function's trampoline) plus its
# mutants over four workers. Runs 43330118713 and 43393671620 measured setup at about 55 minutes
# and 2.8 more per 1,000 mutated lines (0.67 CPU s a line at four workers), the mutants of the red
# scope at about 0.4 CPU s a line, and these four far above it. identity/authz's 1,708 mutants
# (about 1,370 CPU minutes: nearly every unit test calls `authorise`, whose 324 mutants take 160 s
# each) are over one shard's budget on their own, so they go to five shards; every part pays the
# whole file's setup. A file's weight is its lines times (setup + mutants) a line over an ordinary
# line's, so every other file still weighs its line count.
WEEKLY_SETUP_SECONDS_PER_LINE: Final = 0.67
WEEKLY_BASE_SECONDS_PER_LINE: Final = 0.4
WEEKLY_HEAVY: Final[dict[str, Heavy]] = {
    "src/abacus/modules/identity/authz/__init__.py": Heavy(seconds_per_line=70, parts=5),
    "src/abacus/modules/evidence/form_extraction.py": Heavy(seconds_per_line=30),
    "src/abacus/modules/evidence/pii.py": Heavy(seconds_per_line=17),
    "src/abacus/kernel/crypto/payload_codec.py": Heavy(seconds_per_line=92),
}

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


def shards(
    files: Sequence[str],
    count: int,
    weight: dict[str, int],
    apart: Callable[[str], str] | None = None,
) -> list[list[str]]:
    """`count` shards with every file in exactly one, balanced greedily by weight (heaviest
    first into the lightest shard); each shard's files sorted. Items with the same `apart` key
    (the parts of one split file) never share a shard."""
    if count < 1:
        raise ValueError("at least one shard")
    buckets: list[list[str]] = [[] for _ in range(count)]
    loads = [0] * count
    held: list[set[str]] = [set() for _ in range(count)]
    for rel in sorted(files, key=lambda f: (-weight.get(f, 0), f)):
        key = apart(rel) if apart is not None else None
        free = [i for i in range(count) if key is None or key not in held[i]]
        if not free:
            raise ValueError(f"more parts of {key} than shards")
        lightest = min(free, key=lambda i: (loads[i], i))
        buckets[lightest].append(rel)
        loads[lightest] += weight.get(rel, 0)
        if key is not None:
            held[lightest].add(key)
    return [sorted(b) for b in buckets]


METHOD_SEPARATOR: Final = "\u01c1"  # mutmut's `ǁ` in `xǁ<Class>ǁ<method>`
_PART = "#"  # `<file>#<last digits>`: one part of a split file in the weekly plan


def digit_parts(parts: int) -> list[str]:
    """The last digits of the mutant numbers in each of `parts` parts: every digit in one."""
    if parts < 1 or 10 % parts:
        raise ValueError(f"a split file's parts divide 10, not {parts}")
    return ["".join(str(d) for d in range(10) if d % parts == k) for k in range(parts)]


def module_of(rel: str) -> str:
    """The dotted module mutmut names a backend-relative source path's mutants after."""
    dotted = rel.removeprefix("src/").removesuffix(".py").replace("/", ".")
    return dotted.removesuffix(".__init__")


def mutant_globs(rel: str, digits: str | None = None) -> list[str]:
    """mutmut 3.8 `mutmut run` globs for a file's mutants (functions `x_<name>`, methods
    `xǁ<Class>ǁ<method>`), or, with `digits`, for those whose number ends in one of them."""
    tail = "__mutmut_*" if digits is None else f"__mutmut_*[{digits}]"
    module = module_of(rel)
    return [f"{module}.x_*{tail}", f"{module}.x{METHOD_SEPARATOR}*{tail}"]


@dataclass(frozen=True)
class ShardPlan:
    files: list[str]
    mutants: list[str]  # empty: every mutant of `files`


def weekly_plan(
    files: Sequence[str],
    count: int,
    lines: dict[str, int],
    heavy: dict[str, Heavy] = WEEKLY_HEAVY,
) -> list[ShardPlan]:
    """`count` shard plans over `files`: line count for every file, setup and mutant cost for the
    `heavy` ones, whose `parts` (by the mutant number's last digit) go to different shards. A
    shard holding a part runs only the mutants its globs name; every other shard runs all of its
    files."""
    units: list[str] = []
    weight: dict[str, int] = {}
    for rel in files:
        cost = heavy.get(rel)
        if cost is None:
            units.append(rel)
            weight[rel] = lines.get(rel, 0)
            continue
        each = WEEKLY_SETUP_SECONDS_PER_LINE + cost.seconds_per_line / cost.parts
        ordinary = WEEKLY_SETUP_SECONDS_PER_LINE + WEEKLY_BASE_SECONDS_PER_LINE
        for digits in digit_parts(cost.parts) if cost.parts > 1 else [""]:
            unit = f"{rel}{_PART}{digits}" if digits else rel
            units.append(unit)
            weight[unit] = round(lines.get(rel, 0) * each / ordinary)
    plans: list[ShardPlan] = []
    for bucket in shards(units, count, weight, apart=lambda u: u.split(_PART, 1)[0]):
        split = any(_PART in u for u in bucket)
        mutants: list[str] = []
        for unit in bucket if split else []:
            rel, _, digits = unit.partition(_PART)
            mutants += mutant_globs(rel, digits or None)
        plans.append(ShardPlan(sorted({u.split(_PART, 1)[0] for u in bucket}), mutants))
    return plans


_ONLY_MUTATE = re.compile(r"(?ms)^only_mutate = \[\n.*?^\]\n")


def narrow(pyproject_text: str, files: Sequence[str]) -> str:
    """pyproject.toml with `[tool.mutmut] only_mutate` replaced by exactly these files."""
    if _ONLY_MUTATE.search(pyproject_text) is None:
        raise ValueError("pyproject.toml has no multi-line `only_mutate = [` in [tool.mutmut]")
    body = "".join(f'    "{f}",\n' for f in files)
    return _ONLY_MUTATE.sub(lambda _m: f"only_mutate = [\n{body}]\n", pyproject_text, count=1)


def prepare(backend: Path = BACKEND) -> list[str]:
    """Link each top-level repository entry into backend/ (skipping names backend/ already has),
    and backend/backend to backend/ itself; the runner's checkout only. Returns the names linked.

    mutmut runs from backend/mutants/, so `Path(__file__).parents[n]` in a copied test or tool
    stops one level short: what was the repository root is backend/, and every
    `<root>/backend/...` read would miss. The self link makes those paths resolve to the real
    files (Q-03-T147). Python's `rglob` and `os.walk` do not follow it, so nothing loops."""
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


def _decided(code: int | None) -> int:
    """How much a mutant's exit code says: a result, a mutant mutmut skipped, or none."""
    return 0 if code is None else 1 if code in NOT_RUN else 2


def merge_metas(metas: Sequence[dict[str, object]]) -> dict[str, object]:
    """One `.meta` from several shards' copies for the same source: per mutant, the shard that
    decided it wins over one that did not run it (TASK-7818: a split file's parts)."""
    codes: dict[str, int | None] = {}
    durations: dict[str, object] = {}
    merged: dict[str, object] = {}
    for meta in metas:
        merged.update({k: v for k, v in meta.items() if k not in merged})
        theirs = cast(dict[str, int | None], meta.get("exit_code_by_key") or {})
        timed = cast(dict[str, object], meta.get("durations_by_key") or {})
        for mutant, code in theirs.items():
            if mutant not in codes or _decided(code) > _decided(codes[mutant]):
                codes[mutant] = code
                if mutant in timed:
                    durations[mutant] = timed[mutant]
    merged["exit_code_by_key"] = codes
    merged["durations_by_key"] = durations
    return merged


def read_metas(*roots: Path) -> dict[str, dict[str, object]]:
    """mutmut keeps one `<source path>.meta` JSON per mutated file under `mutants/`; given one
    folder per shard, the copies of one source's `.meta` are merged."""
    found: dict[str, list[dict[str, object]]] = {}
    for root in roots:
        for meta in sorted(root.rglob("*.py.meta")):
            source = meta.relative_to(root).as_posix().removesuffix(".meta")
            parsed = cast(dict[str, object], json.loads(meta.read_text(encoding="utf-8")))
            found.setdefault(source, []).append(parsed)
    return {source: merge_metas(copies) for source, copies in sorted(found.items())}


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
        mutants: list[str] = []
    else:
        every = red_files()
        lines = {f: _lines(BACKEND, f) for f in every}
        shard, count = cast(int, args.shard), cast(int, args.shards)
        plan = weekly_plan(every, count, lines)[shard - 1]
        files, mutants = plan.files, plan.mutants
    payload = {"files": files, "mutants": mutants}
    Path(args.out).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"mutation plan ({args.kind}): {len(files)} red files, {len(mutants)} mutant globs")
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
    roots = [Path(p) for p in cast(list[str], args.mutants) if Path(p).is_dir()]
    results = tally(read_metas(*roots)) if roots else {}
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
    summary.add_argument("--mutants", nargs="+", default=["mutants"])
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
