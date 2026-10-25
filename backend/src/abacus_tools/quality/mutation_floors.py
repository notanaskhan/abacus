"""Mutation floors only rise (Q-03-T027; QD-4; ADR-079; DEC-365).

Run: python -m abacus_tools.quality.mutation_floors [--base REF]

`backend/mutation-thresholds.yaml` holds one floor per red scope. This guard compares it with the
same file at a base ref and fails when a floor is lower or a scope is gone. Without `--base` it
compares with `origin/main` when that ref is reachable and otherwise only checks the format (stage
1 checks out one commit; `mutation-floors.yml` passes the pull request's base with full history,
and there an unreachable base fails). The edit hook (`.claude/hooks/_protected.py`) applies the
same rule to an agent's edit before it lands; its parser is a Python 3.9 copy of `parse` below,
kept in step by `tests/unit/quality/test_mutation_floors.py`.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

GIT = shutil.which("git") or "/usr/bin/git"
REPO = Path(__file__).resolve().parents[4]
FILE = REPO / "backend" / "mutation-thresholds.yaml"
REL = "backend/mutation-thresholds.yaml"

_FLOOR = re.compile(r"^  ([a-z0-9_]+(?:/[a-z0-9_]+)*):\s*(\d{1,3})\s*(?:#.*)?$")
_TOP = re.compile(r"^([a-z_]+):\s*(\S.*)?$")


class FloorsInvalid(ValueError):
    """The thresholds file is not in the format the hook and this guard can read."""


def parse(text: str) -> dict[str, int]:
    """The `floors:` block as {scope: percent}. Strict: anything else under it is an error."""
    floors: dict[str, int] = {}
    inside = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        top = _TOP.match(line)
        if top is not None:
            inside = top.group(1) == "floors" and top.group(2) is None
            continue
        if not inside:
            raise FloorsInvalid(f"line {number}: {line!r} is outside a known block")
        floor = _FLOOR.match(line)
        if floor is None:
            raise FloorsInvalid(f"line {number}: {line!r} is not `  <scope>: <0-100>`")
        scope, value = floor.group(1), int(floor.group(2))
        if value > 100:
            raise FloorsInvalid(f"line {number}: {scope} floor {value} is over 100")
        if scope in floors:
            raise FloorsInvalid(f"line {number}: {scope} is listed twice")
        floors[scope] = value
    if not floors:
        raise FloorsInvalid("no floors: the file needs a `floors:` block")
    return floors


def lowered(base: dict[str, int], head: dict[str, int]) -> list[str]:
    """Each floor the head lowers or drops, worded for the refusal."""
    found: list[str] = []
    for scope, floor in sorted(base.items()):
        if scope not in head:
            found.append(f"{scope}: the floor ({floor}) was removed")
        elif head[scope] < floor:
            found.append(f"{scope}: {floor} lowered to {head[scope]}")
    return found


def _git_show(ref: str) -> str | None:
    result = subprocess.run(
        [GIT, "-C", str(REPO), "show", f"{ref}:{REL}"],
        capture_output=True,
        text=True,
        check=False,
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
        return []  # the base predates the strict format; the head is what is checked
    return [f"{REL}: {problem}" for problem in lowered(base, head)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--base", help="the ref to compare with (required to be reachable)")
    args = parser.parse_args(argv)
    head_text = FILE.read_text(encoding="utf-8")
    if args.base:
        if not _reachable(args.base):
            print(f"mutation floors: base {args.base} is not reachable; fetch full history")
            return 1
        base_text = _git_show(args.base)
    elif _reachable("origin/main"):
        base_text = _git_show("origin/main")
    else:
        print("mutation floors: origin/main is not reachable; format checked only")
        base_text = None
    problems = check(head_text, base_text)
    for problem in problems:
        print(f"{problem} (floors are only raised: ADR-079, QD-4)")
    if not problems:
        print(f"mutation floors: {len(parse(head_text))} scopes, none lowered")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
