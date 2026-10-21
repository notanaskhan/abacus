"""Validate the status registry and generate the backend and UI status data (C2; F-03-T09).

Run: python -m abacus_tools.codegen.status_vocabulary [--check]

Source: docs/product/status-vocabulary.yaml (ADR-138, DEC-08). Outputs:
- `abacus.kernel._statuses`: one StrEnum per object with its stored codes (derived codes such as
  `overdue` are never stored), and the SQL CHECK list for each.
- `packages/ui/src/status.gen.ts`: every code's label, variant and flags for the UI runtime, the
  retired codes, and where each of the 144 words in the handoff's `lib/status.js` went
  (`HANDOFF_WORDS`: a registry code, or retired with its reason and replacement; F-05-T12).

`--check` (in `make check-fast`) fails when either output is stale or the registry is invalid.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml

BACKEND = Path(__file__).resolve().parents[3]
ROOT = BACKEND.parent
SOURCE = ROOT / "docs" / "product" / "status-vocabulary.yaml"
PY_TARGET = BACKEND / "src" / "abacus" / "kernel" / "_statuses.py"
TS_TARGET = ROOT / "packages" / "ui" / "src" / "status.gen.ts"
_CODE = re.compile(r"^[a-z][a-z0-9_]*$")
_RETIRED_CODE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,2}$")
_VARIANTS = {
    "state",
    "amber",
    "green-tint",
    "green",
    "red-tint",
    "red",
    "neutral",
    "muted",
    "soon",
    "outline",
    "tag",
}
_REQUIRED = ("label", "variant", "terminal", "derived")
_OPTIONAL = {"disc", "context_labels", "client_label", "text_tone", "context_variants", "emphasis"}
# The handoff's lib/status.js is closed: 21 objects and 144 words (F-05-T12).
HANDOFF_OBJECT_COUNT = 21
HANDOFF_WORD_COUNT = 144


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class Code:
    code: str
    fields: dict[str, object]

    @property
    def derived(self) -> bool:
        return bool(self.fields["derived"])


@dataclass(frozen=True)
class StatusObject:
    name: str
    codes: tuple[Code, ...]


def parse(source: str) -> list[StatusObject]:
    """Every object and code, validated (AC-2)."""
    document = cast(dict[str, object], yaml.safe_load(source) or {})
    raw = cast(dict[str, dict[str, object]], document.get("objects") or {})
    objects: list[StatusObject] = []
    for name, body in raw.items():
        if not _CODE.fullmatch(name):
            raise RegistryError(f"{name!r}: an object name is snake_case")
        codes_raw = cast(dict[str, dict[str, object]], body.get("codes") or {})
        if not codes_raw:
            raise RegistryError(f"{name}: no codes")
        codes: list[Code] = []
        for code, fields in codes_raw.items():
            where = f"{name}.{code}"
            if not _CODE.fullmatch(code):
                raise RegistryError(f"{where}: a code is snake_case")
            missing = [f for f in _REQUIRED if f not in fields]
            if missing:
                raise RegistryError(f"{where}: missing {missing}")
            unknown = set(fields) - set(_REQUIRED) - _OPTIONAL
            if unknown:
                raise RegistryError(f"{where}: unknown fields {sorted(unknown)}")
            variant = fields["variant"]
            if variant is not None and variant not in _VARIANTS:
                raise RegistryError(f"{where}: variant {variant!r} (match is never a status)")
            label = str(fields["label"])
            words = [w for w in re.findall(r"[A-Za-z]+", label) if len(w) > 1]
            title_case = len(words) > 1 and all(w[0].isupper() and not w.isupper() for w in words)
            if not label.strip() or title_case:
                raise RegistryError(f"{where}: a label is sentence case, not Title Case")
            codes.append(Code(code, dict(fields)))
        objects.append(StatusObject(name, tuple(codes)))
    return objects


def parse_handoff(
    source: str, objects: list[StatusObject]
) -> dict[str, dict[str, dict[str, object]]]:
    """Where every handoff status word went: a registry code, or retired with its reason.

    Each of the 144 words is either `{object, code}` naming a registry code that exists, or
    `{status: false, reason, replacement?}` (retired; `replacement` is an `object.code` when one
    exists). Nothing else, so a word cannot be dropped without a decision (F-05-T12).
    """
    document = cast(dict[str, object], yaml.safe_load(source) or {})
    raw = cast(dict[str, dict[str, dict[str, object]]], document.get("handoff_words") or {})
    known = {obj.name: {c.code for c in obj.codes} for obj in objects}
    words: dict[str, dict[str, dict[str, object]]] = {}
    for handoff_object, entries in raw.items():
        words[handoff_object] = {}
        for word, entry in entries.items():
            where = f"handoff_words.{handoff_object}.{word}"
            if entry.get("status") is False:
                reason = entry.get("reason")
                if not isinstance(reason, str) or not reason.strip():
                    raise RegistryError(f"{where}: a retired word gives its reason")
                replacement = entry.get("replacement")
                if replacement is not None:
                    obj_name, _, code = str(replacement).partition(".")
                    if code not in known.get(obj_name, set()):
                        raise RegistryError(f"{where}: replacement {replacement!r} is not a code")
                words[handoff_object][word] = {
                    "retired": True,
                    "reason": reason,
                    "replacement": replacement,
                }
                continue
            target, code = str(entry.get("object")), str(entry.get("code"))
            if code not in known.get(target, set()):
                raise RegistryError(f"{where}: {target}.{code} is not in the registry")
            words[handoff_object][word] = {"object": target, "code": code}
    count = sum(len(entries) for entries in words.values())
    if len(words) != HANDOFF_OBJECT_COUNT or count != HANDOFF_WORD_COUNT:
        raise RegistryError(
            f"handoff_words: {len(words)} objects and {count} words, "
            f"expected {HANDOFF_OBJECT_COUNT} and {HANDOFF_WORD_COUNT}"
        )
    return words


def parse_retired(source: str) -> dict[str, dict[str, object]]:
    """The retired codes, key -> {replacement: [...], note?}.

    Keys like `request_item.open` or `ui.workpaper.draft` are codes. The block also lists retired
    words and tables (`label.Evidence check`, `handoff.lib/status.js`); those stay in the YAML as
    prose and are not emitted, because the UI never looks them up (and a banned term in a key
    would trip the scope guards).
    """
    document = cast(dict[str, object], yaml.safe_load(source) or {})
    raw = cast(dict[str, dict[str, object]], document.get("retired") or {})
    retired: dict[str, dict[str, object]] = {}
    for key, entry in raw.items():
        if not isinstance(entry.get("replacement"), list):
            raise RegistryError(f"retired.{key}: replacement is a list")
        if _RETIRED_CODE.fullmatch(key):
            retired[key] = {k: v for k, v in entry.items() if k in {"replacement", "note"}}
    return retired


def _class(name: str) -> str:
    return "".join(part.capitalize() for part in name.split("_")) + "Status"


def render_py(objects: list[StatusObject]) -> str:
    lines = [
        '"""GENERATED from docs/product/status-vocabulary.yaml. Do not edit.\n\n'
        'Regenerate: python -m abacus_tools.codegen.status_vocabulary\n"""\n\n'
        "from enum import StrEnum\n\n# fmt: off\n"
    ]
    stored_lines: list[str] = []
    for obj in objects:
        stored = [c.code for c in obj.codes if not c.derived]
        derived = [c.code for c in obj.codes if c.derived]
        lines.append(f"\n\nclass {_class(obj.name)}(StrEnum):\n")
        if stored:
            lines.extend(f"    {code.upper()} = {json.dumps(code)}\n" for code in stored)
        else:
            lines.append("    pass\n")
        if derived:
            lines.append(f"    # derived, never stored: {', '.join(derived)}\n")
        stored_lines.append(f"    {json.dumps(obj.name)}: (\n")
        stored_lines.extend(f"        {json.dumps(code)},\n" for code in stored)
        stored_lines.append("    ),\n")
    lines.append("\n\n# Each object's stored codes, and their SQL CHECK list.\n")
    lines.append("STORED: dict[str, tuple[str, ...]] = {\n")
    lines.extend(stored_lines)
    lines.append("}\n")
    lines.append(
        "CHECKS: dict[str, str] = {\n"
        '    name: "(" + ", ".join(f"\'{code}\'" for code in codes) + ")"\n'
        "    for name, codes in STORED.items()\n"
        "}\n"
    )
    return "".join(lines)


