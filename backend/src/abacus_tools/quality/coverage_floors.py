"""Coverage floors per red module (Q-03-T066; ADR-079; DEC-907).

Run from backend/:
- `python -m abacus_tools.quality.coverage_floors` (in `make check-fast`): the floors in
  `backend/coverage-thresholds.yaml` are well formed and none is lower, or gone, than at
  `origin/main` (format only when that ref is not reachable, as `mutation_floors`).
- `python -m abacus_tools.quality.coverage_floors --measure` (in `make ci-coverage`, after
  `coverage combine`): each red module's line and branch coverage from the combined data meets its
  floor; a module with no measured file (`compute` until a package exists) is skipped.

The red modules are `abacus_tools.quality.mutation.SCOPES` (the same globs, the same generated
files left out). The global floor stays `[tool.coverage.report] fail_under` (`coverage_floor`).
"""

from __future__ import annotations

import argparse
import fnmatch
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Final, cast

from abacus_tools.quality.mutation import GENERATED, SCOPES

GIT = shutil.which("git") or "/usr/bin/git"
BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent
REL: Final = "backend/coverage-thresholds.yaml"
FILE: Final = REPO / REL
KINDS: Final = ("line", "branch")

_FLOOR = re.compile(r"^  ([a-z0-9_]+(?:/[a-z0-9_]+)*):\s*(\d{1,3})\s*(?:#.*)?$")
_TOP = re.compile(r"^([a-z_]+):\s*(\S.*)?$")

Floors = dict[str, dict[str, int]]  # {"line": {module: percent}, "branch": {...}}


class FloorsInvalid(ValueError):
    """The thresholds file is not in the format this guard reads."""


def parse(text: str) -> Floors:
    """The `line:` and `branch:` blocks. Strict: anything else under them is an error."""
    floors: Floors = {kind: {} for kind in KINDS}
    block: str | None = None
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        top = _TOP.match(line)
        if top is not None:
            block = top.group(1) if top.group(1) in KINDS and top.group(2) is None else None
            continue
        if block is None:
            raise FloorsInvalid(f"line {number}: {line!r} is outside a line or branch block")
        floor = _FLOOR.match(line)
        if floor is None:
            raise FloorsInvalid(f"line {number}: {line!r} is not `  <module>: <0-100>`")
        module, value = floor.group(1), int(floor.group(2))
        if value > 100:
            raise FloorsInvalid(f"line {number}: {module} {block} floor {value} is over 100")
        if module in floors[block]:
            raise FloorsInvalid(f"line {number}: {module} is listed twice under {block}")
        floors[block][module] = value
    for kind in KINDS:
        if not floors[kind]:
            raise FloorsInvalid(f"no {kind} floors: the file needs a `{kind}:` block")
    unknown = sorted((set(floors["line"]) | set(floors["branch"])) - set(SCOPES))
    if unknown:
        raise FloorsInvalid(f"{unknown} are not red modules (mutation.SCOPES)")
    return floors


def lowered(base: Floors, head: Floors) -> list[str]:
    """Each floor the head lowers or drops, worded for the refusal."""
    found: list[str] = []
    for kind in KINDS:
        for module, floor in sorted(base.get(kind, {}).items()):
            if module not in head.get(kind, {}):
                found.append(f"{module}: the {kind} floor ({floor}) was removed")
            elif head[kind][module] < floor:
                found.append(f"{module}: {kind} {floor} lowered to {head[kind][module]}")
    return found


@dataclass(frozen=True)
class Measured:
    files: int
    statements: int
    missing: int
    branches: int
    covered_branches: int

    @property
    def line(self) -> float:
        return (
            100.0
            if not self.statements
            else (self.statements - self.missing) * 100 / self.statements
        )

    @property
    def branch(self) -> float:
        return 100.0 if not self.branches else self.covered_branches * 100 / self.branches


def _relative(path: str) -> str:
    """A measured file as a backend-relative path (`src/abacus/...`), however it was recorded."""
    marker = path.find("src/abacus")
    return path[marker:] if marker >= 0 else path


def measure(report: Mapping[str, object]) -> dict[str, Measured]:
    """Per red module, from `coverage json`'s report (its `files` summaries)."""
    files = cast(dict[str, dict[str, dict[str, int]]], report["files"])
    out: dict[str, Measured] = {}
    for module, globs in SCOPES.items():
        st = mi = br = cb = n = 0
        for path, entry in files.items():
            rel = _relative(path)
            if rel.endswith(GENERATED) or not any(fnmatch.fnmatch(rel, g) for g in globs):
                continue
            summary = entry["summary"]
            n += 1
            st += summary["num_statements"]
            mi += summary["missing_lines"]
            br += summary.get("num_branches", 0)
            cb += summary.get("covered_branches", 0)
        out[module] = Measured(n, st, mi, br, cb)
    return out


def below(floors: Floors, measured: Mapping[str, Measured]) -> list[str]:
    """Each red module under a floor; a module with no measured file is not judged."""
    found: list[str] = []
    for module in sorted(set(floors["line"]) | set(floors["branch"])):
        got = measured.get(module)
        if got is None or got.files == 0:
            continue
        for kind, value in (("line", got.line), ("branch", got.branch)):
            floor = floors[kind].get(module)
            if floor is not None and value < floor:
                found.append(f"{module}: {kind} {value:.1f}% is under its floor {floor}%")
    return found


def _git_show(ref: str) -> str | None:
    result = subprocess.run(
        [GIT, "-C", str(REPO), "show", f"{ref}:{REL}"], capture_output=True, text=True, check=False
    )
    return result.stdout if result.returncode == 0 else None


def _reachable(ref: str) -> bool:
    result = subprocess.run(
        [GIT, "-C", str(REPO), "rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def check(head_text: str, base_text: str | None) -> list[str]:
    try:
        head = parse(head_text)
    except FloorsInvalid as exc:
        return [f"{REL}: {exc}"]
    if base_text is None:
        return []
    try:
        base = parse(base_text)
    except FloorsInvalid:
        return []  # the base predates the file or its format; the head is what is checked
    return [f"{REL}: {problem}" for problem in lowered(base, head)]


def _report() -> dict[str, object]:
    coverage = shutil.which("coverage")
    if coverage is None:
        raise RuntimeError("coverage is not installed")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "coverage.json"
        # `--fail-under=0`: the global floor is coverage_floor's to judge (with its dated DEC-10
        # exception); here `coverage json` must write the report, not exit 2 below pyproject's 95.
        subprocess.run(
            [coverage, "json", "-q", "--fail-under=0", "-o", str(out)], cwd=BACKEND, check=True
        )
        return cast(dict[str, object], json.loads(out.read_text(encoding="utf-8")))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--measure", action="store_true", help="judge the combined coverage data")
    args = parser.parse_args(argv)
    text = FILE.read_text(encoding="utf-8")
    if args.measure:
        try:
            floors = parse(text)
        except FloorsInvalid as exc:
            print(f"coverage floors: {REL}: {exc}")
            return 1
        measured = measure(_report())
        for module, got in sorted(measured.items()):
            if got.files:
                print(f"coverage floors: {module}: line {got.line:.1f}%, branch {got.branch:.1f}%")
        problems = below(floors, measured)
    else:
        ref = "origin/main" if _reachable("origin/main") else None
        if ref is None:
            print("coverage floors: origin/main is not reachable; format checked only")
        problems = check(text, None if ref is None else _git_show(ref))
    for problem in problems:
        print(f"coverage floors: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
