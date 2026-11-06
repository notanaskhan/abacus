"""Form extraction (P-11-T26; P-11 F8; AC8.1 to AC8.3, AC8.6; ADR-050; DEC-2308). PROTECTED.

Code reads a known form: it identifies the form from anchor text and the tax year, loads the box
map for exactly that form and year (never another year's), and takes each value by its label. A
field's confidence is the minimum of its words' (a text layer reads 1.0) and any key-value pair's;
below 0.90 it is `low_confidence` and stored as read, never corrected or guessed. A date that does
not parse is stored as text with `low_confidence`. A model never reads a value.

The maps are repo parameter files under `evidence/forms/<form>/<tax_year>.yaml` (DEC-76). The pure
functions take words and answer fields; `extract_version` is the activity's body.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from functools import cache
from pathlib import Path
from typing import Any, Final, cast
from uuid import UUID

import yaml
from sqlalchemy import text

from abacus.kernel._flags import EVIDENCE_FORM_EXTRACTION
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import flag_variant
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.evidence.events import ExtractedFieldsRecorded
from abacus.modules.evidence.repository import pages_of
from abacus.modules.evidence.words import WORDS_VERSION, PageWords, Word, read_page_layer

FORMS: Final = Path(__file__).parent / "forms"
LOW_CONFIDENCE: Final = Decimal("0.90")
EXTRACTOR_VERSION: Final = "form-map-1"
_LINE_TOLERANCE: Final = 4.0
_GAP_LIMIT: Final = 36.0
_FAMILIES: Final[dict[str, frozenset[str]]] = {
    "off": frozenset(),
    "notices": frozenset({"notices"}),
    "notices_tax_forms": frozenset({"notices", "tax_forms"}),
    "all": frozenset({"notices", "tax_forms", "statements"}),
}
_TAX_YEAR: Final = re.compile(r"\btax\s+year:?\s*(20\d{2})\b", re.IGNORECASE)
_MONEY: Final = re.compile(r"^\(?\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)\)?$")
_DATE_FORMATS: Final = ("%B %d, %Y", "%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d")
JsonMap = Mapping[str, Any]  # Any: a YAML box map


@dataclass(frozen=True)
class FieldMap:
    key: str
    label: str
    anchor: str
    value_type: str


@dataclass(frozen=True)
class TableMap:
    """N-04-T17: rows under a header line until a stop label. Each row's leading words are its
    label; its money tokens fill `columns` in order. Values are read, never summed (AC8.7)."""

    key: str
    label: str
    header: str
    stop: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class FormMap:
    form: str
    form_type: str
    tax_year: int
    family: str
    version: str
    anchors: tuple[str, ...]
    fields: tuple[FieldMap, ...]
    tables: tuple[TableMap, ...] = ()


@dataclass(frozen=True)
class Extracted:
    field_key: str
    label: str
    value_type: str
    value_text: str
    page: int
    bbox: tuple[float, float, float, float]
    confidence: Decimal
    low_confidence: bool


@cache
def load_maps() -> tuple[FormMap, ...]:
    maps: list[FormMap] = []
    for path in sorted(FORMS.glob("*/*.yaml")):
        raw = cast(JsonMap, yaml.safe_load(path.read_text()))
        maps.append(
            FormMap(
                raw["form"], raw["form_type"], int(raw["tax_year"]), raw["family"], raw["version"],
                tuple(raw["anchors"]),
                tuple(
                    FieldMap(f["key"], f["label"], f["anchor"], f["value_type"])
                    for f in raw["fields"]
                ),
                tuple(
                    TableMap(t["key"], t["label"], t["header"], t["stop"], tuple(t["columns"]))
                    for t in raw.get("tables", ())
                ),
            )
        )  # fmt: skip
    return tuple(maps)


def page_text(page: PageWords) -> str:
    return " ".join(w.text for w in page.words)


def _lower_words(words: Sequence[Word]) -> list[str]:
    return [w.text.lower().strip(":") for w in words]


def _find_anchor(page: PageWords, anchor: str) -> list[Word] | None:
    """The anchor's words in reading order, on one line."""
    wanted = [t.lower() for t in anchor.split()]
    ordered = sorted(page.words, key=lambda w: (round(w.top / _LINE_TOLERANCE), w.x0))
    lowered = _lower_words(ordered)
    for start in range(len(ordered) - len(wanted) + 1):
        if lowered[start : start + len(wanted)] == wanted:
            found = ordered[start : start + len(wanted)]
            if abs(found[0].top - found[-1].top) <= _LINE_TOLERANCE:
                return found
    return None


