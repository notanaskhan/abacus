"""Validate the feature flag registry and generate `abacus.kernel._flags` (ADR-089; SPEC-011).

Run: python -m abacus_tools.codegen.feature_flags [--check | --calendar]

`--check` (in `make check-fast`) fails when the generated module is stale, the registry is
invalid (AC-6), or any flag has expired (AC-4, TASK-026 D1): an expired flag must be removed
from the registry and the code.

Q-04-T005 (SPEC-403 AC-10; P-29; RK-15): `--check` also fails a flag whose `expires` falls inside
any release window in `deploy/windows.yaml`, unless the entry carries `window_exception: {reason,
approved_by}` with `approved_by` not its owner (a registry-only renewal inside a window). An entry
may also name the `journeys` whose staging runs a flip of it needs (Q-04-T010). `--calendar`
(`make flag-calendar`) lists every flag with owner, expiry, the last release train before it,
window conflicts and a 21-day warning.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import cast

import yaml

from abacus.kernel.clock import system_now
from abacus_tools import release_windows

BACKEND = Path(__file__).resolve().parents[3]
SOURCE_DIR = BACKEND.parent / "docs" / "architecture" / "feature-flags"
TARGET = BACKEND / "src" / "abacus" / "kernel" / "_flags.py"
MAX_LIFETIME = timedelta(days=90)
# A founder override (DEC-137, F-03-T37) may extend one renewal to 180 days. The entry names the
# decision that allows it, so every longer lifetime is on the record.
OVERRIDE_LIFETIME = timedelta(days=180)
_OVERRIDE = re.compile(r"DEC-[0-9]{2,4}")
_NAME = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$")
# platform.entitlements.MODULES: a flag may not name one of these areas.
_ENTITLEMENT_MODULES = frozenset(
    {"attest", "internal_audit", "group_audit", "statements_studio", "office_addins", "insights"}
)
_FIELDS = {"name", "description", "owner", "created", "expires", "kind", "values", "default"} | {
    "override",  # DEC-137
    "window_exception",  # Q-04-T005: a renewal that must expire inside a window, both founders
    "journeys",  # Q-04-T010: the staging journeys a flip of this flag needs green within 24 h
}
_HANDLE = re.compile(r"[a-z][a-z0-9._-]{0,60}")
_JOURNEY = re.compile(r"[a-z0-9][a-z0-9-]{0,60}")
WARN_DAYS = 21
_HEADER = '''"""GENERATED from docs/architecture/feature-flags/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.feature_flags
"""

from abacus.kernel.flags import Flag

# fmt: off
'''


@dataclass(frozen=True)
class WindowException:
    reason: str
    approved_by: str


@dataclass(frozen=True)
class Entry:
    name: str
    owner: str
    expires: date
    kind: str
    values: tuple[str, ...]
    default: str
    window_exception: WindowException | None = None
    journeys: tuple[str, ...] = ()


class RegistryError(ValueError):
    pass


def _date(value: object, field: str, name: str) -> date:
    if isinstance(value, date):
        return value
    raise RegistryError(f"{name}: {field} must be a date (YYYY-MM-DD)")


def source(directory: Path | None = None) -> str:
    """Every module's flags (P-39; F-03-T07: one file per module), joined into one document."""
    folder = directory or SOURCE_DIR
    parts = ["flags:"]
    for path in sorted(folder.glob("*.yaml")):
        if path.name.startswith("_"):
            continue
        text = f"\n{path.read_text(encoding='utf-8')}"
        if "\nflags:\n" not in text:
            raise RegistryError(f"{path.name}: a module file holds one `flags:` list")
        parts.append(text.split("\nflags:\n", 1)[1].rstrip("\n"))
    return "\n".join(parts) + "\n"


