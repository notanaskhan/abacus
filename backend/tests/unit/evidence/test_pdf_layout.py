"""P-03-T15 security review (H1, H2, L2; DEC-369): the word layer and the masked renderer agree on
what a page shows and where, or the page is unscannable.

- H1: a CropBox, a MediaBox off the origin, and /Rotate 90, 180 and 270 with a CropBox: the
  detected value is masked with zero dark pixels left on the page (its only text).
- H2: a FreeText annotation's value is flattened into the content, read and masked; a page that
  is mostly an image, or draws outlined text, is unscannable (no text layer).
- L2: a page past the word cap is unscannable, never part-scanned.
"""

from __future__ import annotations

import io
import re

import pytest
from PIL import Image

from abacus.kernel.tin_patterns import has_tin, scrub_tins
from abacus.modules.evidence import words as words_module
from abacus.modules.evidence.masking import MaskRegion, masked_words
from abacus.modules.evidence.pdf_layout import reconciled
from abacus.modules.evidence.pii import detect, detect_on_page
from abacus.modules.evidence.previews import PDF, pixel_box, render_masked
from abacus.modules.evidence.words import extract_words
from abacus_tools.synthetic.documents import w2_pdf

ITIN = b"900-70-1234"  # a synthetic 9xx ITIN, valid by the IRS group rules
HELVETICA = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"


def _pdf(page_extra: bytes, content: bytes, extra_objects: tuple[bytes, ...] = ()) -> bytes:
    """One page: `page_extra` holds its boxes, rotation and annotations; objects 4 and 5 are its
    content and font; `extra_objects` are 6 and on."""
    box = b"" if b"MediaBox" in page_extra else b"/MediaBox [0 0 612 792] "
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R "
        + box
        + page_extra
        + b" /Resources << /Font << /F1 5 0 R >> /XObject << /Im1 6 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        HELVETICA,
        *extra_objects,
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets: list[int] = []
    for n, body in enumerate(objects, 1):
        offsets.append(out.tell())
        out.write(b"%d 0 obj\n" % n + body + b"\nendobj\n")
    start = out.tell()
    out.write(b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1))
    for offset in offsets:
        out.write(b"%010d 00000 n \n" % offset)
    out.write(
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(objects) + 1, start)
    )
    return out.getvalue()


def _dark(png: bytes) -> int:
    image = Image.open(io.BytesIO(png)).convert("L")
    found = image.getcolors(maxcolors=image.width * image.height) or []
    return sum(count for count, value in found if int(value) < 128)  # pyright: ignore[reportArgumentType] -- an L image's colours are ints


def _masked_dark(content: bytes) -> tuple[int, list[str]]:
    """The pipeline's own steps: word layer, detector, masked render; dark pixels left."""
    layer = extract_words(content, PDF)
    page = layer.pages[0]
    masks = {1: [f.box for f in detect(1, page.words)]}
    rendered = render_masked(content, PDF, masks, {1: (page.width, page.height)})
    return _dark(rendered.pages[0].png), [w.text for w in page.words]


GEOMETRIES = {
    "plain": b"",
    "cropbox": b"/CropBox [50 100 562 742]",
    "mediabox_offset": b"/MediaBox [40 60 652 852]",
    "mediabox_offset_and_cropbox": b"/MediaBox [40 60 652 852] /CropBox [90 160 600 800]",
    "rotate_90": b"/Rotate 90",
    "rotate_180": b"/Rotate 180",
    "rotate_270": b"/Rotate 270",
    "rotate_90_cropbox": b"/Rotate 90 /CropBox [50 100 562 742]",
    "rotate_180_cropbox": b"/Rotate 180 /CropBox [50 100 562 742]",
    "rotate_270_cropbox": b"/Rotate 270 /CropBox [50 100 562 742]",
    "rotate_90_mediabox_offset": b"/Rotate 90 /MediaBox [40 60 652 852]",
}


@pytest.mark.parametrize("extra", GEOMETRIES.values(), ids=list(GEOMETRIES))
def test_h1_the_mask_covers_the_value_whatever_the_page_geometry(extra: bytes) -> None:
    content = _pdf(extra, b"BT /F1 24 Tf 100 600 Td (" + ITIN + b") Tj ET")
    dark, words = _masked_dark(content)
    assert words == [ITIN.decode()]
    assert dark == 0