def _value_words(page: PageWords, label: Sequence[Word]) -> list[Word]:
    """Words right of the label on its line, up to a wide gap; else the line just below it."""
    last = label[-1]
    same_line = sorted(
        (w for w in page.words if abs(w.top - last.top) <= _LINE_TOLERANCE and w.x0 >= last.x1),
        key=lambda w: w.x0,
    )
    taken: list[Word] = []
    previous = last.x1
    for word in same_line:
        if word.x0 - previous > _GAP_LIMIT and taken:
            break
        taken.append(word)
        previous = word.x1
    if taken:
        return taken
    below = [
        w
        for w in page.words
        if label[0].x0 - _LINE_TOLERANCE <= w.x0 <= last.x1 + _GAP_LIMIT and w.top > last.bottom
    ]
    if not below:
        return []
    nearest = min(w.top for w in below)
    return sorted(
        (w for w in below if abs(w.top - nearest) <= _LINE_TOLERANCE), key=lambda w: w.x0
    )


def _normalise(value_type: str, raw: str) -> tuple[str, bool]:
    """The stored text and whether it could be read as its type (never guessed)."""
    cleaned = raw.strip().rstrip(".,;:")
    if value_type == "money":
        match = _MONEY.match(cleaned)
        if match is None:
            return cleaned, False
        try:
            return f"{Decimal(match.group(1).replace(',', '')):.2f}", True
        except InvalidOperation:
            return cleaned, False
    if value_type == "date":
        for fmt in _DATE_FORMATS:
            try:
                return datetime.strptime(cleaned, fmt).date().isoformat(), True
            except ValueError:
                continue
        return cleaned, False
    return cleaned, True


def identify(pages: Sequence[PageWords]) -> FormMap | None:
    """The map for this form and its own tax year; another year's map is never used (AC8.6)."""
    joined = " ".join(page_text(p) for p in pages)
    match = _TAX_YEAR.search(joined)
    year = int(match.group(1)) if match else None
    for form_map in load_maps():
        known = all(re.search(rf"\b{re.escape(a)}\b", joined) for a in form_map.anchors)
        if known and year == form_map.tax_year:
            return form_map
    return None


def extract(form_map: FormMap, pages: Sequence[PageWords]) -> tuple[Extracted, ...]:
    """Each field by its label, first page that has it. A field with no value is not written."""
    out: list[Extracted] = []
    for field in form_map.fields:
        for page in pages:
            label = _find_anchor(page, field.anchor)
            if label is None:
                continue
            words = _value_words(page, label)
            if not words:
                continue
            raw = " ".join(w.text for w in words)
            value, readable = _normalise(field.value_type, raw)
            confidence = min(Decimal(str(w.confidence)) for w in words)
            box = (
                min(w.x0 for w in words),
                min(w.top for w in words),
                max(w.x1 for w in words),
                max(w.bottom for w in words),
            )
            out.append(
                Extracted(
                    field.key, field.label, field.value_type, value, page.page, box,
                    confidence.quantize(Decimal("0.001")),
                    confidence < LOW_CONFIDENCE or not readable,
                )
            )  # fmt: skip
            break
    for table in form_map.tables:
        for page in pages:
            cells = extract_table(table, page)
            if cells:
                out.extend(cells)
                break
    return tuple(out)


def _slug(words: Sequence[str]) -> str:
    joined = re.sub(r"[^a-z0-9]+", "_", " ".join(words).lower()).strip("_")
    return (joined or "row")[:40]


def _lines_below(page: PageWords, top: float, stop_top: float) -> list[list[Word]]:
    lines: dict[int, list[Word]] = {}
    for word in page.words:
        if top < word.top < stop_top:
            lines.setdefault(round(word.top / _LINE_TOLERANCE), []).append(word)
    return [sorted(lines[k], key=lambda w: w.x0) for k in sorted(lines)]


