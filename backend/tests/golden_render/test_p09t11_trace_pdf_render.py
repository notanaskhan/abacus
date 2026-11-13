"""P-09-T11 (TASK-7834; DEC-4820): the agent run trace's PDF through WeasyPrint.

Image-bound like `test_a06t29_fs_render.py`: `make golden-render` runs this file inside the backend
image (no network). The unit suite (`tests/unit/agents/test_p09t11_trace_pdf.py`) proves the
blocks, caps and audit with a stand-in renderer; here the composition root's real renderer (the
API registers C11's isolated child) draws them. Two exports of one trace version are
byte-identical, the PDF says what the JSON says, a long timeline continues across pages, and a
character the vendored faces cannot draw prints as "?" instead of refusing.
"""

from __future__ import annotations

import io
import json
from typing import Final

import pdfplumber

from abacus.api import app as composition_root
from abacus.modules.agents import trace_pdf

RUN_ID: Final = "8f0c3a52-0d7e-4c55-9d1b-3b4f2b8f3c11"
DIGEST: Final = "a" * 64


def _body(rows: int, title: str = "Read files") -> bytes:
    return json.dumps(
        {
            "run": {
                "agent": "evidence.screener",
                "agent_label": "Evidence screener",
                "state": "succeeded",
            },
            "projection": "content",
            "runtime": "Accrued Agent runtime",
            "region": "us-east-1",
            "training": "not used for training",
            "attempts": 1,
            "tokens_in": 120,
            "tokens_out": 40,
            "rows": [
                {
                    "seq": i + 1,
                    "at": "2026-09-14T14:24:00Z",
                    "kind": "step",
                    "title": f"{title} {i + 1}",
                    "state": "done",
                    "detail": None,
                    "actor": "Ana Cruz via Agent",
                }
                for i in range(rows)
            ],
            "records_read": [{"source": "evidence", "count": 224}],
            "output_counts": [["proposals", 2]],
        },
        sort_keys=True,
        separators=(",", ":"),
    ).encode()


def _text(pdf: bytes) -> tuple[int, str]:
    with pdfplumber.open(io.BytesIO(pdf)) as doc:
        return len(doc.pages), "\n".join(page.extract_text() or "" for page in doc.pages)


def test_the_api_registers_the_real_renderer() -> None:
    assert composition_root.create_app is not None  # importing the root registers it
    pdf = trace_pdf.render_trace_pdf(_body(2), RUN_ID, DIGEST)
    assert pdf.startswith(b"%PDF-")


def test_two_exports_of_one_trace_version_are_byte_identical() -> None:
    body = _body(3)
    assert trace_pdf.render_trace_pdf(body, RUN_ID, DIGEST) == trace_pdf.render_trace_pdf(
        body, RUN_ID, DIGEST
    )


def test_the_pdf_says_what_the_json_says() -> None:
    _pages, text = _text(trace_pdf.render_trace_pdf(_body(2), RUN_ID, DIGEST))
    for words in ("Agent run trace", RUN_ID, "Evidence screener", "Read files 1", "Read files 2"):
        assert words in text


def test_a_long_timeline_continues_across_tables_and_pages() -> None:
    rows = trace_pdf.TABLE_ROWS + 120
    pages, text = _text(trace_pdf.render_trace_pdf(_body(rows), RUN_ID, DIGEST))
    assert pages > 1
    assert f"Read files {rows}" in text


def test_a_character_the_faces_cannot_draw_prints_as_a_question_mark() -> None:
    pages, text = _text(trace_pdf.render_trace_pdf(_body(1, "Matched \U0001f9fe"), RUN_ID, DIGEST))
    assert pages >= 1
    assert "Matched ? 1" in text
