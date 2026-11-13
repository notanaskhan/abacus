"""P-11-T37 (TASK-6527; ADR-078; DEC-3127): independent acceptance tests for form extraction.

Row acceptance: "Each extraction rule is proven by tests written outside the implementing
session, including an unsupported tax year that yields manual entry rather than guessed values."

Written from P-11 F8 (AC8.1 to AC8.7) and SPEC-029 against the public functions only, over the
synthetic scanned corpus (P-11-T28) replayed through the OCR normaliser, never the
implementation's own fixtures. Solo edition: "outside the implementing session" is this separate
task and session (DEC-3127), not a second person.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import re
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import asynccontextmanager
from decimal import Decimal
from typing import Any, Final
from uuid import uuid4

import pytest

from abacus.kernel import ocr
from abacus.modules.evidence import form_extraction as fx
from abacus.modules.evidence import ocr_step, statement_tables
from abacus.modules.evidence.pii import names_a_tin
from abacus.modules.evidence.words import PageWords, Word
from abacus_tools.synthetic.scanned_corpus import generate

LETTER: Final = {"width_pt": Decimal(612), "height_pt": Decimal(792)}
TIN: Final = re.compile(r"\b\d{3}-?\d{2}-?\d{4}\b|\b\d{2}-?\d{7}\b")
FAMILIES: Final = ("notices", "tax_forms", "statements")
VARIANTS: Final = ("off", "notices", "notices_tax_forms", "all")


def _blocks(key: str) -> list[dict[str, Any]]:  # Any: untyped JSON or YAML (a test double)
    page = next(p for p in generate() if p.key == key)
    return list(json.loads(page.textract)["Blocks"])


def _layer(
    key: str, edit: Callable[[str], str] = lambda t: t, confidence: float | None = None
) -> PageWords:
    blocks = _blocks(key)
    for block in blocks:
        block["Text"] = edit(str(block["Text"]))
        if confidence is not None:
            block["Confidence"] = confidence
    words = ocr.normalise(blocks, **LETTER)
    return PageWords(
        1, 612.0, 792.0, 0,
        tuple(
            Word(w.text, float(w.bbox[0]), float(w.bbox[1]), float(w.bbox[2]), float(w.bbox[3]),
                 float(w.confidence))
            for w in words
        ),
    )  # fmt: skip


def _fields(layer: PageWords) -> dict[str, fx.Extracted]:
    found = fx.identify([layer])
    assert found is not None
    return {f.field_key: f for f in fx.extract(found, [layer])}


# --- identification (AC8.1) -----------------------------------------------------------------


@pytest.mark.parametrize(
    ("key", "form_type", "year"),
    [
        ("feld_w2", "w2", 2025),
        ("iyer_1099div_corrected", "1099_div", 2025),
        ("whitley_cp2000", "cp2000", 2024),
        ("santos_cp14", "cp14", None),
    ],
)
def test_ac_identification_names_the_form_and_its_own_year(
    key: str, form_type: str, year: int | None
) -> None:
    found = fx.identify([_layer(key)])
    assert found is not None and found.form_type == form_type
    if year is not None:
        assert found.tax_year == year


@pytest.mark.parametrize("key", ["calloway_instrument", "front_range_statement"])
def test_ac_a_page_that_is_no_known_form_is_not_identified(key: str) -> None:
    assert fx.identify([_layer(key)]) is None


# --- maps per tax year, unsupported year (AC8.6) -------------------------------------------


def test_ac_each_year_reads_with_its_own_years_map() -> None:
    supported = sorted({m.tax_year for m in fx.load_maps() if m.form_type == "w2"})
    assert len(supported) >= 2
    for year in supported:
        found = fx.identify([_layer("feld_w2", lambda t, y=year: str(y) if t == "2025" else t)])
        assert found is not None and (found.form_type, found.tax_year) == ("w2", year)
        assert str(year) in found.version


def test_ac_an_unsupported_tax_year_yields_manual_entry_not_guessed_values() -> None:
    supported = {m.tax_year for m in fx.load_maps() if m.form_type == "w2"}
    unsupported = next(y for y in range(2019, 2040) if y not in supported)
    layer = _layer("feld_w2", lambda t: str(unsupported) if t == "2025" else t)
    assert fx.identify([layer]) is None  # no map: no field is read, the consumer offers entry
    n = asyncio.run(_extract_version_with([layer], variant="all"))
    assert n == 0


# --- the low-confidence rule (AC8.3) ---------------------------------------------------------


def test_ac_a_value_below_090_is_flagged_and_stored_exactly_as_read() -> None:
    clear = _fields(_layer("feld_w2"))["w2.box1"]
    faint = _fields(_layer("feld_w2", confidence=85.0))["w2.box1"]
    assert not clear.low_confidence and clear.confidence >= fx.LOW_CONFIDENCE
    assert faint.low_confidence and faint.confidence < fx.LOW_CONFIDENCE
    assert faint.value_text == clear.value_text == "268400.00"


def test_ac_an_amount_that_does_not_read_is_kept_as_text_and_flagged() -> None:
    fields = _fields(_layer("feld_w2", lambda t: "268,4OO.00" if t == "268,400.00" else t))
    box1 = fields["w2.box1"]
    assert box1.value_text == "268,4OO.00" and box1.low_confidence


# --- corrected detection (AC8.4) -------------------------------------------------------------


def test_ac_a_corrected_form_is_flagged_and_an_original_is_not() -> None:
    corrected = _fields(_layer("iyer_1099div_corrected"))
    assert corrected["1099_div.corrected"].value_text == "true"
    assert corrected["div.box1b"].value_text == "3310.00"
    original = _fields(_layer("iyer_1099div_corrected", lambda t: "" if t == "CORRECTED" else t))
    assert "1099_div.corrected" not in original


# --- sealed TINs (AC8.5; P-03) ----------------------------------------------------------------


def _all_tax_form_fields() -> Iterator[fx.Extracted]:
    for page in generate():
        layer = _layer(page.key)
        found = fx.identify([layer])
        if found is not None:
            yield from fx.extract(found, [layer])


def test_ac_no_tin_is_ever_a_field_value_or_label() -> None:
    fields = list(_all_tax_form_fields())
    assert fields
    for field in fields:
        assert not TIN.search(field.value_text), field.field_key
        assert not re.search(r"\b(ssn|ein|tin)\b", field.field_key, re.I), field.field_key


def test_ac_a_page_naming_a_tin_is_the_one_read_for_label_masking() -> None:
    assert names_a_tin(w.text for w in _layer("feld_w2").words)
    assert not names_a_tin(w.text for w in _layer("calloway_instrument").words)


# --- statement tables (P-11-T36; CLS-05) ----------------------------------------------------


def test_ac_statement_tables_are_read_only_when_the_firm_covers_statements() -> None:
    assert [v for v in VARIANTS if fx.covers(v, "statements")] == ["all"]
    words = list(ocr.normalise(_blocks("front_range_statement"), **LETTER))
    assert statement_tables.looks_like_statement(words)
    assert not statement_tables.looks_like_statement(
        list(ocr.normalise(_blocks("feld_w2"), **LETTER))
    )
    parsed = statement_tables.statement_from_ocr([(words, 612.0, 792.0)])
    assert all(line.box is not None for line in parsed.lines)


# --- evidence never altered (ADR-004, ADR-110) ------------------------------------------------


@pytest.mark.source_scan  # reads source text: left out under mutmut (DEC-599)
@pytest.mark.parametrize("module", [fx, statement_tables, ocr_step])
def test_ac_extraction_never_updates_or_deletes_and_never_writes_evidence(module: object) -> None:
    source = inspect.getsource(module)  # type: ignore[arg-type]  # a module
    assert not re.search(r"\b(UPDATE|DELETE\s+FROM|TRUNCATE)\b", source)
    for table in re.findall(r"INSERT INTO (\w+)", source):
        assert table in {"extracted_fields", "extracted_tables", "extracted_table_cells"}, table


# --- families off expose nothing (AC8.6; DEC-2308) -------------------------------------------


@pytest.mark.parametrize("variant", VARIANTS)
def test_ac_a_family_the_variant_does_not_cover_writes_nothing(variant: str) -> None:
    for key, family in (("feld_w2", "tax_forms"), ("whitley_cp2000", "notices")):
        written = asyncio.run(_extract_version_with([_layer(key)], variant=variant))
        assert (written > 0) == fx.covers(variant, family), (key, variant)


async def _extract_version_with(layers: list[PageWords], *, variant: str) -> int:
    """`extract_version` with its ports replaced: no database, the given page layers."""
    inserted: list[dict[str, Any]] = []  # Any: untyped JSON or YAML (a test double)

    class Session:
        async def scalar(self, *_a: object, **_k: object) -> int:
            return 0

        async def execute(self, _sql: object, params: dict[str, Any]) -> None:  # Any: test JSON
            inserted.append(params)

    class Tx:
        session = Session()

        def emit(self, _event: object) -> None: ...

        def record(self, *_a: object, **_k: object) -> None: ...

    @asynccontextmanager
    async def session_of(_tenant: object) -> AsyncGenerator[Session]:
        yield Session()

    @asynccontextmanager
    async def uow_of(_tenant: object) -> AsyncGenerator[Tx]:
        yield Tx()

    async def pages(*_a: object, **_k: object) -> list[int]:
        return list(range(len(layers)))

    async def layer(_tenant: object, page: int) -> PageWords:
        return layers[page]

    async def flag(*_a: object) -> str:
        return variant

    saved = (fx.tenant_session, fx.uow, fx.pages_of, fx.read_page_layer, fx.flag_variant)
    fx.tenant_session, fx.uow, fx.pages_of = session_of, uow_of, pages
    fx.read_page_layer, fx.flag_variant = layer, flag
    try:
        written = await fx.extract_version(uuid4(), uuid4())
    finally:
        (fx.tenant_session, fx.uow, fx.pages_of, fx.read_page_layer, fx.flag_variant) = saved
    assert written == len(inserted)
    return written