def _ts_fields(fields: dict[str, object]) -> dict[str, object]:
    rename = {
        "client_label": "clientLabel",
        "context_labels": "contextLabels",
        "context_variants": "contextVariants",
        "text_tone": "textTone",
    }
    keep = (
        "label",
        "variant",
        "terminal",
        "derived",
        "client_label",
        "context_labels",
        "context_variants",
        "disc",
        "text_tone",
        "emphasis",
    )
    return {rename.get(k, k): fields[k] for k in keep if k in fields}


def _ts_const(name: str, value: object) -> str:
    body = json.dumps(value, indent=2, ensure_ascii=False)
    return f"export const {name} = {body} as const;\n"


def render_ts(
    objects: list[StatusObject],
    handoff: dict[str, dict[str, dict[str, object]]],
    retired: dict[str, dict[str, object]],
) -> str:
    registry = {obj.name: {c.code: _ts_fields(c.fields) for c in obj.codes} for obj in objects}
    return (
        "// GENERATED from docs/product/status-vocabulary.yaml. Do not edit.\n"
        "// Regenerate: python -m abacus_tools.codegen.status_vocabulary "
        "(C2; F-03-T09, F-05-T12).\n\n"
        + _ts_const("STATUS_REGISTRY", registry)
        + "\n// Where each word of the handoff status.js went: a registry code, or retired.\n"
        + _ts_const("HANDOFF_WORDS", handoff)
        + "\n// Codes and words retired from the repo and the design sources, with replacements.\n"
        + _ts_const("RETIRED_CODES", retired)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="status_vocabulary")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    try:
        source = SOURCE.read_text(encoding="utf-8")
        objects = parse(source)
        handoff = parse_handoff(source, objects)
        retired = parse_retired(source)
    except RegistryError as exc:
        print(f"status-vocabulary.yaml: {exc}", file=sys.stderr)
        return 1
    outputs = {PY_TARGET: render_py(objects), TS_TARGET: render_ts(objects, handoff, retired)}
    if args.check:
        stale = [p for p, text in outputs.items() if not p.exists() or p.read_text() != text]
        for path in stale:
            print(f"{path.relative_to(ROOT)} is out of date", file=sys.stderr)
        return 1 if stale else 0
    for path, text in outputs.items():
        path.write_text(text, encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
