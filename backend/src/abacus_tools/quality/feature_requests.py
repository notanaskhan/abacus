"""Every partner feature request has a written answer (F-09-T128; DEC-19's D1-D10 and X-01-X-08).

    python -m abacus_tools.quality.feature_requests

The log `docs/ops/pilot/feature-requests.md` holds one row per request: `| # | Received | Pilot |
Request | Verdict | Names | Answered on | Answer (vault) |`. A row is refused when its pilot is not
a pilot code, its verdict is not `epic`, `deferred` or `excluded`, or what it names does not fit
the verdict: an `epic` row names an epic that exists, a `deferred` row an epic's cut list (`<epic>
cut list`) or `D10`, an `excluded` row an exclusion (`X-01` to `X-08`) or a scope rule (`D4`, `D6`,
`D7`, `D8`). Each row needs its answered-on date and a vault reference: the acceptance is a written
answer for every request.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[3].parent
LOG: Final = ROOT / "docs" / "ops" / "pilot" / "feature-requests.md"
EPICS_DIR: Final = ROOT / "docs" / "plan" / "epics"
COLUMNS: Final = (
    "#",
    "Received",
    "Pilot",
    "Request",
    "Verdict",
    "Names",
    "Answered on",
    "Answer (vault)",
)
_PILOT: Final = re.compile(r"PF-[ATCX]\d{1,2}|PC\d{2}-\d{2}")
_DATE: Final = re.compile(r"\d{4}-\d{2}-\d{2}")
_VAULT: Final = re.compile(r"V-\d+")
_EXCLUSIONS: Final = frozenset({f"X-0{n}" for n in range(1, 9)} | {"D4", "D6", "D7", "D8"})


def known_epics(directory: Path = EPICS_DIR) -> frozenset[str]:
    return frozenset(
        p.stem for p in directory.glob("*.md") if re.fullmatch(r"[A-Z]-\d{2}", p.stem)
    )


def rows(text: str) -> tuple[list[tuple[int, dict[str, str]]], list[str]]:
    found: list[tuple[int, dict[str, str]]] = []
    problems: list[str] = []
    header_seen = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if cells[:2] == ["#", "Received"]:
            header_seen = True
            if tuple(cells) != COLUMNS:
                problems.append(f"line {number}: the columns must be {' | '.join(COLUMNS)}")
            continue
        if not header_seen or all(set(c) <= {"-", ":"} for c in cells):
            continue
        found.append((number, dict(zip(COLUMNS, cells, strict=False))))
    if not header_seen:
        problems.append("the log has no table with the columns " + " | ".join(COLUMNS))
    return found, problems


def check_row(number: int, row: dict[str, str], epics: frozenset[str]) -> list[str]:
    where = f"line {number}"
    problems: list[str] = []
    if not _PILOT.fullmatch(row.get("Pilot", "")):
        problems.append(f"{where}: Pilot must be a pilot code (PF-A1, PC28-07), never a name")
    verdict, names = row.get("Verdict", ""), row.get("Names", "")
    if verdict == "epic":
        if names.split()[0:1] and names.split()[0] not in epics:
            problems.append(f"{where}: an epic verdict names an epic that exists, not {names!r}")
        elif not names:
            problems.append(f"{where}: an epic verdict names its epic")
    elif verdict == "deferred":
        cut = re.fullmatch(r"([A-Z]-\d{2}) cut list", names)
        if not (names == "D10" or (cut is not None and cut.group(1) in epics)):
            problems.append(f"{where}: a deferral names '<epic> cut list' or D10")
    elif verdict == "excluded":
        if names not in _EXCLUSIONS:
            problems.append(f"{where}: an exclusion names X-01 to X-08 or D4, D6, D7, D8")
    else:
        problems.append(f"{where}: Verdict must be epic, deferred or excluded")
    if not _DATE.fullmatch(row.get("Answered on", "")):
        problems.append(f"{where}: every request is answered in writing (Answered on, YYYY-MM-DD)")
    if not _VAULT.fullmatch(row.get("Answer (vault)", "")):
        problems.append(f"{where}: the written answer's vault reference (V-123)")
    return problems


def check(text: str, epics: frozenset[str]) -> list[str]:
    found, problems = rows(text)
    for number, row in found:
        problems.extend(check_row(number, row, epics))
    return problems


def main() -> int:
    problems = (
        check(LOG.read_text(encoding="utf-8"), known_epics())
        if LOG.exists()
        else [f"{LOG} is missing"]
    )
    for problem in problems:
        print(f"feature requests: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
