"""P-03-T15 (SPEC-322 AC-24; P-03 §4.4): masked renditions, by pixel inspection.

Every pixel inside each detected region (padded and rounded outward) is one opaque colour, the
page's background; the same box in the unmasked render has the text's pixels, so the test would
fail if nothing were burned. Pages are RGB with no alpha, so nothing painted can be see-through.
"""

from __future__ import annotations

import io
from typing import cast

from PIL import Image

from abacus.modules.evidence.pii import detect
from abacus.modules.evidence.previews import (
    PDF,
    PNG,
    Box,
    background,
    pixel_box,
    render,
    render_masked,
    render_masked_isolated,
)
from abacus.modules.evidence.words import extract_words
from abacus_tools.synthetic.documents import pii_corpus, w2_pdf


def _image(png: bytes) -> Image.Image:
    return Image.open(io.BytesIO(png))


def _regions(content: bytes) -> tuple[dict[int, list[Box]], dict[int, tuple[float, float]]]:
    layer = extract_words(content, PDF)
    masks: dict[int, list[Box]] = {}
    sizes: dict[int, tuple[float, float]] = {}
    for page in layer.pages:
        sizes[page.page] = (page.width, page.height)
        masks[page.page] = [f.box for f in detect(page.page, page.words)]
    return masks, sizes


def _colours(image: Image.Image, box: Box) -> set[tuple[int, ...]]:
    left, upper, right, lower = (int(v) for v in box)
    crop = image.convert("RGB").crop((left, upper, right + 1, lower + 1))
    found = crop.getcolors(maxcolors=crop.width * crop.height) or []
    return {tuple(cast(tuple[int, ...], colour)) for _count, colour in found}


def _scaled(image: Image.Image, box: Box, size: tuple[float, float]) -> Box:
    return pixel_box(box, image.width / size[0], image.height / size[1], image.width, image.height)


def test_ac24_no_pixel_inside_a_detected_region_survives() -> None:
    content = w2_pdf()
    masks, sizes = _regions(content)
    assert len(masks[1]) == 2  # the SSN and the EIN
    masked = render_masked(content, PDF, masks, sizes)
    clear = render(content, PDF)
    assert masked.kind == "pages" and len(masked.pages) == 1
    page = _image(masked.pages[0].png)
    assert page.mode == "RGB"  # no alpha channel
    fill = background(page)
    unmasked = _image(clear.pages[0].png)
    for box in masks[1]:
        pixels = _scaled(page, box, sizes[1])
        assert _colours(page, pixels) == {fill}, box
        assert len(_colours(unmasked, pixels)) > 1  # the text was there before
    # Outside the regions the page is untouched: the wages figure still prints.
    wages = next(w for w in extract_words(content, PDF).pages[0].words if w.text == "84,250.00")
    outside = _scaled(page, (wages.x0, wages.top, wages.x1, wages.bottom), sizes[1])
    assert len(_colours(page, outside)) > 1


def test_ac24_the_whole_corpus_is_burned_in_the_isolated_child() -> None:
    for doc in pii_corpus():
        masks, sizes = _regions(doc.content)
        assert sum(len(b) for b in masks.values()) == len(doc.expected), doc.name
        found = render_masked_isolated(doc.content, PDF, masks, sizes)
        assert found.kind == "pages", doc.name
        for n, rendered in enumerate(found.pages, start=1):
            page = _image(rendered.png)
            fill = background(page)
            for box in masks.get(n, []):
                assert _colours(page, _scaled(page, box, sizes[n])) == {fill}, doc.name


def test_ac24_an_image_with_alpha_is_burned_opaque() -> None:
    picture = Image.new("RGBA", (400, 200), (255, 255, 255, 0))
    for x in range(100, 200):
        for y in range(50, 80):
            picture.putpixel((x, y), (0, 0, 0, 255))
    out = io.BytesIO()
    picture.save(out, format="PNG")
    box: Box = (100.0, 50.0, 200.0, 80.0)
    found = render_masked(out.getvalue(), PNG, {1: [box]}, {})
    page = _image(found.pages[0].png)
    assert page.mode == "RGB"
    assert len(_colours(page, pixel_box(box, 1.0, 1.0, page.width, page.height))) == 1


def test_a_page_without_regions_is_rendered_as_is_and_tables_render_nothing() -> None:
    content = w2_pdf()
    found = render_masked(content, PDF, {}, {})
    assert found.kind == "pages" and _image(found.pages[0].png).mode == "RGB"
    assert render_masked(b"a,b\n", "text/csv", {}, {}).kind == "table"
    assert render_masked(b"x", "application/zip", {}, {}).reason == "not_previewable"


def test_a_box_past_the_page_edge_is_clamped() -> None:
    assert pixel_box((-5.0, -5.0, 9999.0, 9999.0), 1.0, 1.0, 100, 50) == (0.0, 0.0, 99.0, 49.0)
