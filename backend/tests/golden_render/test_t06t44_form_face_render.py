"""T-06-T44 (TASK-8913; DEC-5915): the form face's PDF through WeasyPrint.

Image-bound like `test_p09t11_trace_pdf_render.py`: `make golden-render` runs this file inside the
backend image (no network). The unit suite (`tests/unit/tax/test_t06t44_form_pages.py`) proves
the bindings, formatting, masking and the content hash; here C11's form-face renderer draws them:
two renders of the same checkpoint are byte-identical (the isolated child included), Item F
reads 17,914,500, the watermark is on every page and the TIN prints only as its mask.
"""

from __future__ import annotations

import io
from datetime import UTC, datetime
from typing import Final

import pdfplumber

from abacus.modules.reporting.api import FaceField, FacePage, render_face, render_face_isolated

AS_OF: Final = datetime(2026, 3, 2, 15, 30, tzinfo=UTC)
HASH: Final = "4" * 64
PAGES: Final = (FacePage("p1", "Form 1065 page 1"), FacePage("p4", "Schedule K, page 4"))
FIELDS: Final = (
    FaceField("p1", "Name of partnership", (0.08, 0.10, 0.6, 0.13), "Ridgeline Partners"),
    FaceField("p1", "D Employer identification number", (0.62, 0.10, 0.92, 0.13), "••-•••0287"),
    FaceField("p1", "F Total assets", (0.62, 0.18, 0.92, 0.21), "17,914,500"),
    FaceField("p4", "2 Net rental real estate income", (0.62, 0.20, 0.92, 0.23), "1,231,600.00"),
)


def _pdf(isolated: bool = False) -> bytes:
    draw = render_face_isolated if isolated else render_face
    return draw("Form 1065 (TY2025)", PAGES, FIELDS, as_of=AS_OF, content_hash=HASH)


def test_two_renders_of_the_same_checkpoint_are_byte_identical() -> None:
    assert _pdf() == _pdf()
    assert _pdf(isolated=True) == _pdf()


def test_a_different_checkpoint_hash_is_a_different_document() -> None:
    other = render_face("Form 1065 (TY2025)", PAGES, FIELDS, as_of=AS_OF, content_hash="5" * 64)
    assert other != _pdf()


def test_item_f_the_watermark_and_the_masked_tin_are_on_the_pages() -> None:
    with pdfplumber.open(io.BytesIO(_pdf())) as pdf:
        texts = [page.extract_text() or "" for page in pdf.pages]
        # The watermark is drawn at -35 degrees, and extract_text orders glyphs by position, so a
        # rotated phrase comes back scattered: read each page's glyphs in drawing order instead.
        drawn = ["".join(str(c["text"]) for c in page.chars) for page in pdf.pages]
    assert len(texts) == 2
    assert "17,914,500" in texts[0]
    mark = "Draft—notforfiling"  # the watermark, whitespace dropped
    assert all(mark in "".join(d.split()) for d in drawn)
    assert "0287" in texts[0] and "1,231,600.00" in texts[1]