def parse(source: str) -> list[Entry]:
    """Every flag, validated (AC-6)."""
    document = cast(dict[str, object], yaml.safe_load(source) or {})
    raw = cast(list[dict[str, object]], document.get("flags") or [])
    entries: list[Entry] = []
    for item in raw:
        name = str(item.get("name", ""))
        if not _NAME.fullmatch(name):
            raise RegistryError(f"{name!r}: a flag name is dotted lower-case words")
        # ADR-148 (F-03-T28): modules are entitlements (database rows), never flags.
        if name.startswith("ff.") or name.split(".", 1)[0] in _ENTITLEMENT_MODULES:
            raise RegistryError(f"{name}: a module is an entitlement, not a flag (ADR-148)")
        unknown = set(item) - _FIELDS
        if unknown:
            raise RegistryError(f"{name}: unknown fields {sorted(unknown)}")
        for field in ("description", "owner"):
            if not str(item.get(field) or "").strip():
                raise RegistryError(f"{name}: {field} is required")
        created = _date(item.get("created"), "created", name)
        expires = _date(item.get("expires"), "expires", name)
        override = item.get("override")
        if override is not None and not _OVERRIDE.fullmatch(str(override)):
            raise RegistryError(f"{name}: an override names its decision (DEC-nnn)")
        lifetime = OVERRIDE_LIFETIME if override is not None else MAX_LIFETIME
        if not created < expires <= created + lifetime:
            raise RegistryError(
                f"{name}: expires must be after created and within {lifetime.days} days"
                + ("" if override is not None else " (or name a founder override, DEC-nnn)")
            )
        kind = str(item.get("kind"))
        default = (
            str(item.get("default")).lower() if kind == "boolean" else str(item.get("default"))
        )
        if kind == "boolean":
            values: tuple[str, ...] = ()
            if "values" in item or default not in ("true", "false"):
                raise RegistryError(f"{name}: a boolean flag has a true/false default, no values")
        elif kind == "variant":
            values = tuple(str(v) for v in cast(list[object], item.get("values") or []))
            if not values or len(set(values)) != len(values) or default not in values:
                raise RegistryError(
                    f"{name}: a variant lists distinct values including its default"
                )
        else:
            raise RegistryError(f"{name}: kind is boolean or variant")
        owner = str(item["owner"])
        exception = _window_exception(item.get("window_exception"), name, owner)
        journeys = _journeys(item.get("journeys"), name)
        entries.append(Entry(name, owner, expires, kind, values, default, exception, journeys))
    names = [e.name for e in entries]
    if len(set(names)) != len(names):
        raise RegistryError("flag names must be unique")
    return entries


def _window_exception(raw: object, name: str, owner: str) -> WindowException | None:
    if raw is None:
        return None
    item = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
    reason = str(item.get("reason") or "").strip()
    by = str(item.get("approved_by") or "")
    if set(item) != {"reason", "approved_by"} or not 1 <= len(reason) <= 200:
        raise RegistryError(f"{name}: window_exception is {{reason (1-200 chars), approved_by}}")
    if not _HANDLE.fullmatch(by) or by == owner:
        raise RegistryError(f"{name}: window_exception.approved_by is the other founder's handle")
    return WindowException(reason, by)


def _journeys(raw: object, name: str) -> tuple[str, ...]:
    if raw is None:
        return ()
    found = [str(j) for j in cast(list[object], raw)] if isinstance(raw, list) else []
    if not found or not all(_JOURNEY.fullmatch(j) for j in found) or len(set(found)) != len(found):
        raise RegistryError(f"{name}: journeys is a list of distinct journey spec slugs")
    return tuple(found)


# --- release windows (Q-04-T005) ---------------------------------------------------------------


def window_of(day: date, cal: release_windows.Calendar) -> str | None:
    """The release window whose dates hold `day`, its trailing deadline week included (any
    window: flags are platform-wide)."""
    return next((w.id for w in cal.windows if w.covers(day)), None)


def window_conflicts(entries: list[Entry], cal: release_windows.Calendar) -> list[str]:
    """A flag expiring inside a window without `window_exception` (SPEC-403 AC-10)."""
    out: list[str] = []
    for e in entries:
        wid = window_of(e.expires, cal)
        if wid is not None and e.window_exception is None:
            out.append(
                f"flag {e.name} expires on {e.expires}, inside {wid} (owner {e.owner}): renew it "
                "to expire outside the window, or add window_exception {reason, approved_by}"
            )
    return out


def train_days(cal: release_windows.Calendar, start: date, end: date) -> list[date]:
    """Release train days in [start, end): the in-window Tuesday slot while production is in a
    window, else the Thursday train (P-29; docs/ops/release-windows.md §2-3)."""
    days: list[date] = []
    day = start
    while day < end:
        noon = datetime.combine(day, time(12), release_windows.CT)
        if release_windows.platform_window(cal, noon) is not None:
            slot = datetime.combine(day, cal.flip_slot.start, cal.flip_slot.tz)
            if release_windows.flip_slot(cal, slot):
                days.append(day)
        elif day.weekday() == 3:  # Thursday
            days.append(day)
        day += timedelta(days=1)
    return days


