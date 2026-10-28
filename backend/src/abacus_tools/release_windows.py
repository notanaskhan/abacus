"""Release windows as code (Q-04-T002; ADR P-29, DEC-68; docs/ops/release-windows.md).

`deploy/windows.yaml` says which firm is in which window on which date. The release gate
(Q-04-T003), the flag and entitlement CLIs (T004), the flag registry check (T005), the flip
ops-request check (T010) and the go-live check (T009) all read it through this module, so they
agree without anyone remembering dates.

    python -m abacus_tools.release_windows check [--file deploy/windows.yaml]
    python -m abacus_tools.release_windows calendar [--year 2027]        # make windows [YEAR=]
    python -m abacus_tools.release_windows in-window --firm PF-A1 --at 2027-09-01T00:00:00-05:00
    python -m abacus_tools.release_windows slot --at 2027-09-21T19:00:00-05:00

The rules (P-29; Q-04 §4.9):

- A window applies to a firm from its `real_data_since`: season windows (Jan 1 - Apr 20) to every
  live firm, autumn windows (Sep 1 - Oct 20) to firms live on tax or EBP work. With no live firm,
  every guard is inert (DEC-68).
- Platform rules (promotion, migrations, deadline weeks) apply when **any** live firm is in a
  window; flip rules apply per firm (OQ-2).
- A deadline is shifted past weekends and legal holidays (IRC §7503; DC Emancipation Day moves
  Apr 15). A deadline week is the Monday-Friday week containing the shifted deadline. A mini-freeze
  (autumn only) runs from the shifted extension deadline minus 7 days through it, 8 days inclusive.
- Inside a window, the flip slot is Tuesday 19:00-21:00 CT, except in a deadline week or a
  mini-freeze ("no slot"). Migrations wait until 20:00 CT.

The file's mini-freezes and deadline weeks are checked against the rule, so a typo fails
`make check-fast` rather than moving a freeze.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from itertools import pairwise
from pathlib import Path
from typing import Final, Literal, cast
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import yaml

BACKEND = Path(__file__).resolve().parents[2]
REPO = BACKEND.parent
WINDOWS_FILE: Final = REPO / "deploy" / "windows.yaml"
CT: Final = ZoneInfo("America/Chicago")

# A pilot code (PF-A1, PF-T1, PF-C1) or a cohort code (PC28-07): never a firm's name (DEC-806).
CODE: Final = re.compile(r"PF-[A-Z][0-9]{1,3}|PC[0-9]{2}-[0-9]{2,3}")
_WINDOW_ID: Final = re.compile(r"(season|autumn)-(20[0-9]{2})")
_HHMM: Final = re.compile(r"([01][0-9]|2[0-3]):[0-5][0-9]")
DASH: Final = "\u2013"  # the calendar's en dash
_WEEKDAYS: Final = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
RULES_VERSION: Final = 1

Kind = Literal["season", "autumn"]


class WindowsError(ValueError):
    """`deploy/windows.yaml` broke a rule; `problems` names each entry."""

    def __init__(self, problems: Sequence[str]) -> None:
        super().__init__("; ".join(problems))
        self.problems = list(problems)


# --- the calendar --------------------------------------------------------------------------------


@dataclass(frozen=True, order=True)
class Span:
    """Inclusive calendar dates in Central time."""

    start: date
    end: date

    def __contains__(self, day: object) -> bool:
        return isinstance(day, date) and self.start <= day <= self.end

    def label(self) -> str:
        """`Sep 8-15`, `Sep 25 - Oct 2` (the calendar's style)."""
        if self.start.month == self.end.month:
            return f"{_md(self.start)}{DASH}{self.end.day}"
        return f"{_md(self.start)} {DASH} {_md(self.end)}"


@dataclass(frozen=True)
class Firm:
    tenant_id: UUID
    code: str
    real_data_since: date | None
    autumn_window: bool

    def live_on(self, day: date) -> bool:
        return self.real_data_since is not None and self.real_data_since <= day


@dataclass(frozen=True)
class Window:
    id: str
    kind: Kind
    span: Span
    mini_freezes: tuple[Span, ...]
    deadline_weeks: tuple[Span, ...]

    def applies_to(self, firm: Firm, day: date) -> bool:
        return (
            day in self.span
            and firm.live_on(day)
            and (self.kind == "season" or firm.autumn_window)
        )


@dataclass(frozen=True)
class Slot:
    weekday: int  # Monday is 0
    start: time
    end: time
    tz: ZoneInfo


@dataclass(frozen=True)
class Calendar:
    rules_version: int
    firms: tuple[Firm, ...]
    windows: tuple[Window, ...]
    flip_slot: Slot
    migrate_not_before: time
    migrate_tz: ZoneInfo

    def firm(self, who: str | UUID) -> Firm | None:
        """By pilot code or tenant id."""
        for firm in self.firms:
            if who in (firm.code, firm.tenant_id, str(firm.tenant_id)):
                return firm
        return None


# --- the P-29 rule (IRC §7503) -------------------------------------------------------------------


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    after = date(year + (month == 12), month % 12 + 1, 1)
    last = after - timedelta(days=1)
    return last - timedelta(days=(last.weekday() - weekday) % 7)


def _observed(day: date) -> date:
    """A fixed-date federal holiday on a Saturday is observed Friday; on a Sunday, Monday."""
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def legal_holidays(year: int) -> frozenset[date]:
    """The legal holidays in the District of Columbia that shift a federal deadline (IRC §7503,
    5 U.S.C. §6103, DC Code §1-612.02): the federal holidays and DC Emancipation Day (Apr 16), each
    as observed."""
    return frozenset(
        {
            _observed(date(year, 1, 1)),
            _nth_weekday(year, 1, 0, 3),  # Martin Luther King Jr. Day
            _nth_weekday(year, 2, 0, 3),  # Washington's Birthday
            _observed(date(year, 4, 16)),  # DC Emancipation Day
            _last_weekday(year, 5, 0),  # Memorial Day
            _observed(date(year, 6, 19)),
            _observed(date(year, 7, 4)),
            _nth_weekday(year, 9, 0, 1),  # Labor Day
            _nth_weekday(year, 10, 0, 2),  # Columbus Day
            _observed(date(year, 11, 11)),
            _nth_weekday(year, 11, 3, 4),  # Thanksgiving
            _observed(date(year, 12, 25)),
        }
    )


def shifted(deadline: date) -> date:
    """The next day that is neither a weekend nor a legal holiday (IRC §7503)."""
    day = deadline
    while day.weekday() >= 5 or day in legal_holidays(day.year):
        day += timedelta(days=1)
    return day


def week_of(day: date) -> Span:
    """The Monday-Friday week containing `day`."""
    monday = day - timedelta(days=day.weekday())
    return Span(monday, monday + timedelta(days=4))


# The deadlines each window kind freezes around (P-29; Q-04 §4.9): Mar 15 and Apr 15 in season;
# the extension deadlines Sep 15, Sep 30 and Oct 15 in autumn.
DEADLINES: Final[Mapping[Kind, tuple[tuple[int, int], ...]]] = {
    "season": ((3, 15), (4, 15)),
    "autumn": ((9, 15), (9, 30), (10, 15)),
}
SPANS: Final[Mapping[Kind, tuple[tuple[int, int], tuple[int, int]]]] = {
    "season": ((1, 1), (4, 20)),
    "autumn": ((9, 1), (10, 20)),
}


def expected(kind: Kind, year: int) -> Window:
    """The window the rule gives for `kind` in `year`."""
    (sm, sd), (em, ed) = SPANS[kind]
    deadlines = [shifted(date(year, m, d)) for m, d in DEADLINES[kind]]
    minis = tuple(Span(d - timedelta(days=7), d) for d in deadlines) if kind == "autumn" else ()
    return Window(
        id=f"{kind}-{year}",
        kind=kind,
        span=Span(date(year, sm, sd), date(year, em, ed)),
        mini_freezes=minis,
        deadline_weeks=tuple(week_of(d) for d in deadlines),
    )


# --- loading and validation ----------------------------------------------------------------------


def _date(value: object) -> date | None:
    if isinstance(value, datetime):
        return None
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    return None


def _spans(value: object, where: str, problems: list[str]) -> tuple[Span, ...]:
    if not isinstance(value, list):
        problems.append(f"{where}: a list of [start, end] date pairs")
        return ()
    spans: list[Span] = []
    for i, pair in enumerate(cast(list[object], value)):
        dates = [_date(d) for d in cast(list[object], pair)] if isinstance(pair, list) else []
        if len(dates) != 2 or dates[0] is None or dates[1] is None:
            problems.append(f"{where}[{i}]: undated; needs both dates as YYYY-MM-DD")
            continue
        start, end = dates[0], dates[1]
        if end < start:
            problems.append(f"{where}[{i}]: ends {end} before it starts {start}")
            continue
        spans.append(Span(start, end))
    return tuple(spans)


def _clock(value: object, where: str, problems: list[str]) -> time | None:
    if not isinstance(value, str) or not _HHMM.fullmatch(value):
        problems.append(f"{where}: a 24-hour HH:MM time")
        return None
    return time.fromisoformat(value)


def _zone(value: object, where: str, problems: list[str]) -> ZoneInfo:
    try:
        return ZoneInfo(str(value))
    except (ZoneInfoNotFoundError, ValueError):
        problems.append(f"{where}: an IANA time zone")
        return CT


def _firms(raw: object, problems: list[str]) -> tuple[Firm, ...]:
    if not isinstance(raw, list):
        problems.append("firms: a list (empty until the first real go-live)")
        return ()
    firms: list[Firm] = []
    seen_codes: set[str] = set()
    seen_ids: set[UUID] = set()
    for i, entry in enumerate(cast(list[object], raw)):
        where = f"firms[{i}]"
        if not isinstance(entry, dict):
            problems.append(f"{where}: a mapping")
            continue
        item = cast(dict[str, object], entry)
        unknown = set(item) - {"tenant_id", "code", "real_data_since", "autumn_window"}
        if unknown:
            problems.append(f"{where}: unknown keys {sorted(unknown)}")
        try:
            tenant = UUID(str(item.get("tenant_id")))
        except ValueError:
            problems.append(f"{where}: tenant_id is not a UUID")
            continue
        code = item.get("code")
        if code is None:
            problems.append(f"{where} ({tenant}): a tenant without a pilot code")
            continue
        if not isinstance(code, str) or not CODE.fullmatch(code):
            problems.append(
                f"{where}: code {code!r} is not a pilot code (PF-A1) or cohort code (PC28-07)"
            )
            continue
        if code in seen_codes or tenant in seen_ids:
            problems.append(f"{where} ({code}): listed twice")
            continue
        seen_codes.add(code)
        seen_ids.add(tenant)
        since_raw = item.get("real_data_since")
        since = None if since_raw is None else _date(since_raw)
        if since_raw is not None and since is None:
            problems.append(f"{where} ({code}): real_data_since is not a date")
            continue
        autumn = item.get("autumn_window", False)
        if not isinstance(autumn, bool):
            problems.append(f"{where} ({code}): autumn_window is true or false")
            continue
        firms.append(Firm(tenant, code, since, autumn))
    return tuple(firms)


def _windows(raw: object, problems: list[str]) -> tuple[Window, ...]:
    if not isinstance(raw, list):
        problems.append("windows: a list")
        return ()
    windows: list[Window] = []
    for i, entry in enumerate(cast(list[object], raw)):
        if not isinstance(entry, dict):
            problems.append(f"windows[{i}]: a mapping")
            continue
        item = cast(dict[str, object], entry)
        wid = str(item.get("id", ""))
        where = f"windows[{wid or i}]"
        match = _WINDOW_ID.fullmatch(wid)
        kind = item.get("kind")
        if match is None or kind != match.group(1):
            problems.append(f"{where}: id is <kind>-<year> and kind is season or autumn")
            continue
        start, end = _date(item.get("starts")), _date(item.get("ends"))
        if start is None or end is None or end < start:
            problems.append(f"{where}: undated; starts and ends are dates, in order")
            continue
        minis = _spans(item.get("mini_freezes", []), f"{where}.mini_freezes", problems)
        weeks = _spans(item.get("deadline_weeks"), f"{where}.deadline_weeks", problems)
        window = Window(wid, cast(Kind, kind), Span(start, end), minis, weeks)
        rule = expected(window.kind, int(match.group(2)))
        for name, got, want in (
            ("dates", (window.span,), (rule.span,)),
            ("mini_freezes", window.mini_freezes, rule.mini_freezes),
            ("deadline_weeks", window.deadline_weeks, rule.deadline_weeks),
        ):
            if tuple(sorted(got)) != want:
                shown = ", ".join(s.label() for s in want) or "none"
                problems.append(f"{where}.{name}: differ from the P-29 rule ({shown})")
        windows.append(window)
    ordered = sorted(windows, key=lambda w: w.span)
    for before, after in pairwise(ordered):
        if after.span.start <= before.span.end:
            problems.append(f"windows[{after.id}]: overlaps {before.id}")
    ids = [w.id for w in windows]
    for wid in sorted({w for w in ids if ids.count(w) > 1}):
        problems.append(f"windows[{wid}]: listed twice")
    return tuple(ordered)


def parse(raw: object) -> Calendar:
    """The calendar, or `WindowsError` naming every entry that breaks a rule (Q-04 AC-1.3)."""
    problems: list[str] = []
    if not isinstance(raw, dict):
        raise WindowsError(["deploy/windows.yaml: a mapping at the top level"])
    data = cast(dict[str, object], raw)
    unknown = set(data) - {"rules_version", "firms", "windows", "flip_slot", "migrate_not_before"}
    if unknown:
        problems.append(f"unknown keys {sorted(unknown)}")
    if data.get("rules_version") != RULES_VERSION:
        problems.append(f"rules_version: {RULES_VERSION}")
    firms = _firms(data.get("firms"), problems)
    windows = _windows(data.get("windows"), problems)
    slot_raw = data.get("flip_slot")
    slot = Slot(1, time(19), time(21), CT)
    if not isinstance(slot_raw, dict):
        problems.append("flip_slot: {weekday, start, end, tz}")
    else:
        s = cast(dict[str, object], slot_raw)
        weekday = str(s.get("weekday", ""))
        start = _clock(s.get("start"), "flip_slot.start", problems)
        end = _clock(s.get("end"), "flip_slot.end", problems)
        tz = _zone(s.get("tz"), "flip_slot.tz", problems)
        if weekday not in _WEEKDAYS:
            problems.append("flip_slot.weekday: a weekday name")
        elif start is not None and end is not None:
            if end <= start:
                problems.append("flip_slot: ends before it starts")
            slot = Slot(_WEEKDAYS.index(weekday), start, end, tz)
    migrate_raw = data.get("migrate_not_before")
    migrate, migrate_tz = time(20), CT
    if not isinstance(migrate_raw, dict):
        problems.append("migrate_not_before: {time, tz}")
    else:
        m = cast(dict[str, object], migrate_raw)
        migrate = _clock(m.get("time"), "migrate_not_before.time", problems) or migrate
        migrate_tz = _zone(m.get("tz"), "migrate_not_before.tz", problems)
    if problems:
        raise WindowsError(problems)
    return Calendar(RULES_VERSION, firms, windows, slot, migrate, migrate_tz)


def load(path: Path = WINDOWS_FILE) -> Calendar:
    try:
        raw: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise WindowsError([f"{path.name}: unreadable ({type(error).__name__})"]) from None
    return parse(raw)


# --- the questions guards ask --------------------------------------------------------------------


def local_day(at: datetime, tz: ZoneInfo = CT) -> date:
    """The calendar date in Central time; a naive datetime is refused, never guessed."""
    if at.tzinfo is None:
        raise ValueError("a release-window instant needs a time zone")
    return at.astimezone(tz).date()


def in_window(cal: Calendar, firm: str | UUID, at: datetime) -> str | None:
    """The window `firm` is in at `at` (Q-04 AC-1.1), or None: not listed, not live yet, or outside
    every window that applies to it."""
    day = local_day(at)
    found = cal.firm(firm)
    if found is None:
        return None
    return next((w.id for w in cal.windows if w.applies_to(found, day)), None)


def platform_window(cal: Calendar, at: datetime) -> str | None:
    """The window production is in at `at`: any live firm's (promotion, migrations and deadline
    weeks follow the strictest live firm, P-29). None while no firm is live (DEC-68)."""
    day = local_day(at)
    for window in cal.windows:
        if any(window.applies_to(firm, day) for firm in cal.firms):
            return window.id
    return None


def _window(cal: Calendar, wid: str | None) -> Window | None:
    return next((w for w in cal.windows if w.id == wid), None)


def deadline_week(cal: Calendar, at: datetime, firm: str | UUID | None = None) -> Span | None:
    """The deadline week `at` falls in, inside the window that applies: `firm`'s, or production's
    when no firm is named. None outside, or while no firm is live."""
    wid = in_window(cal, firm, at) if firm is not None else platform_window(cal, at)
    window = _window(cal, wid)
    day = local_day(at)
    return None if window is None else next((s for s in window.deadline_weeks if day in s), None)


def mini_freeze(cal: Calendar, at: datetime, firm: str | UUID | None = None) -> Span | None:
    """The mini-freeze `at` falls in, by the same rule as `deadline_week`."""
    wid = in_window(cal, firm, at) if firm is not None else platform_window(cal, at)
    window = _window(cal, wid)
    day = local_day(at)
    return None if window is None else next((s for s in window.mini_freezes if day in s), None)


def in_slot(cal: Calendar, at: datetime) -> bool:
    """Whether `at` is inside the weekly slot (Tuesday 19:00-21:00 CT), by the clock alone."""
    if at.tzinfo is None:
        raise ValueError("a release-window instant needs a time zone")
    here = at.astimezone(cal.flip_slot.tz)
    s = cal.flip_slot
    return here.weekday() == s.weekday and s.start <= here.time() < s.end


def flip_slot(cal: Calendar, at: datetime, firm: str | UUID | None = None) -> bool:
    """Whether a change may happen at `at` inside a window: in the slot, and not in a deadline week
    or a mini-freeze (Q-04 AC-4.2: Tue Sep 14, 2027 has no slot). For `firm`, its own window; for
    production, the platform window. Outside a window there is no slot rule: True."""
    wid = in_window(cal, firm, at) if firm is not None else platform_window(cal, at)
    if wid is None:
        return True
    return (
        in_slot(cal, at)
        and deadline_week(cal, at, firm) is None
        and mini_freeze(cal, at, firm) is None
    )


def migrate_not_before(cal: Calendar, at: datetime) -> datetime:
    """When the pipeline's migrate step may run: at once outside a window; inside one, not before
    20:00 CT that day (P-29 rule 2; Q-04 AC-2.5)."""
    if platform_window(cal, at) is None:
        return at
    local = at.astimezone(cal.migrate_tz)
    earliest = datetime.combine(local.date(), cal.migrate_not_before, cal.migrate_tz)
    return max(local, earliest)


def slots(cal: Calendar, window: Window) -> list[date]:
    """The window's slot days: each slot weekday inside it that is in no deadline week or
    mini-freeze."""
    day = window.span.start + timedelta(
        days=(cal.flip_slot.weekday - window.span.start.weekday()) % 7
    )
    out: list[date] = []
    while day <= window.span.end:
        if not any(day in s for s in (*window.deadline_weeks, *window.mini_freezes)):
            out.append(day)
        day += timedelta(days=7)
    return out


# --- the calendar print --------------------------------------------------------------------------


def _md(day: date) -> str:
    return f"{day.strftime('%b')} {day.day}"


def _dated(day: date) -> str:
    return f"{day.strftime('%a %b')} {day.day}, {day.year}"


def calendar_lines(cal: Calendar, year: int | None = None) -> list[str]:
    """`make windows [YEAR=]`: each window with its mini-freezes, deadline weeks, slots and the
    firms it applies to (Q-04 AC-1.4)."""
    lines: list[str] = []
    for window in cal.windows:
        if year is not None and window.span.start.year != year:
            continue
        applies = "every live firm" if window.kind == "season" else "firms live on tax or EBP work"
        firms = [
            f.code
            for f in cal.firms
            if f.real_data_since is not None
            and f.real_data_since <= window.span.end
            and (window.kind == "season" or f.autumn_window)
        ]
        lines += [
            f"{window.id}  {_dated(window.span.start)} {DASH} {_dated(window.span.end)}"
            f"  ({applies})",
            "  mini-freezes:   " + (", ".join(s.label() for s in window.mini_freezes) or "\u2014"),
            "  deadline weeks: " + ", ".join(s.label() for s in window.deadline_weeks),
            "  Tuesday slots:  " + ", ".join(_md(d) for d in slots(cal, window)),
            "  firms:          " + (", ".join(firms) or "none live yet (guards inert)"),
        ]
    return lines


def _instant(text: str) -> datetime:
    at = datetime.fromisoformat(text)
    if at.tzinfo is None:
        raise argparse.ArgumentTypeError("an ISO 8601 instant with an offset")
    return at


def main(argv: Iterable[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m abacus_tools.release_windows")
    parser.add_argument("--file", type=Path, default=WINDOWS_FILE)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check")
    showing = sub.add_parser("calendar")
    showing.add_argument("--year", type=int, default=None)
    asking = sub.add_parser("in-window")
    asking.add_argument("--firm", required=True)
    asking.add_argument("--at", type=_instant, required=True)
    slotting = sub.add_parser("slot")
    slotting.add_argument("--at", type=_instant, required=True)
    slotting.add_argument("--firm", default=None)
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        cal = load(cast(Path, args.file))
    except WindowsError as error:
        for problem in error.problems:
            print(f"windows.yaml: {problem}", file=sys.stderr)
        return 1
    if args.command == "check":
        print(f"windows.yaml: {len(cal.windows)} windows, {len(cal.firms)} firms, valid")
    elif args.command == "calendar":
        print("\n".join(calendar_lines(cal, cast(int | None, args.year))))
    elif args.command == "in-window":
        print(in_window(cal, cast(str, args.firm), cast(datetime, args.at)) or "none")
    else:
        at = cast(datetime, args.at)
        ok = flip_slot(cal, at, cast(str | None, args.firm))
        print("slot" if ok else "no slot")
        return 0 if ok else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
