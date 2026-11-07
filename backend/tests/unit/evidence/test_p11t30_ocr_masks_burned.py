"""P-11-T30 (TASK-6010; ADR-078): masks are burned into OCR pages, pixel by pixel.

The row's open property: "the no-unmasked-pixel property on OCR pages". Each synthetic scanned
page (`scanned_corpus`) is read by `FakeOcr` from its recorded Textract layer, the detector finds
the identifiers on the OCR words, and `previews.render_masked` burns them. Every pixel inside each
detected box is then the page's background (opaque, RGB: nothing see-through), while the clean
render had ink there. Written outside the implementing session (ADR-078).
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from decimal import Decimal

import pytest
from PIL import Image

from abacus.kernel.ocr import FakeOcr
from abacus.modules.evidence import pii, previews
from abacus_tools.synthetic.scanned_corpus import CorpusPage, generate, recordings

PAGES = [p for p in generate() if p.media_type == "image/png"]
IDENTIFIERS = frozenset({"ssn", "itin", "ein", "tin"})


@dataclass(frozen=True)
class _Word:
    text: str
    x0: float
    top: float
    x1: float
    bottom: float


async def _boxes(page: CorpusPage) -> tuple[list[pii.Box], tuple[int, int]]:
    """The page's identifier boxes from its OCR words, in the image's own pixels."""
    with Image.open(io.BytesIO(page.image)) as image:
        size = image.size
    read = await FakeOcr(recordings(PAGES)).read(
        page.image, width_pt=Decimal(size[0]), height_pt=Decimal(size[1]), api="detect_text"
    )
    words = [_Word(w.text, *(float(v) for v in w.bbox)) for w in read.words]
    found = pii.detect(1, words)
    return [f.box for f in found if f.kind in IDENTIFIERS], size


def _colours(image: Image.Image) -> set[object]:
    found = image.getcolors(maxcolors=1 << 20) or []
    return {colour for _count, colour in found}


def _pixels(png: bytes) -> Image.Image:
    with Image.open(io.BytesIO(png)) as image:
        return image.convert("RGB")


async def test_the_corpus_has_pages_with_identifiers() -> None:
    found = [p.key for p in PAGES if (await _boxes(p))[0]]
    assert set(found) == {"whitley_cp2000", "feld_w2"}  # the faces that carry a taxpayer ID


@pytest.mark.parametrize("page", PAGES, ids=[p.key for p in PAGES])
async def test_no_pixel_inside_a_detected_box_survives_the_burn(page: CorpusPage) -> None:
    boxes, size = await _boxes(page)
    masked = previews.render_masked(page.image, page.media_type, {1: boxes}, {1: size})
    clean = previews.render(page.image, page.media_type)
    assert masked.kind == clean.kind != "none"
    burned, original = _pixels(masked.pages[0].png), _pixels(clean.pages[0].png)
    assert burned.mode == "RGB"  # no alpha: a mask can't be see-through
    if not boxes:  # a face with no identifier is drawn unchanged
        assert burned.tobytes() == original.tobytes()
        return
    fill = previews.background(original)
    scale_x, scale_y = burned.width / size[0], burned.height / size[1]
    for x0, top, x1, bottom in boxes:
        left, upper, right, lower = (
            int(min(x0, x1) * scale_x), int(min(top, bottom) * scale_y),
            int(max(x0, x1) * scale_x), int(max(top, bottom) * scale_y),
        )  # fmt: skip
        inside = burned.crop((left, upper, right + 1, lower + 1))
        assert _colours(inside) == {fill}, f"{page.key}: an unmasked pixel in {left, upper}"
        ink = original.crop((left, upper, right + 1, lower + 1))
        assert _colours(ink) != {fill}, f"{page.key}: the clean render had no ink to mask"
