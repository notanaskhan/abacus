"""Q-03-T030: fuzz the import parsers; only declared errors may escape (ADR-052, ADR-110).

Five TB and five GL ledger formats, the XLSX request-list importer and PDF extraction (in-process
and in its child). Inputs are synthetic: structure-aware rows built from each format's own header
labels, workbooks written by openpyxl, mutated PDFs and raw bytes. `test_regressions` replays every
minimised crash committed under `regressions/<target>/` (docs/ops/fuzzing.md).
"""

from __future__ import annotations

import contextlib
import csv
import dataclasses
import io
import os
import tempfile
from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Final, cast

import openpyxl
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from abacus.modules.connections.gl_formats import GL_FORMATS
from abacus.modules.connections.gl_parse import parse_gl_to_file
from abacus.modules.connections.import_formats import FORMATS
from abacus.modules.connections.import_parse import parse_export
from abacus.modules.evidence.extraction import PDF, extract, extract_isolated
from abacus.modules.ledger.api import NormaliseError
from abacus.modules.requests.workbook import RequestListInvalid, preview

# --- the targets and the only outcomes each may have: return, or raise the declared error.
# Anything else is a crash: a SEV3 ticket and a minimised case under `regressions/`.

PERIOD_START: Final = date(2026, 1, 1)
PERIOD_END: Final = date(2026, 12, 31)


def tb(format_id: str) -> Callable[[bytes], None]:
    def run(content: bytes) -> None:
        with contextlib.suppress(NormaliseError):
            parse_export(content, format_id, PERIOD_START, PERIOD_END)

    return run


def gl(format_id: str) -> Callable[[bytes], None]:
    def run(content: bytes) -> None:
        with tempfile.TemporaryDirectory() as tmp, contextlib.suppress(NormaliseError):
            parse_gl_to_file(
                content, format_id, PERIOD_START, PERIOD_END, str(Path(tmp) / "gl.csv")
            )

    return run


def request_list(content: bytes) -> None:
    with contextlib.suppress(RequestListInvalid):
        preview(content)


def pdf(content: bytes) -> None:
    extract(content, PDF)  # never raises: a damaged file is a result, not an exception


def pdf_isolated(content: bytes) -> None:
    result = extract_isolated(content, PDF)
    assert result.reason != "crashed", "the extraction child died or ran out of its limits"


TARGETS: Final[dict[str, Callable[[bytes], None]]] = {
    **{f"tb.{f}": tb(f) for f in FORMATS},
    **{f"gl.{f}": gl(f) for f in GL_FORMATS},
    "requests.xlsx": request_list,
    "evidence.pdf": pdf,
    "evidence.pdf_isolated": pdf_isolated,
}


REGRESSIONS: Final = Path(__file__).parent / "regressions"
# A one-page PDF with a text stream: the mutation seed (written here, never downloaded).
SEED_PDF: Final = (
    b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]/Contents 4 0 R"
    b"/Resources<</Font<</F1 5 0 R>>>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\nBT /F1 12 Tf 72 720 Td (Cash 1000.00) Tj ET\nendstream endobj\n"
    b"5 0 obj<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>endobj\n"
    b"trailer<</Root 1 0 R>>\n%%EOF\n"
)
# The isolated child spawns a process per example: a tenth of each profile's budget (conftest.py).
ISOLATED_EXAMPLES: Final = 2_000 if os.environ.get("ABACUS_FUZZ_PROFILE") == "nightly" else 4


def _labels(fmt: object) -> list[str]:
    found: list[str] = []
    for field in dataclasses.fields(fmt):  # type: ignore[arg-type]  # formats are dataclasses
        value = getattr(fmt, field.name)
        if field.name in ("id", "system", "system_key", "file_type"):
            continue
        if isinstance(value, str) and value:
            found.append(value)
        elif isinstance(value, tuple):
            found.extend(v for v in cast(tuple[object, ...], value) if isinstance(v, str) and v)
    return found or ["Account"]


_TEXT: Final = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc")), max_size=30)
_CELL: Final = st.one_of(
    st.none(),
    _TEXT,
    st.integers(-(10**12), 10**12),
    st.floats(allow_nan=True, allow_infinity=True),
    st.decimals(
        allow_nan=False, allow_infinity=False, places=2, min_value=-(10**9), max_value=10**9
    ),
    st.dates(min_value=date(1900, 1, 1), max_value=date(2100, 12, 31)),
    st.datetimes(min_value=datetime(1900, 1, 1), max_value=datetime(2100, 12, 31)),
)


