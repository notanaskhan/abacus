"""The x1 smoke's p95 trend (Q-03-T043; Q-03 E1; chapter 10 section 10.11.5).

Run: python -m abacus_tools.loadtest.trend --history DIR [--profile x1_smoke]
         [--out trend.json] [--ticket ticket.md]

Reads the harness's JSON reports (`run.write_report`) for one profile from DIR, takes the newest
as this run, and compares each endpoint group's p95 with the median p95 of the same group over the
runs in the four weeks before it. A rise of more than 20% over that median is a regression: the
command writes a ticket body (results only: group, p95, median, rise, run times; never a host,
token, tenant or request) and exits 1, so the step that runs it opens the ticket. With fewer than
`MIN_HISTORY` earlier runs a group has no median yet and is reported as such, never as a pass.

`--out` writes the trend as JSON for the weekly quality report (`quality.report` reads it as
`loadtest-trend.json` among its inputs). Files only: no network, no database.
Exit codes: 0 no regression, 1 a regression (ticket written), 2 nothing to compare.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Final, cast

WINDOW: Final = timedelta(weeks=4)
RISE: Final = 0.20  # a p95 more than 20% over its 4-week median opens a ticket
MIN_HISTORY: Final = 2
SMOKE_PROFILE: Final = "x1_smoke"


@dataclass(frozen=True)
class GroupTrend:
    name: str
    p95_ms: float | None
    median_p95_ms: float | None
    rise: float | None  # 0.25 is 25% over the median
    runs_in_median: int
    regressed: bool


@dataclass(frozen=True)
class Trend:
    profile: str
    run_started_at: str
    groups: list[GroupTrend]

    @property
    def regressed(self) -> list[GroupTrend]:
        return [g for g in self.groups if g.regressed]


def _started(report: dict[str, object]) -> datetime:
    return datetime.fromisoformat(str(report["started_at"]))


def _p95s(report: dict[str, object]) -> dict[str, float | None]:
    groups = cast(list[dict[str, object]], report.get("groups", []))
    found: dict[str, float | None] = {}
    for group in groups:
        value = group.get("p95_ms")
        found[str(group["name"])] = float(cast(float, value)) if value is not None else None
    return found


def trend(reports: Sequence[dict[str, object]], profile: str = SMOKE_PROFILE) -> Trend | None:
    """The newest report of `profile` against the 4-week median of the ones before it."""
    mine = sorted((r for r in reports if r.get("scenario") == profile), key=_started)
    if not mine:
        return None
    latest = mine[-1]
    since = _started(latest) - WINDOW
    earlier = [r for r in mine[:-1] if _started(r) >= since]
    groups: list[GroupTrend] = []
    for name, p95 in sorted(_p95s(latest).items()):
        history = [v for r in earlier if (v := _p95s(r).get(name)) is not None]
        if len(history) < MIN_HISTORY or p95 is None:
            groups.append(GroupTrend(name, p95, None, None, len(history), False))
            continue
        median = statistics.median(history)
        rise = (p95 - median) / median if median > 0 else None
        regressed = rise is not None and rise > RISE
        groups.append(
            GroupTrend(name, p95, round(median, 1), _round(rise), len(history), regressed)
        )
    return Trend(profile, str(latest["started_at"]), groups)


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 4)


def ticket(found: Trend) -> str:
    """The ticket body for a regression: results only."""
    lines = [
        f"# Load smoke regression: {found.profile} at {found.run_started_at}",
        "",
        f"p95 rose more than {RISE:.0%} over its 4-week median (chapter 10 section 10.11.5). "
        "Triage as a reliability item (ADR-093); the runbook is docs/ops/loadtests/README.md.",
        "",
        "| Group | p95 ms | 4-week median ms | Rise | Runs in median |",
        "|---|---|---|---|---|",
    ]
    for g in found.regressed:
        lines.append(
            f"| {g.name} | {g.p95_ms} | {g.median_p95_ms} | {(g.rise or 0):.0%} | "
            f"{g.runs_in_median} |"
        )
    return "\n".join(lines) + "\n"


def load_reports(history: Path) -> list[dict[str, object]]:
    found: list[dict[str, object]] = []
    for path in sorted(history.glob("*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(value, dict) and "scenario" in value and "started_at" in value:
            found.append(cast(dict[str, object], value))
    return found


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.loadtest.trend", description=__doc__)
    parser.add_argument("--history", type=Path, required=True)
    parser.add_argument("--profile", default=SMOKE_PROFILE)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--ticket", type=Path, default=None)
    args = parser.parse_args(list(argv))
    found = trend(load_reports(args.history), args.profile)
    if found is None:
        print(f"no {args.profile} report in {args.history}", file=sys.stderr)
        return 2
    data = {**asdict(found), "regressed": [g.name for g in found.regressed]}
    if args.out is not None:
        args.out.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    for g in found.groups:
        state = "regressed" if g.regressed else ("no median yet" if g.rise is None else "ok")
        print(f"{g.name}: p95 {g.p95_ms} ms, median {g.median_p95_ms} ms, {state}")
    if found.regressed:
        if args.ticket is not None:
            args.ticket.write_text(ticket(found), encoding="utf-8")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
