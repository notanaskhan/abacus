"""The `fs_draft` engine (A-06-T25; A-06 §4.5; ADR-050): statements from the final TB, by code.

Input is the ledger's presented statements over the C9 FS-line taxonomy; output is the version's
line items and linked values with a content hash. Every leaf line is `tb_linked` (with the account
codes and the entries it reflects as its source reference), and group and class totals are
`formula`. Pure: Decimal only, no clock, no model.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from decimal import Decimal
from typing import Final, Protocol

ENGINE_VERSION: Final = "fs_draft@1"
POSITION: Final = "financial_position"
ACTIVITIES: Final = "activities"
_STATEMENT_OF: Final = {
    "assets": POSITION,
    "liabilities": POSITION,
    "equity": POSITION,
    "revenue": ACTIVITIES,
    "expenses": ACTIVITIES,
}
_KEY: Final = re.compile(r"[^a-z0-9_.]+")
_PLACEHOLDER: Final = re.compile(r"\{\{\s*([A-Za-z0-9][A-Za-z0-9_.:-]{0,79})\s*\}\}")
_ZERO: Final = Decimal(0)


class LineInput(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def label(self) -> str: ...
    @property
    def cy(self) -> Decimal: ...
    @property
    def py(self) -> Decimal | None: ...


class GroupInput(Protocol):
    @property
    def key(self) -> str: ...
    @property
    def label(self) -> str: ...
    @property
    def class_(self) -> str: ...
    @property
    def lines(self) -> Sequence[LineInput]: ...
    @property
    def cy(self) -> Decimal: ...
    @property
    def py(self) -> Decimal | None: ...


@dataclass(frozen=True)
class DraftValue:
    year: int
    value: Decimal
    source: str  # tb_linked or formula
    accounts: tuple[str, ...] = ()
    entries: tuple[str, ...] = ()
    terms: tuple[str, ...] = ()  # a formula's own line keys


@dataclass(frozen=True)
class DraftLine:
    statement_key: str
    section_key: str
    line_key: str
    label: str
    position: int
    note_ref: str | None
    values: tuple[DraftValue, ...]


@dataclass(frozen=True)
class NoteInput:
    number: int
    title: str
    body: str
    line_keys: tuple[str, ...]


@dataclass(frozen=True)
class DraftNote:
    number: int
    title: str
    body: str
    unresolved: tuple[str, ...]  # figures the body names that this draft has no line for


def line_key(raw: str) -> str:
    """A key the line-items CHECK accepts: the taxonomy's key, lower-cased and dotted."""
    cleaned = _KEY.sub("_", raw.lower()).strip("_.")
    if not cleaned or not cleaned[0].isalpha():
        cleaned = f"l_{cleaned}"
    return cleaned[:80]


def _values(
    year: int,
    cy: Decimal,
    py: Decimal | None,
    source: str,
    *,
    accounts: tuple[str, ...] = (),
    entries: tuple[str, ...] = (),
    terms: tuple[str, ...] = (),
) -> tuple[DraftValue, ...]:
    current = DraftValue(year, cy, source, accounts, entries, terms)
    if py is None:
        return (current,)
    return (current, DraftValue(year - 1, py, source, accounts, (), terms))


def draft(
    groups: Sequence[GroupInput],
    year: int,
    accounts_of: Mapping[str, tuple[str, ...]],
    entries: tuple[str, ...],
    note_refs: Mapping[str, str],
) -> tuple[DraftLine, ...]:
    """The version's lines in presentation order, with totals as formulas over their own lines."""
    out: list[DraftLine] = []
    position = 0
    class_terms: dict[str, list[str]] = {}
    class_values: dict[str, tuple[Decimal, Decimal | None]] = {}
    for group in groups:
        statement = _STATEMENT_OF.get(group.class_)
        if statement is None:
            continue
        section = line_key(group.key).replace(".", "_")
        terms: list[str] = []
        for line in group.lines:
            key = line_key(line.key)
            terms.append(key)
            out.append(
                DraftLine(
                    statement,
                    section,
                    key,
                    line.label,
                    position,
                    note_refs.get(key),
                    _values(
                        year,
                        line.cy,
                        line.py,
                        "tb_linked",
                        accounts=accounts_of.get(line.key, ()),
                        entries=entries,
                    ),
                )
            )
            position += 1
        total_key = f"{section}.total"
        out.append(
            DraftLine(
                statement,
                section,
                total_key,
                f"Total {group.label}",
                position,
                None,
                _values(year, group.cy, group.py, "formula", terms=tuple(terms)),
            )
        )
        position += 1
        class_terms.setdefault(group.class_, []).append(total_key)
        cy, py = class_values.get(group.class_, (_ZERO, None if group.py is None else _ZERO))
        class_values[group.class_] = (
            cy + group.cy,
            None if py is None or group.py is None else py + group.py,
        )
    for class_, terms in class_terms.items():
        cy, py = class_values[class_]
        out.append(
            DraftLine(
                _STATEMENT_OF[class_],
                f"class_{class_}",
                f"class.{class_}.total",
                f"Total {class_}",
                position,
                None,
                _values(year, cy, py, "formula", terms=tuple(terms)),
            )
        )
        position += 1
    return tuple(out)


def _plain(line: DraftLine) -> dict[str, object]:
    body = asdict(line)
    body["values"] = [{**asdict(value), "value": str(value.value)} for value in line.values]
    return body


def references_of(notes: Sequence[NoteInput]) -> dict[str, str]:
    """Each FS line's reference, from the notes that name it: "Note 3", or "Notes 3, 4"."""
    numbers: dict[str, list[int]] = {}
    for note in notes:
        for key in note.line_keys:
            numbers.setdefault(line_key(key), []).append(note.number)
    return {
        key: f"Note {found[0]}" if len(found) == 1 else f"Notes {', '.join(map(str, found))}"
        for key, found in ((k, sorted(set(v))) for k, v in numbers.items())
    }


def _figure(value: Decimal) -> str:
    places = 0 if value == value.to_integral_value() else 2
    written = f"{abs(value):,.{places}f}"
    return f"({written})" if value < 0 else written


def _filled(body: str, figures: Mapping[str, str]) -> tuple[str, tuple[str, ...]]:
    missing: list[str] = []

    def figure(found: re.Match[str]) -> str:
        known = figures.get(line_key(found[1]))
        if known is None:
            missing.append(found[1])
        return known or found[0]

    return _PLACEHOLDER.sub(figure, body), tuple(sorted(set(missing)))


def render_notes(
    notes: Sequence[NoteInput], lines: Sequence[DraftLine], year: int
) -> tuple[DraftNote, ...]:
    """Each note with `{{line.key}}` filled from the year's value on the version's own lines. A key
    with no line stays as written and is named, for a person to see; code never guesses a figure.
    """
    figures = {
        line.line_key: _figure(value.value)
        for line in lines
        for value in line.values
        if value.year == year
    }
    return tuple(
        DraftNote(note.number, note.title, *_filled(note.body, figures)) for note in notes
    )


def content_hash(lines: Sequence[DraftLine], notes: Sequence[DraftNote] = ()) -> str:
    plain = [_plain(line) for line in lines]
    written: object = plain
    if notes:
        written = {"lines": plain, "notes": [[n.number, n.title, n.body] for n in notes]}
    canonical = json.dumps(written, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def adjustments_hash(entry_refs: Sequence[str]) -> str:
    """Of the recorded entries a version reflects; a new approved entry changes it."""
    return hashlib.sha256("|".join(sorted(entry_refs)).encode()).hexdigest()