def test_h2_a_freetext_annotation_is_read_and_masked() -> None:
    appearance = b"BT /F1 24 Tf 2 6 Td (" + ITIN + b") Tj ET"
    content = _pdf(
        b"/Annots [7 0 R]",
        b"BT /F1 12 Tf 72 720 Td (Form W-9 taxpayer identification number) Tj ET",
        (
            b"<< /Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceGray "
            b"/BitsPerComponent 8 /Length 1 >>\nstream\n\xff\nendstream",
            b"<< /Type /Annot /Subtype /FreeText /Contents (" + ITIN + b") /DA (/F1 24 Tf) "
            b"/Rect [100 600 300 640] /P 3 0 R /AP << /N 8 0 R >> >>",
            b"<< /Type /XObject /Subtype /Form /BBox [0 0 200 40] "
            b"/Resources << /Font << /F1 5 0 R >> >> /Length %d >>\nstream\n"
            % len(appearance)
            + appearance
            + b"\nendstream",
        ),
    )
    dark, words = _masked_dark(content)
    assert ITIN.decode() in words  # flattened into the content, so the layer reads it
    lines = extract_words(content, PDF).pages[0].words
    label = [w for w in lines if w.text != ITIN.decode()]
    assert label  # the printed label is still there
    # Only the label's text is left dark: the annotation's value is burned out.
    label_only, _ = _masked_dark(
        _pdf(b"", b"BT /F1 12 Tf 72 720 Td (Form W-9 taxpayer identification number) Tj ET")
    )
    assert dark == label_only


IMAGE = (
    b"<< /Type /XObject /Subtype /Image /Width 2 /Height 2 /ColorSpace /DeviceGray "
    b"/BitsPerComponent 8 /Length 4 >>\nstream\n\x00\xff\xff\x00\nendstream"
)


def test_n1_an_image_page_keeps_its_text_masking_and_is_marked_for_its_images() -> None:
    """Review N1 (replacing H2's "mostly an image" rule): image pixels can't be read before OCR,
    so a page with an image big enough to hold a number is marked (`images`), whatever its
    share of the page, while its words are still read and masked; a speck stays unmarked."""
    for size in (b"400 0 0 500 50 100", b"250 0 0 155 100 300", b"60 0 0 40 100 300"):
        page = extract_words(
            _pdf(
                b"",
                b"q " + size + b" cm /Im1 Do Q BT /F1 12 Tf 72 720 Td (TIN 900-70-1234) Tj ET",
                (IMAGE,),
            ),
            PDF,
        ).pages[0]
        assert page.images, size
        assert [w.text for w in page.words] == ["TIN", "900-70-1234"]
        assert [f.kind for f in detect(1, page.words)] == ["itin"]
    speck = extract_words(
        _pdf(b"", b"q 12 0 0 12 50 700 cm /Im1 Do Q BT /F1 12 Tf 72 600 Td (Fax) Tj ET", (IMAGE,)),
        PDF,
    ).pages[0]
    assert not speck.images and [w.text for w in speck.words] == ["Fax"]


def test_h2_text_drawn_as_outlines_makes_the_page_unscannable() -> None:
    curves = b" ".join(
        b"%d 300 m %d 320 %d 320 %d 300 c f" % (x, x + 3, x + 6, x + 9) for x in range(60, 560, 10)
    )
    content = _pdf(b"", b"BT /F1 12 Tf 72 720 Td (Recipient) Tj ET " + curves, (IMAGE,))
    assert extract_words(content, PDF).pages[0].words == ()


def test_l2_a_page_past_the_word_cap_is_unscannable(monkeypatch: pytest.MonkeyPatch) -> None:
    content = _pdf(b"", b"BT /F1 12 Tf 72 720 Td (one two three four) Tj ET", (IMAGE,))
    assert len(extract_words(content, PDF).pages[0].words) == 4
    monkeypatch.setattr(words_module, "MAX_PAGE_WORDS", 3)
    assert extract_words(content, PDF).pages[0].words == ()


