"""The coverage floor, with a dated exception (ADR-079; DEC-10; F-01-T05).

Run: python -m abacus_tools.ci.coverage_floor     (after `coverage combine`)

The floor is `[tool.coverage.report] fail_under` in backend/pyproject.toml (95) and is never
lowered. `backend/coverage-exception.toml`, when present, is the one exception DEC-10 allows: it
names its decision, steps that only ratchet up toward the floor, and a date it expires, after
which the floor applies in full. This tool runs `coverage report --fail-under=<today's floor>`.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import cast

from abacus.kernel.clock import system_now

BACKEND = Path(__file__).resolve().parents[3]
PYPROJECT = BACKEND / "pyproject.toml"
EXCEPTION = BACKEND / "coverage-exception.toml"


class ExceptionInvalid(ValueError):
    pass


@dataclass(frozen=True)
class Step:
    starts: date
    minimum: int


@dataclass(frozen=True)
class CoverageException:
    decision: str
    expires: date
    steps: tuple[Step, ...]


def configured_floor(pyproject: Path = PYPROJECT) -> int:
    data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    report = cast(dict[str, object], data["tool"]["coverage"]["report"])
    return int(cast(int, report["fail_under"]))


def load(path: Path = EXCEPTION, floor: int = 95) -> CoverageException | None:
    """The exception, validated; None when there is no file."""
    if not path.exists():
        return None
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    decision = data.get("decision")
    if not isinstance(decision, str) or not decision.startswith("DEC-"):
        raise ExceptionInvalid('an exception names its decision (decision = "DEC-nn")')
    expires = data.get("expires")
    if not isinstance(expires, date):
        raise ExceptionInvalid("an exception expires on a date (expires = YYYY-MM-DD)")
    raw = data.get("steps")
    if not isinstance(raw, list) or not raw:
        raise ExceptionInvalid("an exception has at least one step")
    steps: list[Step] = []
    for item in cast(list[dict[str, object]], raw):
        starts, minimum = item.get("from"), item.get("min")
        if not isinstance(starts, date) or not isinstance(minimum, int):
            raise ExceptionInvalid("each step has a from date and an integer min")
        if steps and starts <= steps[-1].starts:
            raise ExceptionInvalid("steps are in date order")
        if steps and minimum < steps[-1].minimum:
            raise ExceptionInvalid("steps only ratchet up toward the floor")
        if minimum >= floor:
            raise ExceptionInvalid(f"every step is below the floor ({floor})")
        steps.append(Step(starts, minimum))
    if expires <= steps[0].starts:
        raise ExceptionInvalid("expires is after the first step")
    return CoverageException(decision, expires, tuple(steps))


def effective_floor(floor: int, exception: CoverageException | None, today: date) -> int:
    """Today's floor: the latest step that has started, until the exception expires."""
    if exception is None or today >= exception.expires:
        return floor
    started = [s.minimum for s in exception.steps if s.starts <= today]
    return started[-1] if started else floor


def main() -> int:
    floor = configured_floor()
    exception = load(floor=floor)
    today_floor = effective_floor(floor, exception, system_now().date())
    if exception is not None and today_floor < floor:
        print(
            f"coverage floor {floor}; exception {exception.decision} until "
            f"{exception.expires.isoformat()}: today's floor is {today_floor}"
        )
    coverage = shutil.which("coverage")
    if coverage is None:
        print("coverage is not installed", file=sys.stderr)
        return 2
    return subprocess.run(
        [coverage, "report", f"--fail-under={today_floor}"], cwd=BACKEND, check=False
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
