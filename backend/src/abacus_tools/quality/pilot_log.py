"""The Pilot 0 usability log and its top ten (Q-03-T084; F-09 §3.7 G3; Q-04's pilot model).

    python -m abacus_tools.quality.pilot_log            # the log is well formed (check-fast)
    python -m abacus_tools.quality.pilot_log --exit     # PW0 exit: every top-10 row is resolved

F-09 files each Pilot 0 finding as an issue (screen ID, state letter, severity, owning epic)
within two business days; the ten that matter most are the rows of
`docs/ops/pilot/pilot-0-usability-log.md`.
Q-03-T084 fixes the defects among them before M9 (Tue Jun 1, 2027); anything that is a new
capability goes to its owning epic's cut list instead. This check keeps the log honest:

- every row names its issue (`#n`), a pilot code (never a firm name: PF-A1, PF-T1, ...), a screen
  the plan knows, a state letter, a usability severity (S1-S3, the session logs' scale), an epic
  that exists, a kind
  (`defect` or `capability`) and a status (`open`, `closed`, `re-filed`);
- a `closed` row names the fix (`#n`, the PR); a `re-filed` row names the owning epic's issue;
- a `capability` row is never `closed` by a fix here: it is `re-filed` to the cut list;
- at most ten rows.

`--exit` adds the acceptance: the log holds its top ten and none is still `open`. An empty log
passes the shape check and fails the exit check, so the acceptance can't pass vacuously.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[3].parent
LOG: Final = ROOT / "docs" / "ops" / "pilot" / "pilot-0-usability-log.md"
EPICS_DIR: Final = ROOT / "docs" / "plan" / "epics"
BACKLOG: Final = ROOT / "docs" / "plan" / "backlog.csv"
TOP: Final = 10
COLUMNS: Final = (
    "#",
    "Issue",
    "Pilot",
    "Screen",
    "State",
    "Severity",
    "Owning epic",
    "Kind",
    "Status",
    "Resolution",
)
_ISSUE: Final = re.compile(r"#\d+")
_PILOT: Final = re.compile(r"PF-[ATC]\d{1,2}")
_STATE: Final = re.compile(r"[a-z]\d?|—")
# The usability severities the session logs use (P-08-T29): S1 blocks the task, S2 slows it or
# causes a recovered error, S3 is cosmetic or wording. Not ADR-097's incident SEV levels.
_SEVERITY: Final = frozenset({"S1", "S2", "S3"})
_KINDS: Final = frozenset({"defect", "capability"})
_STATUSES: Final = frozenset({"open", "closed", "re-filed"})


@dataclass(frozen=True)
class Row:
    line: int
    cells: dict[str, str]


def rows(text: str) -> tuple[list[Row], list[str]]:
    """The log table's rows, and any problem with the table itself."""
    problems: list[str] = []
    header: list[str] | None = None
    found: list[Row] = []
    for n, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            if header is not None and found:
                break  # the table ended
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if header is None:
            if cells[:2] == ["#", "Issue"]:
                header = cells
                if tuple(cells) != COLUMNS:
                    problems.append(f"line {n}: the columns must be {' | '.join(COLUMNS)}")
            continue
        if all(set(c) <= {"-", ":"} for c in cells):
            continue  # the separator
        found.append(Row(n, dict(zip(COLUMNS, cells, strict=False))))
    if header is None:
        problems.append("the log has no table with the columns " + " | ".join(COLUMNS))
    return found, problems


def known_epics(directory: Path = EPICS_DIR) -> frozenset[str]:
    return frozenset(
        p.stem for p in directory.glob("*.md") if re.fullmatch(r"[A-Z]-\d{2}", p.stem)
    )


def known_screens(backlog: Path = BACKLOG) -> frozenset[str]:
    screens: set[str] = set()
    with backlog.open(encoding="utf-8", newline="") as handle:
        for record in csv.DictReader(handle):
            for item in (record.get("screens") or "").split(";"):
                name = item.split(":")[-1].strip()
                if re.fullmatch(r"[A-Z]{2,4}-\d{2}", name):
                    screens.add(name)
    return frozenset(screens)


def check_row(row: Row, epics: frozenset[str], screens: frozenset[str]) -> list[str]:
    c = row.cells
    where = f"line {row.line}"
    problems: list[str] = []
    if not _ISSUE.fullmatch(c.get("Issue", "")):
        problems.append(f"{where}: Issue must be an issue reference (#n)")
    if not _PILOT.fullmatch(c.get("Pilot", "")):
        problems.append(f"{where}: Pilot must be a pilot code (PF-A1, PF-T1, ...), never a name")
    if c.get("Screen", "") not in screens:
        problems.append(f"{where}: Screen {c.get('Screen', '')!r} is not a screen the plan names")
    if not _STATE.fullmatch(c.get("State", "")):
        problems.append(f"{where}: State must be the artboard letter (a, a2, ...) or —")
    if c.get("Severity", "") not in _SEVERITY:
        problems.append(f"{where}: Severity must be S1, S2 or S3 (the session logs' scale)")
    if c.get("Owning epic", "") not in epics:
        problems.append(f"{where}: Owning epic {c.get('Owning epic', '')!r} does not exist")
    kind, status = c.get("Kind", ""), c.get("Status", "")
    if kind not in _KINDS:
        problems.append(f"{where}: Kind must be defect or capability")
    if status not in _STATUSES:
        problems.append(f"{where}: Status must be open, closed or re-filed")
    resolution = c.get("Resolution", "")
    if status in ("closed", "re-filed") and not _ISSUE.search(resolution):
        problems.append(f"{where}: a {status} row names its fix PR or cut-list issue (#n)")
    if kind == "capability" and status == "closed":
        problems.append(
            f"{where}: a capability is re-filed to its epic's cut list, not closed here"
        )
    return problems


def check(
    text: str, epics: frozenset[str], screens: frozenset[str], *, exit_review: bool
) -> list[str]:
    found, problems = rows(text)
    for row in found:
        problems.extend(check_row(row, epics, screens))
    if len(found) > TOP:
        problems.append(f"the log holds the top {TOP}; it has {len(found)} rows")
    if exit_review:
        if len(found) < TOP:
            problems.append(f"PW0 exit needs the top {TOP} recorded; the log has {len(found)}")
        problems.extend(
            f"line {r.line}: {r.cells.get('Issue', '?')} is still open at the PW0 exit"
            for r in found
            if r.cells.get("Status") == "open"
        )
    return problems


def _print(problems: Iterable[str]) -> int:
    listed = list(problems)
    for problem in listed:
        print(f"pilot log: {problem}")
    return 1 if listed else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="abacus_tools.quality.pilot_log", description=__doc__)
    parser.add_argument("--exit", action="store_true", help="the PW0 exit review (Q-03-T084)")
    parser.add_argument("--log", type=Path, default=LOG)
    args = parser.parse_args(argv)
    if not args.log.exists():
        return _print([f"{args.log} is missing"])
    text = args.log.read_text(encoding="utf-8")
    return _print(check(text, known_epics(), known_screens(), exit_review=args.exit))


if __name__ == "__main__":
    sys.exit(main())
