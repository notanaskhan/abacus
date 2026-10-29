"""SPEC-520 AC-30, AC-6, AC-20, AC-9 (P-11-T02; ADR-320): the golden letter renders to the same
PDF and DOCX bytes on every run, three pages long, equal to the recorded goldens, and a URL in the
document is refused.

Image-bound: WeasyPrint needs the pinned Pango, HarfBuzz and fontconfig that only the backend
image carries, so this suite runs inside it (`make golden-render`: two fresh containers with no
network, then this file), never against a developer's system libraries.
"""

from __future__ import annotations

import hashlib
import io
from pathlib import Path

import pdfplumber
import pytest

from abacus.modules.reporting.render.pdf import RenderRefused, dated_head, render_pdf
from abacus_tools.synthetic.scenarios.brightwater_hale import render_letter as letter

from .render_letter import pages, render

HERE = Path(__file__).resolve().parent


def _golden(name: str) -> str:
    path = HERE / name
    assert path.is_file(), f"{name} is not recorded: run make golden-render and commit it"
    return path.read_text(encoding="ascii").split()[0]


def test_ac30_two_runs_give_identical_bytes() -> None:
    first, second = render(), render()
    assert first == second


def test_ac30_the_letter_is_three_pages() -> None:
    pdf, _ = render()
    assert pages(pdf) == 3


def test_ac30_pdf_and_docx_equal_the_recorded_goldens() -> None:
    pdf, docx = render()
    assert hashlib.sha256(pdf).hexdigest() == _golden("letter.pdf.sha256")
    assert hashlib.sha256(docx).hexdigest() == _golden("letter.docx.sha256")


def test_ac6_no_clock_time_in_the_pdf() -> None:
    pdf, _ = render()
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        meta = document.metadata
    assert str(meta["CreationDate"]).startswith("D:20260914142400")
    assert str(meta["ModDate"]).startswith("D:20260914142400")


@pytest.mark.parametrize(
    "url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "file:///etc/passwd",
        "data:image/png;base64,iVBORw0KGgo=",
        "asset:font/not-vendored.woff",
    ],
)
def test_ac9_every_url_but_a_known_asset_is_refused(url: str) -> None:
    html = letter.html(dated_head(letter.TITLE, letter.AS_OF)).replace(
        "</body>", f"<img src='{url}'></body>"
    )
    with pytest.raises(RenderRefused) as refused:
        render_pdf(html, letter.CSS, content_hash=letter.CONTENT_HASH)
    assert refused.value.code == "asset_not_allowed"
