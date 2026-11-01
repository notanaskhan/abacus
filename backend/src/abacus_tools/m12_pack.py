"""The M12 ops evidence pack (Q-04-T054; F-09-T164 on Fri Aug 20; chapter 11 §11.6.2; DEC-1677).

Run: python -m abacus_tools.m12_pack --firm <id> [--firm <id> ...] --week <Monday> [--week ...]
     --sprint 19 --sprint 20 --sprint 21 [--hours-per-task 6] [--out docs/ops/pilot/m12-pack.md]
or   make m12-pack FIRMS="<ids>" WEEKS="<Mondays>" SPRINTS="19 20 21"

Everything in the pack is read, never estimated, so the other founder reproduces it byte for byte
from the same inputs (the row's acceptance):

- **W4 to W7 per firm and week** from `pilot_metric_snapshots` (`platform.api`): W4 and W5 through
  Q-04-T050's read (colour, counts, owner, action); W6 as the share faster than the enrolment's
  baseline (≥ 20% green, 0-19% amber, slower red at week 8 only, else amber); W7 per agent
  (≤ 8% green, 9-15% amber, > 15% amber with "red needs two months", which one week cannot show).
- **W2 and W8 per firm** as recorded in its go-live dossier (`docs/ops/go-live/<code>.md`): the
  dossier's level, and any `W2` or `W8` line the founders wrote there from `make shadow-report`.
  Neither is snapshotted, so the pack quotes the dossier and says where it came from.
- **Support hours** from `docs/ops/pilot/support-hours.csv` (sprint, week, lane, hours, SEV
  counts; no client data) against the sprint's support-reserve rows in `docs/plan/backlog.csv`
  (task-equivalents times hours per task), with RK-07's trigger (two sprints over the reserve).
- **SEV and escaped-defect log**: the SEV counts from the support log and the escaped-defect rows
  (`docs/quality/escaped-defects.md`) found inside the weeks read, by severity and state.

The header carries each input file's SHA-256 and the snapshot weeks, so a reproduction that
differs names the input that changed. A synthetic firm (PF-X1, DEC-1530) is labelled synthetic.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from itertools import pairwise
from pathlib import Path
from typing import Final
from uuid import UUID

from abacus.modules.platform.api import (
    FirmRead,
    PilotSnapshot,
    cross_firm,
    wedge_read,
    wedge_report,
    week_snapshots,
)

REPO: Final = Path(__file__).resolve().parents[3]
SUPPORT_LOG: Final = REPO / "docs/ops/pilot/support-hours.csv"
DEFECTS: Final = REPO / "docs/quality/escaped-defects.md"
BACKLOG: Final = REPO / "docs/plan/backlog.csv"
DOSSIERS: Final = REPO / "docs/ops/go-live"
SUPPORT_COLUMNS: Final = ("sprint", "week", "lane", "hours", "sev1", "sev2", "sev3")
W6_GREEN: Final = Decimal("0.20")
W6_RED_WEEK: Final = 8
W7_GREEN: Final = Decimal("0.08")
W7_AMBER: Final = Decimal("0.15")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "missing"


def _pct(value: Decimal | None) -> str:
    return "—" if value is None else f"{(value * 100).quantize(Decimal('0.1'))}%"


# --- W6 and W7 ------------------------------------------------------------------------------


def w6_faster(snapshot: PilotSnapshot) -> Decimal | None:
    """The share faster than baseline: (baseline - median) / baseline. None without a baseline."""
    if not snapshot.baseline_days:
        return None
    return (-snapshot.value / Decimal(snapshot.baseline_days)).quantize(Decimal("0.0001"))


def w6_colour(faster: Decimal | None, week_of_window: int) -> str:
    if faster is None:
        return "no data"
    if faster >= W6_GREEN:
        return "green"
    if faster >= 0:
        return "amber"
    return "red" if week_of_window >= W6_RED_WEEK else "amber"


def w7_colour(rate: Decimal) -> str:
    if rate <= W7_GREEN:
        return "green"
    return "amber"  # 9-15% amber; > 15% is red only for two consecutive months (a monthly read)


@dataclass(frozen=True)
class Row:
    firm: str
    week: date
    signal: str
    value: str
    counts: str
    colour: str
    note: str = ""


def w6_w7_rows(read: FirmRead, snapshots: Sequence[PilotSnapshot]) -> list[Row]:
    name = f"{read.firm_name} (synthetic)" if read.synthetic else read.firm_name
    rows: list[Row] = []
    w6 = [w6_faster(s) for s in snapshots if s.metric_key == "w6_vs_baseline_days.v1"]
    found = [v for v in w6 if v is not None]
    mean = (sum(found, Decimal(0)) / len(found)).quantize(Decimal("0.0001")) if found else None
    rows.append(
        Row(
            name,
            read.week_start,
            "W6 request → received vs baseline",
            _pct(mean) + (" faster" if mean is not None else ""),
            f"{len(found)} enrolment(s) with a baseline",
            w6_colour(mean, read.weeks_live),
            "" if read.weeks_live >= W6_RED_WEEK else "slower is red only at week 8",
        )
    )
    for s in snapshots:
        if not s.metric_key.startswith("w7.v1."):
            continue
        agent = s.metric_key.removeprefix("w7.v1.")
        colour = w7_colour(s.value)
        note = "over 15%: red needs two consecutive months" if s.value > W7_AMBER else ""
        rows.append(
            Row(
                name,
                read.week_start,
                f"W7 override rate · {agent}",
                _pct(s.value),
                "1",
                colour,
                note,
            )
        )
    return rows


# --- dossiers, support hours, defects -------------------------------------------------------

_LEVEL = re.compile(r"^\|\s*Level\s*\|\s*([^|]+?)\s*\|", re.M)
_SIGNAL = re.compile(r"^.*\b(W2|W8)\b.*$", re.M)


def dossier_lines(code: str) -> tuple[str, list[str]]:
    """The dossier's level and any line naming W2 or W8, verbatim."""
    path = DOSSIERS / f"{code}.md"
    if not path.exists():
        return "no dossier", []
    text = path.read_text(encoding="utf-8")
    level = _LEVEL.search(text)
    return (level.group(1) if level else "not recorded"), [
        m.group(0).strip() for m in _SIGNAL.finditer(text)
    ]