@st.composite
def _rows(draw: st.DrawFn, labels: list[str]) -> list[list[object]]:
    width = draw(st.integers(1, 8))
    pool: st.SearchStrategy[object] = st.one_of(st.sampled_from(labels), _CELL)
    header: list[object] = draw(st.lists(pool, min_size=width, max_size=width))
    body: list[list[object]] = draw(st.lists(st.lists(pool, max_size=width + 2), max_size=25))
    preamble: list[list[object]] = draw(st.lists(st.lists(_CELL, max_size=3), max_size=4))
    return [*preamble, header, *body]


def _csv(rows: list[list[object]]) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    for row in rows:
        writer.writerow("" if cell is None else str(cell) for cell in row)
    return buffer.getvalue().encode("utf-8")


def _xlsx(rows: list[list[object]]) -> bytes:
    book = openpyxl.Workbook()
    sheet = book.active
    assert sheet is not None
    for row in rows:
        sheet.append([_xlsx_cell(cell) for cell in row])
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


def _xlsx_cell(cell: object) -> object:
    if isinstance(cell, Decimal):
        return float(cell)
    if isinstance(cell, float) and (cell != cell or cell in (float("inf"), float("-inf"))):
        return str(cell)
    return cell


@st.composite
def _ledger_file(draw: st.DrawFn, file_type: str, labels: list[str]) -> bytes:
    if draw(st.integers(0, 9)) == 0:
        return draw(st.binary(max_size=4096))
    rows = draw(_rows(labels))
    return _xlsx(rows) if file_type == "xlsx" else _csv(rows)


@st.composite
def _mutated(draw: st.DrawFn, seed: bytes) -> bytes:
    data = bytearray(seed)
    for _ in range(draw(st.integers(0, 12))):
        at = draw(st.integers(0, len(data)))
        match draw(st.sampled_from(("flip", "insert", "delete", "truncate"))):
            case "flip" if data:
                data[min(at, len(data) - 1)] = draw(st.integers(0, 255))
            case "insert":
                data[at:at] = draw(st.binary(min_size=1, max_size=64))
            case "delete":
                del data[at : at + draw(st.integers(1, 64))]
            case "truncate":
                del data[at:]
            case _:
                pass
    return bytes(data)


@pytest.mark.parametrize("format_id", sorted(FORMATS))
@given(data=st.data())
def test_tb_parser_raises_only_normalise_error(format_id: str, data: st.DataObject) -> None:
    fmt = FORMATS[format_id]
    TARGETS[f"tb.{format_id}"](data.draw(_ledger_file(fmt.file_type, _labels(fmt))))


@pytest.mark.parametrize("format_id", sorted(GL_FORMATS))
@given(data=st.data())
def test_gl_parser_raises_only_normalise_error(format_id: str, data: st.DataObject) -> None:
    fmt = GL_FORMATS[format_id]
    TARGETS[f"gl.{format_id}"](data.draw(_ledger_file(fmt.file_type, _labels(fmt))))


@given(data=st.data())
def test_request_list_importer_raises_only_request_list_invalid(data: st.DataObject) -> None:
    labels = ["Area", "Request", "Description", "Due", "Owner", "Sheet"]
    content = data.draw(
        st.one_of(_rows(labels).map(_xlsx), st.binary(max_size=4096), st.just(b"PK\x03\x04"))
    )
    TARGETS["requests.xlsx"](content)


@given(content=st.one_of(_mutated(SEED_PDF), st.binary(max_size=4096)))
def test_pdf_extraction_never_raises(content: bytes) -> None:
    TARGETS["evidence.pdf"](content)


@settings(max_examples=ISOLATED_EXAMPLES)
@given(content=_mutated(SEED_PDF))
def test_pdf_extraction_child_never_crashes(content: bytes) -> None:
    TARGETS["evidence.pdf_isolated"](content)


def test_regressions() -> None:
    """Every committed minimised crash still parses to a declared outcome."""
    cases = sorted(REGRESSIONS.glob("*/*.bin"))
    assert cases, "the seed cases are committed with the suite"
    for case in cases:
        target = case.parent.name
        assert target in TARGETS, f"{case}: unknown target {target}"
        TARGETS[target](case.read_bytes())
