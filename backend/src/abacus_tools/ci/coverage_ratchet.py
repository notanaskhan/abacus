"""Total coverage never drops below the figure main last recorded (CV-1; DEC-6005; F-01-T05).

Run from backend/:
- `python -m abacus_tools.ci.coverage_ratchet` (in `make check-fast`):
  `backend/coverage-baseline.toml` is well formed and its total is not lower than, or gone
  from, `origin/main`'s (format only when that ref is not reachable, as `coverage_floors`).
- `python -m abacus_tools.ci.coverage_ratchet --measure` (in `make ci-coverage`, after
  `coverage combine`, before the floor): the combined total, to two decimals, is not under the
  recorded total. A total more than half a point above it asks for the file to be raised.

The floor (`fail_under` 95, with DEC-10's dated exception) is `coverage_floor`'s to judge. This
guard catches a change that lowers coverage while the total is still under that floor, so the
back-fill (DEC-6003) only moves one way. The recorded total is only ever raised.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final

GIT = shutil.which("git") or "/usr/bin/git"
BACKEND = Path(__file__).resolve().parents[3]
REPO = BACKEND.parent
REL: Final = "backend/coverage-baseline.toml"
FILE: Final = REPO / REL
RAISE_AFTER: Final = Decimal("0.50")
_TOTAL = re.compile(r"^\d{1,3}(?:\.\d{1,2})?$")


class BaselineInvalid(ValueError):
    """The baseline file, or coverage's total, is not in the form this guard reads."""


@dataclass(frozen=True)
class Baseline:
    decision: str
    measured_on: str
    run: str
    total: Decimal


def parse(text: str) -> Baseline:
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise BaselineInvalid("the baseline is not TOML") from exc
    decision = data.get("decision")
    if not isinstance(decision, str) or not decision.startswith("DEC-"):
        raise BaselineInvalid('the baseline names its decision (decision = "DEC-nn")')
    measured_on = data.get("measured_on")
    if not isinstance(measured_on, str) or not measured_on:
        raise BaselineInvalid("the baseline names the commit it was measured on (measured_on)")
    run = data.get("run")
    if not isinstance(run, str) or not run:
        raise BaselineInvalid("the baseline names the CI run that measured it (run)")
    raw = data.get("total")
    if isinstance(raw, bool) or not isinstance(raw, int | float):
        raise BaselineInvalid("the baseline has a total between 0 and 100")
    total = Decimal(str(raw))
    if not Decimal("0") <= total <= Decimal("100"):
        raise BaselineInvalid("the baseline has a total between 0 and 100")
    if total != total.quantize(Decimal("0.01")):
        raise BaselineInvalid("the total has at most two decimals")
    return Baseline(decision, measured_on, run, total)


def check(head_text: str | None, base_text: str | None) -> list[str]:
    """Stage 1: the head's baseline is well formed and not lower than the base's."""
    base: Baseline | None = None
    if base_text is not None:
        try:
            base = parse(base_text)
        except BaselineInvalid:
            base = None  # the base predates the format; the head is what is checked
    if head_text is None:
        return (
            [] if base is None else [f"{REL}: the baseline was removed (it was {base.total:.2f})"]
        )
    try:
        head = parse(head_text)
    except BaselineInvalid as exc:
        return [f"{REL}: {exc}"]
    if base is not None and head.total < base.total:
        return [f"{REL}: total {base.total:.2f} lowered to {head.total:.2f}"]
    return []


def judge(baseline: Baseline, measured: Decimal) -> list[str]:
    """Stage 2: the measured total is not under the recorded one."""
    if measured < baseline.total:
        return [
            f"total coverage {measured:.2f}% is under main's recorded {baseline.total:.2f}% "
            f"({baseline.decision})"
        ]
    return []


def advice(baseline: Baseline, measured: Decimal) -> str | None:
    """A total well above the record asks for the record to be raised (never a failure)."""
    if measured - baseline.total > RAISE_AFTER:
        return (
            f"total coverage {measured:.2f}% is above the recorded {baseline.total:.2f}%: "
            f"raise {REL} to {measured:.2f} with this change"
        )
    return None


def read_total(output: str) -> Decimal:
    """`coverage report --format=total --precision=2` prints the total alone."""
    text = output.strip()
    if not _TOTAL.match(text):
        raise BaselineInvalid(f"coverage report gave no total: {text!r}")
    return Decimal(text)


def _measured_total() -> Decimal:
    coverage = shutil.which("coverage")
    if coverage is None:
        raise RuntimeError("coverage is not installed")
    # `--fail-under=0`: the floor is coverage_floor's to judge; here only the figure is wanted.
    result = subprocess.run(
        [coverage, "report", "--format=total", "--precision=2", "--fail-under=0"],
        cwd=BACKEND,
        capture_output=True,
        text=True,
        check=True,
    )
    return read_total(result.stdout)


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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    parser.add_argument("--measure", action="store_true", help="judge the combined coverage data")
    args = parser.parse_args(argv)
    head_text = FILE.read_text(encoding="utf-8") if FILE.exists() else None
    if args.measure:
        if head_text is None:
            print(f"coverage ratchet: {REL} is missing")
            return 1
        try:
            baseline = parse(head_text)
            measured = _measured_total()
        except BaselineInvalid as exc:
            print(f"coverage ratchet: {exc}")
            return 1
        print(
            f"coverage ratchet: total {measured:.2f}% against the recorded "
            f"{baseline.total:.2f}% ({baseline.measured_on}, run {baseline.run})"
        )
        note = advice(baseline, measured)
        if note is not None:
            print(f"coverage ratchet: {note}")
        problems = judge(baseline, measured)
    else:
        ref = "origin/main" if _reachable("origin/main") else None
        if ref is None:
            print("coverage ratchet: origin/main is not reachable; format checked only")
        problems = check(head_text, None if ref is None else _git_show(ref))
    for problem in problems:
        print(f"coverage ratchet: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
