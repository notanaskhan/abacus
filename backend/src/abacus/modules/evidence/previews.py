"""Server-made previews of evidence (SPEC-029 goal 8; TASK-056; ADR-110). PROTECTED.

The browser never renders the raw file. `render_isolated` runs `render` in the isolated child
(`kernel.isolation`): pypdfium2 and Pillow are native code reading hostile files.

- PDF: each page as a PNG, at most `MAX_PAGES`, `PAGE_WIDTH` pixels wide (scanned pages too: they
  have no text, but they have a picture).
- PNG, JPEG, TIFF, GIF (first frame): decoded and re-encoded as PNG, metadata dropped, at most
  `MAX_SIDE` on the longer side; more than `MAX_PIXELS` is refused as a decompression bomb.
- XLSX, CSV: nothing rendered; the viewer shows the extraction's tables (`table`).
- A PDF with active content: `none/active_content`, never opened (DEC-296).
- Anything else (HEIC until P-11-T25): `none`, with why.

Masked renditions (P-03-T15; SPEC-322 AC-24; P-03 §4.4; DEC-369): `render_masked` renders as
`render` does and then, still in the child, paints every detected PII box on its page opaque in
the page's background colour (the most common colour of the image's border), padded `MASK_PAD`
pixels and rounded outward, on an RGB image with no alpha. Boxes are page points (top-left
origin, the word layer's space) scaled by the image over the page's size in points. The unmasked
bitmap never leaves the child; only the burned PNG does.
"""

from __future__ import annotations

import io
import math
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Literal, cast

from PIL import Image, ImageDraw

from abacus.kernel.isolation import IsolationFailed, run_isolated
from abacus.modules.evidence.active_content import is_active

RENDERER_VERSION: Final = "v1"
# P-03-T15: the masked rendition is its own renderer version, so it never collides with a
# pre-masking preview of the same source; `MASK_VERSION` names the masker that burned it.
MASKED_RENDERER_VERSION: Final = "v2"
MASK_VERSION: Final = "m1"
MASK_PAD: Final = 2  # pixels around each detected box (P-03 §4.4)
MAX_PAGES: Final = 50
PAGE_WIDTH: Final = 1240
MAX_SIDE: Final = 2400
MAX_PIXELS: Final = 40_000_000
TABLE_ROWS: Final = 1000
PDF: Final = "application/pdf"
PNG: Final = "image/png"
JPEG: Final = "image/jpeg"
TIFF: Final = "image/tiff"
GIF: Final = "image/gif"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
CSV: Final = "text/csv"

Kind = Literal["pages", "image", "table", "none"]
Box = tuple[float, float, float, float]  # x0, top, x1, bottom
# A page's burn: the rendered image in, the image to keep out (page number from 1).
_Burn = Callable[[int, Image.Image], Image.Image]


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


def _pdf(content: bytes, burn: _Burn | None = None) -> Rendered:
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
            image = bitmap.to_pil()
            pages.append(_png(burn(index + 1, image) if burn is not None else image))
    except Exception:  # a hostile page: pdfium raises several kinds
        return Rendered("none", "damaged")
    finally:
        document.close()
    if not pages:
        return Rendered("none", "empty")
    return Rendered("pages", pages=tuple(pages), truncated=count > MAX_PAGES)


def _image(content: bytes, burn: _Burn | None = None) -> Rendered:
    Image.MAX_IMAGE_PIXELS = MAX_PIXELS
    try:
        with Image.open(io.BytesIO(content)) as image:
            if image.width * image.height > MAX_PIXELS:
                return Rendered("none", "too_large")
            image.load()
            if burn is None:
                image.thumbnail((MAX_SIDE, MAX_SIDE))
                return Rendered("image", pages=(_png(image),))
            burned = burn(1, image)  # at the original size, where an image's boxes are
            burned.thumbnail((MAX_SIDE, MAX_SIDE))
            return Rendered("image", pages=(_png(burned),))
    except Image.DecompressionBombError:
        return Rendered("none", "too_large")
    except Exception:  # a damaged or hostile image
        return Rendered("none", "damaged")


def render(content: bytes, media_type: str) -> Rendered:
    """In-process rendering (tests, and inside the isolated child). A PDF with active content is
    never rendered (DEC-296, ED-021)."""
    if media_type == PDF:
        if is_active(content):
            return Rendered("none", "active_content")
        return _pdf(content)
    if media_type in (PNG, JPEG, TIFF, GIF):
        return _image(content)
    if media_type in (XLSX, CSV):
        return Rendered("table")
    return Rendered("none", "not_previewable")


