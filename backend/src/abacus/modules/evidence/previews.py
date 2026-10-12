"""Server-made previews of evidence (SPEC-029 goal 8; TASK-056; ADR-110). PROTECTED.

The browser never renders the raw file. `render_isolated` runs `render` in the isolated child
(`kernel.isolation`): pypdfium2 and Pillow are native code reading hostile files.

- PDF: each page as a PNG, at most `MAX_PAGES`, `PAGE_WIDTH` pixels wide (scanned pages too: they
  have no text, but they have a picture).
- PNG, JPEG: decoded and re-encoded as PNG, metadata dropped, at most `MAX_SIDE` on the longer
  side; more than `MAX_PIXELS` is refused as a decompression bomb.
- XLSX, CSV: nothing rendered; the viewer shows the extraction's tables (`table`).
- Anything else: `none`, with why.
"""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Final, Literal

from PIL import Image

from abacus.kernel.isolation import IsolationFailed, run_isolated

RENDERER_VERSION: Final = "v1"
MAX_PAGES: Final = 50
PAGE_WIDTH: Final = 1240
MAX_SIDE: Final = 2400
MAX_PIXELS: Final = 40_000_000
TABLE_ROWS: Final = 1000
PDF: Final = "application/pdf"
PNG: Final = "image/png"
JPEG: Final = "image/jpeg"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV: Final = "text/csv"

Kind = Literal["pages", "image", "table", "none"]


@dataclass(frozen=True)
class Page:
    png: bytes
    width: int
    height: int


@dataclass(frozen=True)
class Rendered:
    kind: Kind
    reason: str | None = None
    pages: tuple[Page, ...] = ()
    truncated: bool = False


def _png(image: Image.Image) -> Page:
    clean = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    out = io.BytesIO()
    clean.save(out, format="PNG", optimize=True)  # no metadata is carried over
    return Page(out.getvalue(), clean.width, clean.height)


def _pdf(content: bytes) -> Rendered:
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(content)
    except pdfium.PdfiumError as exc:
        reason = "encrypted" if "password" in str(exc).casefold() else "damaged"
        return Rendered("none", reason)
    try:
        count = len(document)
        pages: list[Page] = []
        for index in range(min(count, MAX_PAGES)):
            page = document[index]
            width, _ = page.get_size()
            bitmap = page.render(scale=PAGE_WIDTH / max(width, 1.0))
            pages.append(_png(bitmap.to_pil()))
    except Exception:  # a hostile page: pdfium raises several kinds
        return Rendered("none", "damaged")
    finally:
        document.close()
    if not pages:
        return Rendered("none", "empty")
    return Rendered("pages", pages=tuple(pages), truncated=count > MAX_PAGES)


def _image(content: bytes) -> Rendered:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > MAX_PIXELS:
                return Rendered("none", "too_large")
            image.load()
            image.thumbnail((MAX_SIDE, MAX_SIDE))
            return Rendered("image", pages=(_png(image),))
    except Image.DecompressionBombError:
        return Rendered("none", "too_large")
    except Exception:  # a damaged or hostile image
        return Rendered("none", "damaged")


def render(content: bytes, media_type: str) -> Rendered:
    """In-process rendering (tests, and inside the isolated child)."""
    if media_type == PDF:
        return _pdf(content)
    if media_type in (PNG, JPEG):
        return _image(content)
    if media_type in (XLSX, CSV):
        return Rendered("table")
    return Rendered("none", "not_previewable")


def render_isolated(content: bytes, media_type: str) -> Rendered:
    """`render` in a short-lived child with limits; a crash or a hang is `none/crashed`."""
    try:
        return run_isolated(render, content, media_type)
    except IsolationFailed:
        return Rendered("none", "crashed")
    except Exception:
        return Rendered("none", "crashed")