@dataclass(frozen=True)
class SupportSprint:
    sprint: str
    hours: Decimal
    reserve_hours: Decimal
    sev: tuple[int, int, int]

    @property
    def over(self) -> bool:
        return self.hours > self.reserve_hours


def reserve_task_equivalents(sprint: str, backlog: Path = BACKLOG) -> Decimal:
    """The sprint's support-reserve rows (Q-04 "S<n> support reserve ..."), summed."""
    with backlog.open(encoding="utf-8") as f:
        return sum(
            (
                Decimal(r["size_tasks"])
                for r in csv.DictReader(f)
                if r["sprint"] == sprint and r["title"].startswith(f"S{sprint} support reserve")
            ),
            Decimal(0),
        )


def support(
    sprints: Sequence[str], hours_per_task: Decimal, log: Path = SUPPORT_LOG
) -> list[SupportSprint]:
    rows: list[dict[str, str]] = []
    if log.exists():
        with log.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if tuple(reader.fieldnames or ()) != SUPPORT_COLUMNS:
                raise ValueError(f"{log}: columns must be {','.join(SUPPORT_COLUMNS)}")
            rows = list(reader)
    out: list[SupportSprint] = []
    for sprint in sprints:
        mine = [r for r in rows if r["sprint"] == sprint]
        out.append(
            SupportSprint(
                sprint,
                sum((Decimal(r["hours"]) for r in mine), Decimal(0)),
                reserve_task_equivalents(sprint) * hours_per_task,
                (
                    sum(int(r["sev1"]) for r in mine),
                    sum(int(r["sev2"]) for r in mine),
                    sum(int(r["sev3"]) for r in mine),
                ),
            )
        )
    return out


def rk07(sprints: Sequence[SupportSprint]) -> bool:
    """RK-07: support hours over the reserve two sprints running."""
    return any(a.over and b.over for a, b in pairwise(sprints))