def background(image: Image.Image) -> tuple[int, int, int]:
    """The page's background colour: the most common colour on the image's border."""
    rgb = image if image.mode == "RGB" else image.convert("RGB")
    w, h = rgb.size
    strips = (
        rgb.crop((0, 0, w, 1)),
        rgb.crop((0, h - 1, w, h)),
        rgb.crop((0, 0, 1, h)),
        rgb.crop((w - 1, 0, w, h)),
    )
    counts: Counter[tuple[int, int, int]] = Counter()
    for strip in strips:
        for count, colour in strip.getcolors(maxcolors=strip.width * strip.height) or []:
            r, g, b = cast(tuple[int, int, int], colour)
            counts[(r, g, b)] += count
    return counts.most_common(1)[0][0] if counts else (255, 255, 255)


def pixel_box(box: Box, scale_x: float, scale_y: float, width: int, height: int) -> Box:
    """A box in page points as the pixels it covers, padded and rounded outward, clamped."""
    x0, top, x1, bottom = box
    return (
        float(max(0, math.floor(min(x0, x1) * scale_x) - MASK_PAD)),
        float(max(0, math.floor(min(top, bottom) * scale_y) - MASK_PAD)),
        float(min(width - 1, math.ceil(max(x0, x1) * scale_x) + MASK_PAD)),
        float(min(height - 1, math.ceil(max(top, bottom) * scale_y) + MASK_PAD)),
    )


def burn(
    image: Image.Image, boxes: Sequence[Box], size: tuple[float, float] | None
) -> Image.Image:
    """`image` as RGB (no alpha, so nothing painted can be see-through) with every box painted
    opaque in its background colour. `size` is the page in the boxes' units (points for a PDF);
    without it the boxes are in the image's own pixels."""
    clean = image.convert("RGB")
    if not boxes:
        return clean
    width_pt, height_pt = size if size is not None else (float(clean.width), float(clean.height))
    scale_x = clean.width / max(width_pt, 1e-6)
    scale_y = clean.height / max(height_pt, 1e-6)
    fill = background(clean)
    draw = ImageDraw.Draw(clean)
    for box in boxes:
        left, upper, right, lower = pixel_box(box, scale_x, scale_y, clean.width, clean.height)
        if right >= left and lower >= upper:
            draw.rectangle((left, upper, right, lower), fill=fill)
    return clean


def render_masked(
    content: bytes,
    media_type: str,
    masks: Mapping[int, Sequence[Box]],
    sizes: Mapping[int, tuple[float, float]],
) -> Rendered:
    """`render` with every page burned (`burn`): `masks` are each page's detected boxes and
    `sizes` each page's size in the boxes' units (the word layer's points for a PDF). Every page
    is RGB, masked or not. In process for tests; the worker calls `render_masked_isolated`."""

    def burn_page(page_no: int, image: Image.Image) -> Image.Image:
        return burn(image, masks.get(page_no, ()), sizes.get(page_no))

    if media_type == PDF:
        if is_active(content):
            return Rendered("none", "active_content")
        return _pdf(content, burn_page)
    if media_type in (PNG, JPEG, TIFF, GIF):
        return _image(content, burn_page)
    if media_type in (XLSX, CSV):
        return Rendered("table")
    return Rendered("none", "not_previewable")


def render_masked_isolated(
    content: bytes,
    media_type: str,
    masks: Mapping[int, Sequence[Box]],
    sizes: Mapping[int, tuple[float, float]],
) -> Rendered:
    """`render_masked` in a short-lived child with limits; a crash or a hang is `none/crashed`."""
    try:
        return run_isolated(render_masked, content, media_type, dict(masks), dict(sizes))
    except IsolationFailed:
        return Rendered("none", "crashed")
    except Exception:
        return Rendered("none", "crashed")


def render_isolated(content: bytes, media_type: str) -> Rendered:
    """`render` in a short-lived child with limits; a crash or a hang is `none/crashed`."""
    try:
        return run_isolated(render, content, media_type)
    except IsolationFailed:
        return Rendered("none", "crashed")
    except Exception:
        return Rendered("none", "crashed")
