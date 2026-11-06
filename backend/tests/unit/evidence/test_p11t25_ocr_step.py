"""P-11-T25 (TASK-3310; DEC-2309): OCR's page images and words, from the row and AC7.

"A scanned W-2 at a flagged firm gets OCR words, a masked box a and a page offshore members can
open, with the flag off the page stays not_scannable, and the version's bytes and fingerprint never
change." The pipeline's database half runs in the integration pass; here the pure rules hold.
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

from PIL import Image

from abacus.kernel.db import TenantContext
from abacus.kernel.ocr import OcrPage, OcrWord
from abacus.modules.evidence.ocr_normalise import rasterise
from abacus.modules.evidence.ocr_step import _page_words, _system
from abacus.modules.evidence.words import layer_document, parse_layer


def _image(fmt: str, size: tuple[int, int] = (60, 40), **save: object) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", size, "white").save(buffer, format=fmt, **save)
    return buffer.getvalue()


def test_ac_an_images_page_is_its_size_in_pixels() -> None:
    [page] = rasterise(_image("PNG"), "image/png", None)
    assert (page.page, page.width_pt, page.height_pt) == (1, 60.0, 40.0)


def test_ac_exif_orientation_is_applied_before_reading() -> None:
    exif = Image.Exif()
    exif[0x0112] = 6  # rotated 90 degrees
    [page] = rasterise(_image("JPEG", exif=exif), "image/jpeg", None)
    assert (page.width_pt, page.height_pt) == (40.0, 60.0)


def test_ac_a_multi_page_tiff_is_each_frame() -> None:
    first, second = Image.new("RGB", (10, 10)), Image.new("RGB", (20, 20))
    buffer = io.BytesIO()
    first.save(buffer, format="TIFF", save_all=True, append_images=[second])
    pages = rasterise(buffer.getvalue(), "image/tiff", None)
    assert [(p.page, p.width_pt) for p in pages] == [(1, 10.0), (2, 20.0)]


def test_ac_ocr_words_carry_their_confidence_through_the_sealed_layer() -> None:
    read = OcrPage(
        "a" * 64,
        (OcrWord("6081", (Decimal("1"), Decimal("2"), Decimal("3"), Decimal("4")), Decimal("0.84")),),
        None,
    )
    layer = _page_words(1, 612.0, 792.0, 0, read)
    assert layer.words[0].confidence == 0.84
    assert parse_layer(layer_document(layer)).words == layer.words


def test_ac_the_step_runs_as_the_system() -> None:
    tenant = _system(uuid.uuid4())
    assert isinstance(tenant, TenantContext)
    assert tenant.actor_kind == "system"
