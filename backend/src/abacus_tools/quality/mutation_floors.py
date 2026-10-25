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
import ast
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import cast

GIT = shutil.which("git") or "/usr/bin/git"
REPO = Path(__file__).resolve().parents[4]
FILE = REPO / "backend" / "mutation-thresholds.yaml"
REL = "backend/mutation-thresholds.yaml"
# The mutation scope is protected with the floors: narrowing it would drop a floor unmeasured.
PYPROJECT_REL = "backend/pyproject.toml"
DRIVER_REL = "backend/src/abacus_tools/quality/mutation.py"

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


def _git_show(ref: str, rel: str = REL) -> str | None:
    result = subprocess.run(
        [GIT, "-C", str(REPO), "show", f"{ref}:{rel}"],
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


def scopes_of(driver_source: str) -> dict[str, set[str]]:
    """`SCOPES` in abacus_tools.quality.mutation, read from source (the base's or the head's)."""
    for node in ast.walk(ast.parse(driver_source)):
        target = node.target if isinstance(node, ast.AnnAssign) else None
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
        value = getattr(node, "value", None)
        if isinstance(target, ast.Name) and target.id == "SCOPES" and isinstance(value, ast.Dict):
            found: dict[str, set[str]] = {}
            for key, globs in zip(value.keys, value.values, strict=True):
                if isinstance(key, ast.Constant) and isinstance(globs, ast.Tuple):
                    found[str(key.value)] = {
                        str(g.value) for g in globs.elts if isinstance(g, ast.Constant)
                    }
            return found
    return {}


def _mutmut(pyproject: str) -> dict[str, object]:
    tool = cast(dict[str, object], tomllib.loads(pyproject).get("tool", {}))
    return cast(dict[str, object], tool.get("mutmut", {}))


def _strings(config: dict[str, object], key: str) -> set[str]:
    raw: object = config.get(key) or []
    return {str(v) for v in cast(list[object], raw)} if isinstance(raw, list) else set()


def narrowed(
    base_pyproject: str | None,
    head_pyproject: str,
    base_driver: str | None,
    head_driver: str,
) -> list[str]:
    """What the head narrows in the mutation scope: a red scope or glob removed from SCOPES,
    `only_mutate` or the test selection; a pattern added to `do_not_mutate`; other run arguments
    changed. Widening is a normal change."""
    found: list[str] = []
    if base_driver is not None:
        base_scopes, head_scopes = scopes_of(base_driver), scopes_of(head_driver)
        for scope, globs in sorted(base_scopes.items()):
            missing = sorted(globs - head_scopes.get(scope, set()))
            if scope not in head_scopes:
                found.append(f"{DRIVER_REL}: SCOPES drops the {scope} scope")
            elif missing:
                found.append(f"{DRIVER_REL}: SCOPES[{scope!r}] drops {missing}")
    if base_pyproject is not None:
        base, head = _mutmut(base_pyproject), _mutmut(head_pyproject)
        if base:
            for key in ("only_mutate", "pytest_add_cli_args_test_selection"):
                gone = sorted(_strings(base, key) - _strings(head, key))
                if gone:
                    found.append(f"{PYPROJECT_REL}: [tool.mutmut] {key} drops {gone}")
            added = sorted(_strings(head, "do_not_mutate") - _strings(base, "do_not_mutate"))
            if added:
                found.append(f"{PYPROJECT_REL}: [tool.mutmut] do_not_mutate adds {added}")
            for key in ("source_paths", "pytest_add_cli_args"):
                if base.get(key) != head.get(key):
                    found.append(f"{PYPROJECT_REL}: [tool.mutmut] {key} changed")
    return found


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
    parser.add_argument(
        "--head-root",
        type=Path,
        default=REPO,
        help="the checkout whose files are judged (mutation-floors.yml runs the base's guard "
        "from a base worktree against the pull request's checkout)",
    )
    args = parser.parse_args(argv)
    root = cast(Path, args.head_root)
    head_text = (root / REL).read_text(encoding="utf-8")
    ref: str | None
    if args.base:
        if not _reachable(args.base):
            print(f"mutation floors: base {args.base} is not reachable; fetch full history")
            return 1
        ref = cast(str, args.base)
    elif _reachable("origin/main"):
        ref = "origin/main"
    else:
        print("mutation floors: origin/main is not reachable; format checked only")
        ref = None
    problems = check(head_text, None if ref is None else _git_show(ref))
    if ref is not None:
        problems += narrowed(
            _git_show(ref, PYPROJECT_REL),
            (root / PYPROJECT_REL).read_text(encoding="utf-8"),
            _git_show(ref, DRIVER_REL),
            (root / DRIVER_REL).read_text(encoding="utf-8"),
        )
    for problem in problems:
        print(f"{problem} (floors and their scope are only raised: ADR-079, QD-4)")
    if not problems:
        print(f"mutation floors: {len(parse(head_text))} scopes, none lowered or narrowed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
