"""P-11-T25 (DEC-2309): rasterising before OCR, on real files of each kind."""

from __future__ import annotations

import io

import pypdfium2 as pdfium
import pytest
from PIL import Image

from abacus.modules.evidence import ocr_normalise as normalise


def _png(width: int = 20, height: int = 10) -> bytes:
    out = io.BytesIO()
    Image.new("RGB", (width, height), "white").save(out, format="PNG")
    return out.getvalue()


def _gif(frames: int) -> bytes:
    images = [Image.new("RGB", (8, 8), (60 * i, 0, 0)) for i in range(frames)]
    out = io.BytesIO()
    images[0].save(out, format="GIF", save_all=True, append_images=images[1:], duration=10)
    return out.getvalue()


def _pdf(pages: int) -> bytes:
    document = pdfium.PdfDocument.new()
    for _ in range(pages):
        document.new_page(100, 200)
    out = io.BytesIO()
    document.save(out)
    document.close()
    return out.getvalue()


def test_an_image_is_one_upright_page_sized_in_pixels() -> None:
    (page,) = normalise.rasterise(_png(), "image/png", None)
    assert (page.page, page.width_pt, page.height_pt) == (1, 20.0, 10.0)
    assert page.png.startswith(b"\x89PNG")


def test_a_multi_frame_image_stops_at_the_page_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(normalise, "MAX_PAGES", 2)
    assert [p.page for p in normalise.rasterise(_gif(3), "image/gif", None)] == [1, 2]


def test_a_pdf_gives_every_page_or_only_those_named() -> None:
    content = _pdf(3)
    assert [p.page for p in normalise.rasterise(content, normalise.PDF, None)] == [1, 2, 3]
    assert [p.page for p in normalise.rasterise(content, normalise.PDF, [2])] == [2]


def test_a_pdf_stops_at_the_page_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(normalise, "MAX_PAGES", 1)
    assert [p.page for p in normalise.rasterise(_pdf(2), normalise.PDF, None)] == [1]