@dataclass(frozen=True)
class CalendarRow:
    name: str
    owner: str
    expires: date
    last_train: date | None
    window: str | None
    excepted: bool
    warn: bool


def flag_calendar(
    entries: list[Entry], cal: release_windows.Calendar, today: date | None = None
) -> list[CalendarRow]:
    """Every flag by expiry: its last train before expiry from today, the window it expires in,
    whether that is excepted, and a warning within 21 days (Q-04 AC-3.3)."""
    today = today or system_now().date()
    rows: list[CalendarRow] = []
    for e in sorted(entries, key=lambda x: (x.expires, x.name)):
        trains = train_days(cal, today, e.expires)
        rows.append(
            CalendarRow(
                name=e.name,
                owner=e.owner,
                expires=e.expires,
                last_train=trains[-1] if trains else None,
                window=window_of(e.expires, cal),
                excepted=e.window_exception is not None,
                warn=(e.expires - today).days <= WARN_DAYS,
            )
        )
    return rows


def calendar_lines(rows: list[CalendarRow]) -> list[str]:
    width = max((len(r.name) for r in rows), default=4)
    lines = [f"{'flag':<{width}}  owner         expires     last train  window"]
    for r in rows:
        train = r.last_train.isoformat() if r.last_train else "none left"
        window = (r.window + (" (excepted)" if r.excepted else " CONFLICT")) if r.window else ""
        mark = "  ! renew or retire" if r.warn else ""
        lines.append(f"{r.name:<{width}}  {r.owner:<12}  {r.expires}  {train:<10}  {window}{mark}")
    soon = sum(r.warn for r in rows)
    lines.append(f"{len(rows)} flags; {soon} expire within {WARN_DAYS} days")
    return lines


def constant(name: str) -> str:
    return name.replace(".", "_").upper()


def render(entries: list[Entry]) -> str:
    """One `Flag(...)` per flag, one argument per line (under `# fmt: off`)."""
    entries = sorted(entries, key=lambda e: e.name)  # the file a flag lives in never matters
    lines = [_HEADER]
    for e in entries:
        lines.append(f"{constant(e.name)} = Flag(\n")
        lines.append(f"    name={json.dumps(e.name)},\n")
        lines.append(f"    kind={json.dumps(e.kind)},\n")
        lines.append(f"    default={json.dumps(e.default)},\n")
        if e.values:
            lines.append("    values=(\n")
            lines.extend(f"        {json.dumps(v)},\n" for v in e.values)
            lines.append("    ),\n")
        lines.append(")\n")
    lines.append("\nFLAGS: dict[str, Flag] = {\n")
    lines.extend(f"    {json.dumps(e.name)}: {constant(e.name)},\n" for e in entries)
    lines.append("}\n")
    return "".join(lines)


def expired(entries: list[Entry], today: date | None = None) -> list[Entry]:
    today = today or system_now().date()
    return [e for e in entries if e.expires < today]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="feature_flags")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--calendar", action="store_true", help="make flag-calendar")
    parser.add_argument("--windows", type=Path, default=release_windows.WINDOWS_FILE)
    args = parser.parse_args(argv)
    try:
        entries = parse(source())
    except RegistryError as exc:
        print(f"feature-flags/: {exc}", file=sys.stderr)
        return 1
    try:
        cal = release_windows.load(cast(Path, args.windows))
    except release_windows.WindowsError as exc:
        print(f"deploy/windows.yaml: {exc}", file=sys.stderr)
        return 1
    if args.calendar:
        print("\n".join(calendar_lines(flag_calendar(entries, cal))))
        return 0
    output = render(entries)
    if not args.check:
        TARGET.write_text(output, encoding="utf-8")
        return 0
    status = 0
    if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != output:
        print(
            "kernel/_flags.py is stale: python -m abacus_tools.codegen.feature_flags",
            file=sys.stderr,
        )
        status = 1
    for e in expired(entries):
        print(
            f"flag {e.name} expired on {e.expires} (owner {e.owner}): remove it", file=sys.stderr
        )
        status = 1
    for problem in window_conflicts(entries, cal):
        print(problem, file=sys.stderr)
        status = 1
    return status


if __name__ == "__main__":
    sys.exit(main())