def defects_found(first: date, last: date, path: Path = DEFECTS) -> list[tuple[str, str, str]]:
    """(id, severity, state) of escaped defects found between the first and last week read."""
    out: list[tuple[str, str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 10 or not re.fullmatch(r"ED-\d+", cells[0]):
            continue
        try:
            found = date.fromisoformat(cells[1])
        except ValueError:
            continue
        if first <= found <= last:
            out.append((cells[0], cells[7], cells[9].split(" ")[0]))
    return out


# --- the pack -------------------------------------------------------------------------------


async def build(
    firms: Sequence[UUID],
    codes: Sequence[str],
    weeks: Sequence[date],
    sprints: Sequence[str],
    hours_per_task: Decimal,
) -> str:
    lines = [
        "# M12 ops evidence pack (Q-04-T054)",
        "",
        "Read from code by `make m12-pack`; reproduce with the same inputs. Inputs:",
        "",
        f"- weeks read: {', '.join(w.isoformat() for w in weeks)}; sprints: {', '.join(sprints)};"
        f" hours per task-equivalent: {hours_per_task}",
        f"- support log `docs/ops/pilot/support-hours.csv` sha256 {sha256(SUPPORT_LOG)}",
        f"- escaped-defect log `docs/quality/escaped-defects.md` sha256 {sha256(DEFECTS)}",
        f"- backlog `docs/plan/backlog.csv` sha256 {sha256(BACKLOG)}",
        "",
        "## W4 and W5 (chapter 11 §11.6.2, Q-04-T050's read)",
        "",
    ]
    extra: list[Row] = []
    for week in weeks:
        reads = [await wedge_read(firm, week) for firm in firms]
        lines.append(wedge_report(cross_firm(reads)))
        for read, firm in zip(reads, firms, strict=True):
            extra.extend(w6_w7_rows(read, await week_snapshots(firm, week)))
    lines += [
        "## W6 and W7",
        "",
        "| Firm | Week | Signal | Value | Counts | Colour | Note |",
        "|---|---|---|---|---|---|---|",
        *(
            f"| {r.firm} | {r.week.isoformat()} | {r.signal} | {r.value} | {r.counts} | "
            f"{r.colour} | {r.note} |"
            for r in extra
        ),
        "",
        "## W2 and W8 (as recorded in each go-live dossier)",
        "",
        "| Pilot code | Dossier level | W2 / W8 lines recorded |",
        "|---|---|---|",
    ]
    for code in codes:
        level, recorded = dossier_lines(code)
        lines.append(f"| {code} | {level} | {'; '.join(recorded) or 'none recorded'} |")
    found = support(sprints, hours_per_task)
    lines += [
        "",
        "## Support hours against the reserve, and SEVs",
        "",
        "| Sprint | Hours logged | Reserve hours | Over | SEV1 | SEV2 | SEV3 |",
        "|---|---|---|---|---|---|---|",
        *(
            f"| S{s.sprint} | {s.hours} | {s.reserve_hours} | {'yes' if s.over else 'no'} | "
            f"{s.sev[0]} | {s.sev[1]} | {s.sev[2]} |"
            for s in found
        ),
        "",
        "RK-07 (two sprints running over the reserve): "
        + ("fires." if rk07(found) else "does not fire."),
    ]
    if weeks:
        first, last = min(weeks), max(weeks) + timedelta(days=6)
        defects = defects_found(first, last)
        lines += [
            "",
            f"## Escaped defects found {first.isoformat()} to {last.isoformat()}",
            "",
            "| ID | Severity | State |",
            "|---|---|---|",
            *(f"| {i} | {sev} | {state} |" for i, sev, state in defects),
            *(["| none | | |"] if not defects else []),
        ]
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the M12 ops evidence pack.")
    parser.add_argument("--firm", type=UUID, action="append", required=True)
    parser.add_argument("--code", action="append", default=[], help="pilot code per firm (PF-X1)")
    parser.add_argument("--week", type=date.fromisoformat, action="append", required=True)
    parser.add_argument("--sprint", action="append", required=True)
    parser.add_argument("--hours-per-task", type=Decimal, default=Decimal(6))
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    text = asyncio.run(build(args.firm, args.code, args.week, args.sprint, args.hours_per_task))
    if args.out is None:
        print(text, end="")
    else:
        args.out.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
