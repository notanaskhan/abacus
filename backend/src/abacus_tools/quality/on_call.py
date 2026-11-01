"""The on-call rota covers every live-window day (Q-04-T020; `docs/ops/on-call.md`).

    python -m abacus_tools.quality.on_call

Acceptance: every PW1 day has a named backup. The check reads the file's `Windows` and `Rota`
tables and refuses:
- a window day no rota row covers, or one covered twice;
- a row whose primary or backup is not a founder handle, or whose backup is its primary;
- a row outside its window, or a window that names a firm by anything but a pilot code;
- a phone number or an email address anywhere in the file (contacts live in the vault);
- a missing `updated:` date (`go_live` reads it for `operations.on_call_current`).
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[3].parent
ON_CALL: Final = ROOT / "docs" / "ops" / "on-call.md"
HANDLES: Final = frozenset({"N", "AY"})
_PILOT: Final = re.compile(r"PF-[ATCX]\d{1,2}|PC\d{2}-\d{2}")
_EMAIL: Final = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE: Final = re.compile(r"(?<![\d-])\+?\(?\d{3}\)?[\s.-]\d{3}[\s.-]\d{4}(?!\d)")
_UPDATED: Final = re.compile(r"^updated:\s*(\d{4}-\d{2}-\d{2})\s*$", re.MULTILINE)


@dataclass(frozen=True)
class Window:
    name: str
    starts: date
    ends: date
    firms: tuple[str, ...]


@dataclass(frozen=True)
class Shift:
    line: int
    window: str
    start: date
    end: date
    primary: str
    backup: str


def _table(text: str, heading: str) -> list[tuple[int, list[str]]]:
    """The rows (line number, cells) of the first table under `heading`."""
    rows: list[tuple[int, list[str]]] = []
    inside = False
    header_seen = False
    for number, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if line.startswith("## "):
            if inside:
                break
            inside = line == heading
            continue
        if not inside or not line.startswith("|"):
            if inside and header_seen and rows and not line:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if not header_seen:
            header_seen = True
            continue
        if all(set(c) <= {"-", ":"} for c in cells):
            continue
        rows.append((number, cells))
    return rows


def windows(text: str) -> tuple[list[Window], list[str]]:
    found: list[Window] = []
    problems: list[str] = []
    for number, cells in _table(text, "## Windows"):
        try:
            starts, ends = date.fromisoformat(cells[1]), date.fromisoformat(cells[2])
        except (IndexError, ValueError):
            problems.append(f"line {number}: a window needs ISO start and end dates")
            continue
        firms = tuple(
            f.strip() for f in (cells[3] if len(cells) > 3 else "").split(",") if f.strip()
        )
        bad = [f for f in firms if not _PILOT.fullmatch(f)]
        if bad:
            problems.append(f"line {number}: firms are pilot codes only, not {', '.join(bad)}")
        found.append(Window(cells[0], starts, ends, firms))
    return found, problems


def shifts(text: str) -> tuple[list[Shift], list[str]]:
    found: list[Shift] = []
    problems: list[str] = []
    for number, cells in _table(text, "## Rota"):
        try:
            start, end = date.fromisoformat(cells[1]), date.fromisoformat(cells[2])
        except (IndexError, ValueError):
            problems.append(f"line {number}: a rota row needs ISO From and To dates")
            continue
        primary, backup = cells[3], cells[4]
        if primary not in HANDLES or backup not in HANDLES:
            problems.append(f"line {number}: primary and backup are founder handles (N, AY)")
        elif primary == backup:
            problems.append(f"line {number}: the backup must not be the primary")
        if end < start:
            problems.append(f"line {number}: To is before From")
        found.append(Shift(number, cells[0], start, end, primary, backup))
    return found, problems


def _days(start: date, end: date) -> list[date]:
    return [start + timedelta(days=n) for n in range((end - start).days + 1)]


def check(text: str) -> list[str]:
    problems: list[str] = []
    if not _UPDATED.search(text):
        problems.append("the frontmatter needs `updated: YYYY-MM-DD`")
    for pattern, what in ((_EMAIL, "an email address"), (_PHONE, "a phone number")):
        if pattern.search(text):
            problems.append(f"the file holds {what}: contacts live in the vault")
    found_windows, window_problems = windows(text)
    found_shifts, shift_problems = shifts(text)
    problems += window_problems + shift_problems
    by_name = {w.name: w for w in found_windows}
    for shift in found_shifts:
        window = by_name.get(shift.window)
        if window is None:
            problems.append(
                f"line {shift.line}: window {shift.window!r} is not in the Windows table"
            )
        elif shift.start < window.starts or shift.end > window.ends:
            problems.append(f"line {shift.line}: the row runs outside {window.name}")
    for window in found_windows:
        covered = Counter(
            day for s in found_shifts if s.window == window.name for day in _days(s.start, s.end)
        )
        uncovered = [d for d in _days(window.starts, window.ends) if covered[d] == 0]
        doubled = sorted(d for d, n in covered.items() if n > 1)
        if uncovered:
            problems.append(
                f"{window.name}: {len(uncovered)} day(s) without a primary and backup, "
                f"first {uncovered[0].isoformat()}"
            )
        if doubled:
            problems.append(f"{window.name}: {doubled[0].isoformat()} is on two rota rows")
    return problems


def main() -> int:
    if not ON_CALL.exists():
        print("on-call: docs/ops/on-call.md is missing")
        return 1
    problems = check(ON_CALL.read_text(encoding="utf-8"))
    for problem in problems:
        print(f"on-call: {problem}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