def test_reconciled_needs_both_parsers_to_see_the_same_text() -> None:
    word = (100.0, 100.0, 200.0, 120.0)
    assert reconciled([word], [(101.0, 101.0, 199.0, 119.0)])
    assert not reconciled([word], [(101.0, 101.0, 199.0, 119.0), (300.0, 300.0, 400.0, 320.0)])
    assert not reconciled([word], [(400.0, 400.0, 500.0, 420.0)])
    assert not reconciled([word], [])
    assert reconciled([], [])


@pytest.mark.parametrize("rotation", [90, 180, 270])
def test_h1_a_rotated_cropped_w2_is_detected_and_burned(rotation: int) -> None:
    """Label-anchored values on a rotated page: detected in the content's upright frame
    (`detect_on_page`), burned in render space; each region's pixels are one colour."""
    content = w2_pdf().replace(
        b"/MediaBox [0 0 612 792]",
        b"/MediaBox [0 0 612 792] /Rotate %d /CropBox [20 30 600 780]" % rotation,
    )
    page = extract_words(content, PDF).pages[0]
    found = detect_on_page(1, page.words, page.rotation, page.width, page.height)
    assert sorted((f.kind, f.last4) for f in found) == [("ein", "0287"), ("ssn", "6081")]
    rendered = render_masked(
        content, PDF, {1: [f.box for f in found]}, {1: (page.width, page.height)}
    )
    image = Image.open(io.BytesIO(rendered.pages[0].png)).convert("RGB")
    scale_x, scale_y = image.width / page.width, image.height / page.height
    for f in found:
        left, upper, right, lower = (
            int(v) for v in pixel_box(f.box, scale_x, scale_y, image.width, image.height)
        )
        crop = image.crop((left, upper, right + 1, lower + 1))
        assert len(crop.getcolors(maxcolors=crop.width * crop.height) or []) == 1


# --- Regression check (review round 2): ordinary forms stay scannable ---------------------------


def _scannable(content: bytes) -> bool:
    return bool(extract_words(content, PDF).pages[0].words)


def test_sideways_margin_text_and_a_diagonal_watermark_stay_scannable() -> None:
    body = b"BT /F1 12 Tf 72 720 Td (Recipient name) Tj ET "
    margin = b"BT /F1 7 Tf 0 1 -1 0 30 200 Tm (Form W-9 (Rev. 10-2018) Cat. No. 10231X) Tj ET "
    watermark = b"BT /F1 60 Tf 0.707 0.707 -0.707 0.707 150 300 Tm (DRAFT) Tj ET"
    assert _scannable(_pdf(b"", body + margin + watermark, (IMAGE,)))


def test_a_sideways_tin_makes_the_page_unscannable() -> None:
    body = b"BT /F1 12 Tf 72 720 Td (Recipient name) Tj ET "
    sideways = b"BT /F1 12 Tf 0 1 -1 0 300 200 Tm (" + ITIN + b") Tj ET"
    assert not _scannable(_pdf(b"", body + sideways, (IMAGE,)))
    spaced = b"BT /F1 12 Tf 0 1 -1 0 300 200 Tm (9 0 0 7 0 1 2 3 4) Tj ET"
    assert not _scannable(_pdf(b"", body + spaced, (IMAGE,)))


def _rounded_box(x: int, y: int, w: int, h: int) -> bytes:
    r = 6
    return (
        b"%d %d m %d %d l %d %d %d %d %d %d c %d %d l %d %d %d %d %d %d c %d %d l "
        b"%d %d %d %d %d %d c %d %d l %d %d %d %d %d %d c S "
        % (
            x + r, y, x + w - r, y, x + w, y, x + w, y, x + w, y + r,
            x + w, y + h - r, x + w, y + h, x + w, y + h, x + w - r, y + h,
            x + r, y + h, x, y + h, x, y + h, x, y + h - r,
            x, y + r, x, y, x, y, x + r, y,
        )
    )  # fmt: skip


