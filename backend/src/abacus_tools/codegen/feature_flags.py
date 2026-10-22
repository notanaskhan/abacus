"""Validate the feature flag registry and generate `abacus.kernel._flags` (ADR-089; SPEC-011).

Run: python -m abacus_tools.codegen.feature_flags [--check]

`--check` (in `make check-fast`) fails when the generated module is stale, the registry is
invalid (AC-6), or any flag has expired (AC-4, TASK-026 D1): an expired flag must be removed
from the registry and the code.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import cast

import yaml

from abacus.kernel.clock import system_now

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
    "override"  # DEC-137
}
_HEADER = '''"""GENERATED from docs/architecture/feature-flags/*.yaml. Do not edit.

Regenerate: python -m abacus_tools.codegen.feature_flags
"""

from abacus.kernel.flags import Flag

# fmt: off
'''


@dataclass(frozen=True)
class Entry:
    name: str
    owner: str
    expires: date
    kind: str
    values: tuple[str, ...]
    default: str


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
        entries.append(Entry(name, str(item["owner"]), expires, kind, values, default))
    names = [e.name for e in entries]
    if len(set(names)) != len(names):
        raise RegistryError("flag names must be unique")
    return entries


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
    args = parser.parse_args(argv)
    try:
        entries = parse(source())
    except RegistryError as exc:
        print(f"feature-flags/: {exc}", file=sys.stderr)
        return 1
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
    return status


if __name__ == "__main__":
    sys.exit(main())