def extract_table(table: TableMap, page: PageWords) -> tuple[Extracted, ...]:
    """A table's cells as separate fields; a row's unreadable amount is low confidence as read."""
    header = _find_anchor(page, table.header)
    if header is None:
        return ()
    stop = _find_anchor(page, table.stop)
    stop_top = stop[0].top if stop is not None and stop[0].top > header[0].top else page.height
    out: list[Extracted] = []
    for line in _lines_below(page, header[0].bottom - 1, stop_top):
        names: list[Word] = []
        cells: list[Word] = []
        for word in line:
            looks_like_amount = _MONEY.match(word.text.rstrip(".,;:")) is not None
            (cells if cells or looks_like_amount else names).append(word)
        if not names or not cells:
            continue
        slug = _slug([w.text for w in names])
        name = " ".join(w.text for w in names)
        for column, word in zip(table.columns, cells, strict=False):
            value, readable = _normalise("money", word.text)
            confidence = min(Decimal(str(word.confidence)), *(
                Decimal(str(w.confidence)) for w in names
            ))  # fmt: skip
            out.append(
                Extracted(
                    f"{table.key}.{slug}.{column}", f"{table.label} · {name} · {column}"[:200],
                    "money", value, page.page, (word.x0, word.top, word.x1, word.bottom),
                    confidence.quantize(Decimal("0.001")),
                    confidence < LOW_CONFIDENCE or not readable,
                )
            )  # fmt: skip
    return tuple(out)


def covers(variant: str, family: str) -> bool:
    return family in _FAMILIES.get(variant, frozenset())


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "evidence.form_extraction")


async def extract_version(tenant_id: UUID, version_id: UUID) -> int:
    """`forms.extract`: identify, extract and record; returns the fields written. Idempotent."""
    tenant = _system(tenant_id)
    async with tenant_session(tenant) as session:
        already = await session.scalar(
            text("SELECT count(*) FROM extracted_fields WHERE evidence_version_id = :v"),
            {"v": version_id},
        )
        pages = await pages_of(
            session,
            evidence_version_id=version_id,
            inbox_file_id=None,
            inbox_attachment_id=None,
            extractor_version=WORDS_VERSION,
        )
    if already:
        return int(already)
    layers = [await read_page_layer(tenant_id, page) for page in pages]
    form_map = identify(layers)
    variant = await flag_variant(tenant, EVIDENCE_FORM_EXTRACTION)
    if form_map is None or not covers(variant, form_map.family):
        return 0
    found = extract(form_map, layers)
    if not found:
        return 0
    async with uow(tenant) as tx:
        for field in found:
            await tx.session.execute(
                text(
                    "INSERT INTO extracted_fields (tenant_id, evidence_version_id, form_type, "
                    "tax_year, form_map_version, field_key, label, value_type, value_text, "
                    "page_no, bbox, confidence, low_confidence, extractor_kind, "
                    "extractor_version, match_id) VALUES (:t, :v, :form, :year, :map, :key, "
                    ":label, :type, :value, :page, CAST(:bbox AS numeric(10,2)[]), :confidence, "
                    ":low, 'form_map', :extractor, :match)"
                ),
                {
                    "t": tenant_id,
                    "v": version_id,
                    "form": form_map.form_type,
                    "year": form_map.tax_year,
                    "map": form_map.version,
                    "key": field.field_key,
                    "label": field.label,
                    "type": field.value_type,
                    "value": field.value_text,
                    "page": field.page,
                    "bbox": [str(round(c, 2)) for c in field.bbox],
                    "confidence": field.confidence,
                    "low": field.low_confidence,
                    "extractor": EXTRACTOR_VERSION,
                    "match": f"ev:{version_id}#field:{field.field_key}",
                },
            )
        tx.emit(
            ExtractedFieldsRecorded(
                evidence_version_id=version_id,
                form_type=form_map.form_type,
                tax_year=form_map.tax_year,
                fields=len(found),
                low_confidence=sum(1 for f in found if f.low_confidence),
            )
        )
        tx.record(
            "extracted_fields.recorded",
            target=Target("evidence_version", version_id),
            after=Ref(form=form_map.form_type, fields=len(found)),
        )
    return len(found)