def test_rounded_boxes_and_a_vector_logo_stay_scannable() -> None:
    boxes = b"".join(
        _rounded_box(60 + 120 * (i % 4), 400 + 70 * (i // 4), 100, 50) for i in range(8)
    )
    logo = b"".join(
        b"%d %d m %d %d %d %d %d %d c f " % (500 + i, 700, 505 + i, 730, 510 + i, 730, 520, 700)
        for i in range(0, 30, 2)
    )  # fifteen overlapping curved shapes in a 30 pt mark
    body = b"BT /F1 12 Tf 72 720 Td (Bank statement) Tj ET "
    assert _scannable(_pdf(b"", body + boxes + logo, (IMAGE,)))


def test_one_path_of_outlined_glyphs_makes_the_page_unscannable() -> None:
    glyphs = (
        b"".join(
            b"%d 300 m %d 316 %d 316 %d 300 c %d 284 %d 284 %d 300 c "
            % (x, x + 2, x + 8, x + 10, x + 8, x + 2, x)
            for x in range(100, 280, 14)
        )
        + b"f"
    )  # thirteen digit-sized loops in one path: 26 Bézier segments, 180 by 32 pt
    body = b"BT /F1 12 Tf 72 720 Td (Recipient) Tj ET "
    assert not _scannable(_pdf(b"", body + glyphs, (IMAGE,)))


def test_every_synthetic_document_stays_scannable() -> None:
    import inspect

    from abacus_tools.synthetic import documents

    makers = [
        fn
        for name, fn in inspect.getmembers(documents, inspect.isfunction)
        if name.endswith("_pdf")
        and name not in ("scanned_pdf", "encrypted_pdf", "positioned_pdf")
        and all(p.default is not p.empty for p in inspect.signature(fn).parameters.values())
    ]
    assert len(makers) >= 15
    for make in makers:
        layer = extract_words(make(), PDF)
        assert layer.status == "extracted", make.__name__
        for page in layer.pages:
            assert page.words and not page.images, (make.__name__, page.page)


# --- Review N2: a TIN drawn in pieces -------------------------------------------------------


def _material(content: bytes) -> str:
    """Agent material for the page, as `masked_text` builds it (masked words, then the scrub)."""
    page = extract_words(content, PDF).pages[0]
    found = detect_on_page(1, page.words, page.rotation, page.width, page.height)
    regions = [MaskRegion(1, f.box, f.kind, f.last4) for f in found]
    return scrub_tins(" ".join(w.text for w in masked_words(page.words, regions, 1)))


LABEL = b"BT /F1 9 Tf 380 640 Td (Social security number) Tj ET\n"
COMB = b"".join(
    b"BT /F1 12 Tf %d 620 Td (%s) Tj ET\n" % (380 + i * 18, bytes([c]))
    for i, c in enumerate(ITIN.replace(b"-", b""))
)
PIECES = {
    "comb": (LABEL + COMB, LABEL),
    "split_on_one_line": (
        b"BT /F1 18 Tf 100 600 Td (TIN 900-70-) Tj 110 0 Td (1234) Tj ET",
        b"BT /F1 18 Tf 100 600 Td (TIN) Tj ET",
    ),
    "wrapped": (
        b"BT /F1 18 Tf 100 600 Td (Taxpayer identification number 900-70-) Tj "
        b"0 -22 Td (1234) Tj ET",
        b"BT /F1 18 Tf 100 600 Td (Taxpayer identification number) Tj ET",
    ),
    "spaced": (
        b"BT /F1 18 Tf 100 600 Td (TIN 9 0 0 7 0 1 2 3 4) Tj ET",
        b"BT /F1 18 Tf 100 600 Td (TIN) Tj ET",
    ),
}


@pytest.mark.parametrize("name", list(PIECES))
def test_n2_a_tin_drawn_in_pieces_is_masked_and_out_of_agent_material(name: str) -> None:
    content, label_only = PIECES[name]
    dark, _ = _masked_dark(_pdf(b"", content, (IMAGE,)))
    baseline, _ = _masked_dark(_pdf(b"", label_only, (IMAGE,)))
    assert dark == baseline  # only the label's pixels are left
    text = _material(_pdf(b"", content, (IMAGE,)))
    assert not has_tin(text) and "1234" in text  # the token's last four, never the digits
    assert not re.search(r"9\D?0\D?0\D?7\D?0", text)
