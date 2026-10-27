"""Reading a practice-management client list for CLI-06's bulk import (P-07-T52; Story 3.2).

Hostile input (ADR-052), in the `requests/workbook.py` pattern: bounded (`MAX_BYTES`,
`MAX_ROWS`), read as UTF-8 CSV and never evaluated, and problems are fixed codes, never a cell's
contents. Columns are mapped by their heading: the known CCH Axcess Tax client-list headings and
plain synonyms (DEC-643); a column with no known heading is ignored and named in no output.

Every cell is cleaned before the import keeps it: bidirectional controls and other control
characters are removed (note `bidi_removed`), whitespace collapsed, and the text bounded. A cell
beginning `=`, `+`, `-` or `@` is kept as inert text (note `formula_like`): nothing here or
downstream evaluates it, and the one CSV writer escapes it (`literal_cell`). Any TIN form in a
name or email cell is scrubbed (note `tin_in_text`), so names never carry TIN digits; a TIN comes
only from a TIN column, as nine digits with its kind. `digits` is Restricted: never log it.
"""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from typing import Final, Literal

from abacus.kernel.tin_patterns import find_tins, scrub_tins, valid_itin

Source = Literal["cch_axcess_tax_export", "csv"]
Field = Literal[
    "client_name", "entity_name", "entity_type", "ein", "ssn", "tin", "contact_name", "email"
]
TinKind = Literal["ein", "ssn", "itin"]

MAX_BYTES: Final = 5 * 1024 * 1024
MAX_ROWS: Final = 2000
MAX_CELL: Final = 200
_SPACE = re.compile(r"\s+")
_HEADING = re.compile(r"[^a-z0-9]+")
_DIGITS = re.compile(r"[^0-9]")
# Bidirectional embeddings, overrides, isolates and marks (Trojan Source), then other controls.
_BIDI = re.compile("[؜‎‏‪-‮⁦-⁩]")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]")
_FORMULA_LEADS: Final = ("=", "+", "-", "@")
_SSN_SHAPE = re.compile(r"[0-9]{3}[ -][0-9]{2}[ -][0-9]{4}")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Headings, normalised (lower case, runs of other characters as one space). The CCH Axcess Tax
# client-list export's headings are the first of each group (inferred from the firm's export
# layout; DEC-643); the rest are the plain synonyms a firm's own CSV may use.
HEADINGS: Final[dict[str, Field]] = {
    "client name": "client_name",
    "name": "client_name",
    "display name": "client_name",
    "client": "client_name",
    "entity name": "entity_name",
    "legal name": "entity_name",
    "client type": "entity_type",
    "entity type": "entity_type",
    "type": "entity_type",
    "federal id number": "ein",
    "fein": "ein",
    "ein": "ein",
    "federal ein": "ein",
    "ssn": "ssn",
    "taxpayer ssn": "ssn",
    "social security number": "ssn",
    "itin": "ssn",
    "tax id": "tin",
    "taxpayer id": "tin",
    "tin": "tin",
    "primary contact": "contact_name",
    "contact name": "contact_name",
    "contact": "contact_name",
    "email address": "email",
    "primary email": "email",
    "contact email": "email",
    "email": "email",
}
# What the CCH export must carry to be read as one (the CSV source maps any name heading).
CCH_REQUIRED: Final = "client name"

# Entity type cells to the registered `client_entities.entity_type` codes; a cell not here is
# kept as no type with the note `entity_type_unknown`.
ENTITY_TYPE_WORDS: Final[dict[str, str]] = {
    "individual": "individual",
    "person": "individual",
    "1040": "individual",
    "married filing jointly": "household_mfj",
    "mfj": "household_mfj",
    "household": "household_mfj",
    "c corporation": "c_corp",
    "c corp": "c_corp",
    "corporation": "c_corp",
    "1120": "c_corp",
    "s corporation": "s_corp",
    "s corp": "s_corp",
    "1120s": "s_corp",
    "1120 s": "s_corp",
    "llc": "llc",
    "limited liability company": "llc",
    "partnership": "partnership",
    "1065": "partnership",
    "trust": "trust",
    "fiduciary": "trust",
    "1041": "trust",
    "estate": "estate",
    "706": "estate",
    "employee benefit plan": "ebp_plan",
    "benefit plan": "ebp_plan",
    "5500": "ebp_plan",
    "exempt organization": "exempt_org",
    "exempt": "exempt_org",
    "nonprofit": "exempt_org",
    "990": "exempt_org",
}


