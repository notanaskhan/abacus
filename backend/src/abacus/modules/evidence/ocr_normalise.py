"""Pages as images for OCR (P-11-T25; P-11 §4.4; ADR-110). Runs in the isolated child.

EXIF orientation, HEIC through pillow-heif, multi-page TIFF, and PDF pages rasterised at OCR
resolution. Each page answers its size in page points: a PDF's own points, and an image's pixels
(the unit an image's masks use), so OCR's boxes land where the masks and the viewer expect.
Nothing here keeps a file or logs a word.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from PIL import Image, ImageOps, ImageSequence
from pillow_heif import register_heif_opener

from abacus.kernel.isolation import run_isolated

OCR_DPI: Final = 200
MAX_PAGES: Final = 500
MAX_PIXELS: Final = 80_000_000
PDF: Final = "application/pdf"
IMAGES: Final = frozenset(
    {"image/png", "image/jpeg", "image/tiff", "image/heic", "image/heif"}
)


@dataclass(frozen=True)
class PageImage:
    page: int
    png: bytes
    width_pt: float
    height_pt: float
    rotation: int = 0


def _png(image: Image.Image) -> bytes:
    buffer = io.BytesIO()
    image.convert("RGB").save(buffer, format="PNG")
    return buffer.getvalue()


def _pdf_pages(content: bytes, wanted: frozenset[int] | None) -> tuple[PageImage, ...]:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(content)
    try:
        out: list[PageImage] = []
        for index in range(min(len(document), MAX_PAGES)):
            number = index + 1
            if wanted is not None and number not in wanted:
                continue
            page = document[index]
            width, height = page.get_size()
            bitmap = page.render(scale=OCR_DPI / 72)
            out.append(PageImage(number, _png(bitmap.to_pil()), width, height, page.get_rotation()))
        return tuple(out)
    finally:
        document.close()


def _image_pages(content: bytes) -> tuple[PageImage, ...]:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    register_heif_opener()
    out: list[PageImage] = []
    with Image.open(io.BytesIO(content)) as image:
        for index, frame in enumerate(ImageSequence.Iterator(image)):
            if index >= MAX_PAGES:
                break
            upright = ImageOps.exif_transpose(frame.copy())
            out.append(
                PageImage(index + 1, _png(upright), float(upright.width), float(upright.height))
            )
    return tuple(out)


def rasterise(content: bytes, media_type: str, wanted: Sequence[int] | None) -> tuple[PageImage, ...]:
    """The named pages (all of them with None), upright and ready to read."""
    if media_type == PDF:
        return _pdf_pages(content, None if wanted is None else frozenset(wanted))
    return _image_pages(content)


def rasterise_isolated(
    content: bytes, media_type: str, wanted: Sequence[int] | None
) -> tuple[PageImage, ...]:
    return run_isolated(rasterise, content, media_type, None if wanted is None else tuple(wanted))
