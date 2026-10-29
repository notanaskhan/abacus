"""Red batch and main runs and their time to green (Q-03-T087; Q-03 §3.6, the integration lane).

    gh run list -R notanaskhan/abacus --workflow ci --limit 500 \
        --json databaseId,headBranch,headSha,conclusion,status,createdAt,updatedAt,event \
        > runs.json
    python -m abacus_tools.ci.integration_lane --runs runs.json [--since 2027-04-01] [--md out.md]

The lane's acceptance: every red batch run of the period is resolved within one working day. A run
is **red** when it completed with `failure` or `timed_out` on `main` or on a batch branch
(`review-*`, `batch-*`); it is **resolved** at the completion of the next `success` on the same
branch (cancelled and skipped runs neither break nor resolve). The time between counts working days
only (Monday to Friday, in UTC; a weekend does not count against the lane). A red run that is still
unresolved counts up to now.

The report lists each red streak (the first red run and the green that ended it), its working-day
age, and whether it breached one day. Exit 1 when any streak breached; 0 otherwise. It reads the
run list only: it never re-runs, cancels or comments.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Final, cast

from abacus.kernel.clock import system_now

BATCH_BRANCH: Final = re.compile(r"^(main|review-[\w.-]+|batch-[\w.-]+)$")
RED: Final = frozenset({"failure", "timed_out"})
GREEN: Final = "success"
LIMIT: Final = timedelta(days=1)


@dataclass(frozen=True)
class Run:
    id: int
    branch: str
    sha: str
    conclusion: str
    finished: datetime


@dataclass(frozen=True)
class Streak:
    branch: str
    first_red: Run
    green: Run | None
    reds: int

    def age(self, now: datetime) -> timedelta:
        return working_time(self.first_red.finished, self.green.finished if self.green else now)

    def breached(self, now: datetime) -> bool:
        return self.age(now) > LIMIT


def _when(value: object) -> datetime:
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(UTC)


def runs(raw: Iterable[dict[str, object]]) -> list[Run]:
    """Completed runs on main and batch branches, oldest first."""
    found: list[Run] = []
    for item in raw:
        branch = str(item.get("headBranch", ""))
        conclusion = str(item.get("conclusion") or "")
        if item.get("status") not in (None, "completed") or not BATCH_BRANCH.match(branch):
            continue
        if conclusion not in RED and conclusion != GREEN:
            continue
        found.append(
            Run(
                id=int(cast(int, item["databaseId"])),
                branch=branch,
                sha=str(item.get("headSha", ""))[:8],
                conclusion=conclusion,
                finished=_when(item.get("updatedAt") or item.get("createdAt")),
            )
        )
    return sorted(found, key=lambda r: (r.finished, r.id))


def working_time(start: datetime, end: datetime) -> timedelta:
    """The part of [start, end) that falls on Monday to Friday (UTC)."""
    if end <= start:
        return timedelta(0)
    total = timedelta(0)
    cursor = start
    while cursor < end:
        midnight = datetime.combine(cursor.date() + timedelta(days=1), datetime.min.time(), UTC)
        step_end = min(end, midnight)
        if cursor.weekday() < 5:
            total += step_end - cursor
        cursor = step_end
    return total


def streaks(found: Sequence[Run]) -> list[Streak]:
    by_branch: dict[str, list[Run]] = defaultdict(list)
    for run in found:
        by_branch[run.branch].append(run)
    out: list[Streak] = []
    for branch, items in by_branch.items():
        first: Run | None = None
        reds = 0
        for run in items:
            if run.conclusion in RED:
                if first is None:
                    first = run
                reds += 1
            elif first is not None:
                out.append(Streak(branch, first, run, reds))
                first, reds = None, 0
        if first is not None:
            out.append(Streak(branch, first, None, reds))
    return sorted(out, key=lambda s: s.first_red.finished)


def _days(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 86400:.2f}"


def report(found: Sequence[Streak], now: datetime) -> str:
    head = (
        "| Branch | First red | Red runs | Resolved by | Working days | Within 1 day |\n"
        "|---|---|---|---|---|---|\n"
    )
    rows = "".join(
        f"| `{s.branch}` | run {s.first_red.id} (`{s.first_red.sha}`) "
        f"{s.first_red.finished:%Y-%m-%d %H:%M} | {s.reds} | "
        + (
            f"run {s.green.id} (`{s.green.sha}`) {s.green.finished:%Y-%m-%d %H:%M}"
            if s.green
            else "**still red**"
        )
        + f" | {_days(s.age(now))} | {'no' if s.breached(now) else 'yes'} |\n"
        for s in found
    )
    return head + (rows or "| — | no red run in the period | — | — | — | — |\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.ci.integration_lane", description=__doc__)
    parser.add_argument("--runs", type=Path, required=True, help="`gh run list --json` output")
    parser.add_argument("--since", type=date.fromisoformat, help="the period's first day")
    parser.add_argument("--md", type=Path, help="write the table to this file as well")
    args = parser.parse_args(argv)
    raw = cast(list[dict[str, object]], json.loads(args.runs.read_text(encoding="utf-8")))
    found = runs(raw)
    if args.since is not None:
        found = [r for r in found if r.finished.date() >= args.since]
    now = system_now().astimezone(UTC)
    lane = streaks(found)
    table = report(lane, now)
    if args.md is not None:
        args.md.write_text(table, encoding="utf-8")
    print(table)
    return 1 if any(s.breached(now) for s in lane) else 0


if __name__ == "__main__":
    sys.exit(main())