class ImportFileInvalid(Exception):
    """The file can't be read as a client list: `code` says why (never its contents)."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ParsedTin:
    kind: TinKind
    digits: str  # Restricted


@dataclass(frozen=True)
class ParsedRow:
    row_no: int  # its place among the rows kept, from 1
    client_name: str
    entity_name: str
    entity_type: str | None
    contact_name: str | None
    email: str | None
    tin: ParsedTin | None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ParsedFile:
    mapping: dict[str, str]  # the column's heading (cleaned) to the field code
    rows: list[ParsedRow] = field(default_factory=list[ParsedRow])


def heading_key(text: str) -> str:
    return _HEADING.sub(" ", text.casefold()).strip()


def clean_cell(raw: str) -> tuple[str, set[str]]:
    """The cell as the import keeps it, and its notes."""
    notes: set[str] = set()
    text = raw
    if _BIDI.search(text):
        text = _BIDI.sub("", text)
        notes.add("bidi_removed")
    text = _SPACE.sub(" ", _CONTROL.sub("", text)).strip()
    if len(text) > MAX_CELL:
        text = text[:MAX_CELL].rstrip()
        notes.add("truncated")
    if text.startswith(_FORMULA_LEADS):
        notes.add("formula_like")
    return text, notes


def _text(raw: str, notes: set[str]) -> str:
    text, found = clean_cell(raw)
    scrubbed = scrub_tins(text)
    if scrubbed != text:
        found.add("tin_in_text")
    notes.update(found)
    return scrubbed


def entity_type_of(text: str) -> str | None:
    return ENTITY_TYPE_WORDS.get(heading_key(text))


def _tin(raw: str, column: Field, notes: set[str]) -> ParsedTin | None:
    text, _ = clean_cell(raw)
    if not text:
        return None
    digits = _DIGITS.sub("", text)
    if len(digits) != 9 or digits == "000000000":
        notes.add("tin_invalid")
        return None
    personal = ParsedTin("itin" if valid_itin(digits) else "ssn", digits)
    if column == "ssn":
        return personal
    if column == "ein":
        # CCH's Federal ID Number holds an individual's SSN or ITIN too: its form says which.
        return personal if _SSN_SHAPE.fullmatch(text) else ParsedTin("ein", digits)
    found = find_tins(text)
    if len(found) != 1:
        notes.add("tin_invalid")
        return None
    return ParsedTin(found[0].type, found[0].digits)


def _decode(content: bytes) -> str:
    if not content:
        raise ImportFileInvalid("empty_file")
    if len(content) > MAX_BYTES:
        raise ImportFileInvalid("file_too_large")
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise ImportFileInvalid("not_utf8_csv") from None


def _mapping(headings: list[str], source: Source) -> dict[int, Field]:
    keys = [heading_key(clean_cell(h)[0]) for h in headings]
    if source == "cch_axcess_tax_export" and CCH_REQUIRED not in keys:
        raise ImportFileInvalid("not_cch_export")
    mapped: dict[int, Field] = {}
    taken: set[Field] = set()
    for position, key in enumerate(keys):
        wanted = HEADINGS.get(key)
        if wanted is not None and wanted not in taken:  # the first column of a field wins
            mapped[position] = wanted
            taken.add(wanted)
    if "client_name" not in taken:
        raise ImportFileInvalid("no_name_column")
    return mapped


def parse_client_list(content: bytes, source: Source) -> ParsedFile:
    """Every data row with a name, in file order (a row without one is left out and noted in no
    count: it isn't a client). 422-worthy problems raise `ImportFileInvalid`."""
    reader = csv.reader(io.StringIO(_decode(content), newline=""), strict=False)
    try:
        headings = next(reader)
    except (StopIteration, csv.Error):
        raise ImportFileInvalid("no_rows") from None
    mapped = _mapping(headings, source)
    rows: list[ParsedRow] = []
    try:
        for number, cells in enumerate(reader, start=1):
            if number > MAX_ROWS:
                raise ImportFileInvalid("too_many_rows")
            notes: set[str] = set()
            values: dict[Field, str] = {}
            tin: ParsedTin | None = None
            for position, wanted in mapped.items():
                raw = cells[position] if position < len(cells) else ""
                if wanted in ("ein", "ssn", "tin"):
                    tin = tin or _tin(raw, wanted, notes)
                else:
                    values[wanted] = _text(raw, notes)
            name = values.get("client_name", "")
            if not name:
                continue
            kind_text = values.get("entity_type", "")
            entity_type = entity_type_of(kind_text) if kind_text else None
            if kind_text and entity_type is None:
                notes.add("entity_type_unknown")
            email = values.get("email") or None
            if email is not None and not _EMAIL.fullmatch(email):
                notes.add("email_invalid")
                email = None
            rows.append(
                ParsedRow(
                    row_no=len(rows) + 1,
                    client_name=name,
                    entity_name=values.get("entity_name") or name,
                    entity_type=entity_type,
                    contact_name=values.get("contact_name") or None,
                    email=email,
                    tin=tin,
                    notes=tuple(sorted(notes)),
                )
            )
    except csv.Error:
        raise ImportFileInvalid("not_utf8_csv") from None
    if not rows:
        raise ImportFileInvalid("no_rows")
    return ParsedFile(
        {
            scrub_tins(clean_cell(headings[p])[0])[:64] or f"column {p + 1}": f
            for p, f in sorted(mapped.items())
        },
        rows,
    )
