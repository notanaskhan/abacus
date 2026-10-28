"""SPEC-029 AC-12 (TASK-056): previews are made on the server: PDF pages and images as fresh
PNGs (metadata dropped, bombs refused), spreadsheets as tables; anything else is `none`."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from abacus.modules.evidence import previews
from abacus.modules.evidence.previews import (
    JPEG,
    PAGE_WIDTH,
    PDF,
    PNG,
    XLSX,
    render,
    render_isolated,
)
from abacus_tools.synthetic.documents import bank_statement_pdf, encrypted_pdf, scanned_pdf


def _jpeg_with_metadata() -> bytes:
    image = Image.new("RGB", (3000, 1500), (200, 10, 10))
    exif = Image.Exif()
    exif[0x010E] = "secret description"  # ImageDescription
    out = io.BytesIO()
    image.save(out, format="JPEG", exif=exif)
    return out.getvalue()


def test_ac12_a_pdf_becomes_page_images_at_the_preview_width() -> None:
    found = render(bank_statement_pdf(), PDF)
    assert (found.kind, len(found.pages)) == ("pages", 1)
    page = found.pages[0]
    assert page.width == PAGE_WIDTH
    assert page.png[:8] == b"\x89PNG\r\n\x1a\n"


def test_ac12_a_scanned_pdf_still_has_page_images() -> None:
    found = render(scanned_pdf(pages=3), PDF)
    assert (found.kind, len(found.pages)) == ("pages", 3)


def test_ac12_pages_past_the_limit_are_left_out_and_say_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(previews, "MAX_PAGES", 2)
    found = render(scanned_pdf(pages=3), PDF)
    assert (len(found.pages), found.truncated) == (2, True)


def test_ac12_a_password_protected_pdf_has_no_preview() -> None:
    assert (render(encrypted_pdf(), PDF).kind, render(encrypted_pdf(), PDF).reason) == (
        "none",
        "encrypted",
    )


def test_ac12_a_damaged_pdf_has_no_preview_and_is_not_an_error() -> None:
    found = render(b"%PDF-1.4\nnot a pdf", PDF)
    assert (found.kind, found.reason) == ("none", "damaged")


def test_ac12_an_image_is_re_encoded_smaller_without_its_metadata() -> None:
    found = render(_jpeg_with_metadata(), JPEG)
    assert found.kind == "image"
    page = found.pages[0]
    assert max(page.width, page.height) <= previews.MAX_SIDE
    with Image.open(io.BytesIO(page.png)) as again:
        assert again.format == "PNG"
        assert not again.getexif()
    assert b"secret description" not in page.png


def test_ac12_a_decompression_bomb_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(previews, "MAX_PIXELS", 1000)
    # `render` writes the limit into Pillow's global; undo that too, or every later image this
    # process opens is refused as a bomb (mutmut runs tests in its own order).
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", Image.MAX_IMAGE_PIXELS)
    image = Image.new("RGB", (100, 100))
    out = io.BytesIO()
    image.save(out, format="PNG")
    found = render(out.getvalue(), PNG)
    assert (found.kind, found.reason) == ("none", "too_large")


def test_ac12_spreadsheets_are_tables_and_word_documents_have_no_preview() -> None:
    assert render(b"PK", XLSX).kind == "table"
    found = render(
        b"PK", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    assert (found.kind, found.reason) == ("none", "not_previewable")


def test_ac12_isolated_rendering_equals_in_process_rendering() -> None:
    content = bank_statement_pdf(layout="c")
    assert render_isolated(content, PDF) == render(content, PDF)
