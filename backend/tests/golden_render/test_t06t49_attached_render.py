"""T-06-T49 (TASK-9017; DEC-6023): a preview with attached forms draws only the pages that have a
template. Image-bound (`make golden-render` runs it inside the backend image): the face's two
pages and Form 8825's page are drawn, the Form 4562 placeholder is not, so the draft PDF has
three pages and every one carries the watermark."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from uuid import UUID

import pdfplumber

from abacus.modules.tax import form_pages_service as fp

AS_OF = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
FACE, RENTAL = UUID(int=1), UUID(int=2)


def _field(page: str, label: str, value: str) -> fp.Field:
    return fp.Field(f"{page}_x", page, label, (0.06, 0.08, 0.66, 0.10), "text", "return_fact",
                    "entity.name", value)  # fmt: skip


def test_t06t49_the_draft_draws_only_pages_with_a_template() -> None:
    found = fp.Preview(
        UUID(int=10), UUID(int=11), UUID(int=12), AS_OF, FACE, "Form 1065 (TY2025)",
        (("p1", "Form 1065 page 1"), ("p4", "Schedule K, page 4"),
         ("f8825_p1", "Form 8825"), ("f4562_p1", "Form 4562")),
        (_field("p1", "Name of partnership", "Ridgeline Property Partners, LP"),
         _field("f8825_p1", "Name of partnership", "Ridgeline Property Partners, LP")),
        (("f8825_p1", RENTAL), ("f4562_p1", None)),
    )  # fmt: skip
    pdf_bytes = fp.render(found)
    assert pdf_bytes == fp.render(found)
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        assert len(pdf.pages) == 3
        assert all("Draft" in (p.extract_text() or "") for p in pdf.pages)
