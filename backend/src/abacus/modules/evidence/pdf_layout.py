"""What a PDF page shows, and where, for masking (P-03-T15 security review H1, H2, L2; DEC-369).
PROTECTED. Runs only inside the isolated child (`kernel.isolation`): it parses hostile files.

The masked rendition must cover every pixel of a detected value, so the word layer and the
renderer have to agree on both what is on a page and where it is:
- **What (H2):** annotations and form fields are flattened into the page content first
  (`flattened`), for word extraction and rendering alike, and the renderer then draws page
  content only (no annotations): a filled form's value is either in the word layer or not drawn.
- **Where (H1):** word boxes are recorded in render space: the page's visible box (MediaBox ∩
  CropBox) with its `/Rotate` applied and a top-left origin, in points, exactly what PDFium
  renders. `RenderSpace` maps pdfplumber's coordinates (relative to its own MediaBox convention)
  back to PDF user space and on to render space.
- **Fail closed:** a page is unscannable (no word layer, so `not_scannable`) when the mapping
  can't be reconciled with PDFium's own text positions (a word PDFium has no text under, or text
  PDFium draws that no word covers), when a run of nine digits is set sideways, upside down or
  mirrored (`sideways_number`: read out of order, no detector sees it), when it draws text as
  outlines (`outlined_text`), or when its words pass the extractor's cap.
- **Images (review N1):** image pixels can't be read before OCR (P-11). A page with an image
  covering `IMAGE_FLOOR` of it or more keeps its words (its text is still masked for everyone)
  but is marked as holding unscanned image content (`image_content`), so the page is never served
  to a reader who may not read unmasked content. Agents never receive page images.
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import TYPE_CHECKING, Final, Protocol, cast

if TYPE_CHECKING:
    from pdfplumber.page import Page as PlumberPage
    from pypdfium2 import PdfObject, PdfPage

Box = tuple[float, float, float, float]  # x0, top, x1, bottom: render space, points

# DEC-369 (review N1): an image is unscanned content (a pasted SSN card, a W-2 photo, a cheque, a
# logo) when it covers a quarter of a percent of the page or more and is big enough to hold a
# nine-digit number at a legible 6 pt (30 pt along, 6 pt across); tinier marks are left alone.
IMAGE_FLOOR: Final = 0.0025
IMAGE_LONG: Final = 30.0
IMAGE_SHORT: Final = 6.0
# DEC-369 (review N1 regression check): outlined text is a row of `GLYPH_ROW` or more glyph-sized
# curved paths on one baseline, or one curved path of `GLYPH_CURVES`+ Bézier segments shaped like
# a line of text. Logos, rounded boxes and charts are neither.
GLYPH_ROW: Final = 9
GLYPH_CURVES: Final = 20
GLYPH_MIN: Final = 4.0  # points: the shortest and tallest a glyph may be
GLYPH_MAX: Final = 40.0
TIN_DIGITS: Final = 9
SLACK: Final = 2.0  # points: rounding between the two parsers


def flattened(content: bytes, *, unrotated: bool = False) -> bytes:
    """The PDF with every page's annotations and form fields flattened into its content (PDFium's
    `FPDFPage_Flatten`, `FLAT_NORMALDISPLAY`: what a viewer displays). `unrotated` also sets each
    page's `/Rotate` to 0, so pdfplumber reads text in the content's own orientation (read with
    the page turned 180°, `123` comes out as `321` and no detector finds it; `RenderSpace` turns
    the boxes back). Raises on a file PDFium can't open or save."""
    import pypdfium2 as pdfium

    raw = _raw()
    document = pdfium.PdfDocument(content)
    try:
        for index in range(len(document)):
            page = document[index]
            try:
                if raw.FPDFPage_Flatten(page.raw, raw.FLAT_NORMALDISPLAY) == raw.FLATTEN_FAIL:
                    raise ValueError("flatten_failed")
                if unrotated:
                    page.set_rotation(0)
            finally:
                page.close()
        out = io.BytesIO()
        document.save(out)
        return out.getvalue()
    finally:
        document.close()


class _Raw(Protocol):
    """The PDFium calls and constants used here from `pypdfium2.raw`, which ships no stubs."""

    FLAT_NORMALDISPLAY: int
    FLATTEN_FAIL: int
    FPDF_PAGEOBJ_IMAGE: int
    FPDF_PAGEOBJ_PATH: int
    FPDF_SEGMENT_BEZIERTO: int

    def FPDFPage_Flatten(self, page: object, flag: int, /) -> int: ...
    def FPDFPath_CountSegments(self, path: object, /) -> int: ...
    def FPDFPath_GetPathSegment(self, path: object, index: int, /) -> object | None: ...
    def FPDFPathSegment_GetType(self, segment: object, /) -> int: ...


def _raw() -> _Raw:
    return cast(_Raw, import_module("pypdfium2.raw"))


@dataclass(frozen=True)
class RenderSpace:
    """One page's mapping from PDF user space to render space (and from pdfplumber's space)."""

    visible: Box  # PDFium's page box in user space: left, bottom, right, top
    rotation: int  # the page's /Rotate, as PDFium renders it
    width: float  # render size in points, rotation applied
    height: float
    # pdfplumber's frame: pdfminer's raw MediaBox and pdfplumber's inverted one and height.
    miner_box: Box = (0.0, 0.0, 0.0, 0.0)
    plumber_x0: float = 0.0
    plumber_top: float = 0.0
    plumber_height: float = 0.0

    def point(self, x: float, y: float) -> tuple[float, float]:
        """A user-space point in render space (top-left origin, rotation applied)."""
        left, bottom, right, top = self.visible
        if self.rotation == 90:
            return y - bottom, x - left
        if self.rotation == 180:
            return right - x, y - bottom
        if self.rotation == 270:
            return top - y, right - x
        return x - left, top - y

    def user_box(self, left: float, bottom: float, right: float, top: float) -> Box:
        """A user-space rectangle in render space."""
        a = self.point(left, bottom)
        b = self.point(right, top)
        return (min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]))

    def _miner_to_user(self, xm: float, ym: float) -> tuple[float, float]:
        """pdfminer's page coordinates back to user space (the inverse of its CTM, which has no
        rotation: pdfplumber reads the unrotated copy)."""
        x0, y0, _x1, _y1 = self.miner_box
        return xm + x0, ym + y0

    def plumber_box(self, x0: float, top: float, x1: float, bottom: float) -> Box:
        """A pdfplumber box (x0, top, x1, bottom) in render space."""
        corners: list[tuple[float, float]] = []
        for xp, tp in ((x0, top), (x1, bottom)):
            xm = xp - self.plumber_x0
            ym = self.plumber_height - (tp - self.plumber_top)
            corners.append(self.point(*self._miner_to_user(xm, ym)))
        (ax, ay), (bx, by) = corners
        return (min(ax, bx), min(ay, by), max(ax, bx), max(ay, by))


def render_space(
    pdfium_page: PdfPage, plumber_page: PlumberPage | None = None
) -> RenderSpace | None:
    """The page's mapping (PDFium's page as rendered; pdfplumber's page from the unrotated copy),
    or None when PDFium's render size disagrees with its own page box (fail closed)."""
    rotation = int(pdfium_page.get_rotation()) % 360
    if rotation not in (0, 90, 180, 270):
        return None
    left, bottom, right, top = (float(v) for v in pdfium_page.get_bbox())
    width, height = (float(v) for v in pdfium_page.get_size())
    wide, tall = right - left, top - bottom
    expected = (tall, wide) if rotation in (90, 270) else (wide, tall)
    if abs(expected[0] - width) > 1 or abs(expected[1] - height) > 1 or wide <= 0 or tall <= 0:
        return None
    if plumber_page is None:
        return RenderSpace((left, bottom, right, top), rotation, width, height)
    raw = cast(Sequence[float], plumber_page.page_obj.mediabox)  # pdfminer's raw MediaBox
    if int(plumber_page.rotation) % 360 != 0:
        return None  # pdfplumber must read the unrotated copy
    if not (float(plumber_page.width) > 0 and float(plumber_page.height) > 0):
        return None  # a MediaBox pdfplumber can't place words on (PDFium may default it)
    return RenderSpace(
        (left, bottom, right, top),
        rotation,
        width,
        height,
        (float(raw[0]), float(raw[1]), float(raw[2]), float(raw[3])),
        float(plumber_page.mediabox[0]),
        float(plumber_page.mediabox[1]),
        float(plumber_page.height),
    )


def sideways_number(chars: Sequence[dict[str, object]]) -> bool:
    """A run of `TIN_DIGITS` digits (single spaces or hyphens between them allowed) among the
    characters not set upright (a text matrix without a positive diagonal and no shear): text
    read out of order, where no detector can be trusted (fail closed). Sideways labels, margin
    notes with a few digits and a diagonal DRAFT watermark don't qualify (review N1 check)."""
    groups: dict[tuple[float, float, float, float], list[tuple[float, float, str]]] = {}
    for char in chars:
        text = str(char.get("text") or "")
        matrix = char.get("matrix")
        values = cast(Sequence[float], matrix) if isinstance(matrix, tuple | list) else ()
        if len(values) < 4:
            if any(c.isdigit() for c in text):
                return True  # a digit we can't place: fail closed
            continue
        a, b, c, d = (float(v) for v in values[:4])
        if a > 0 and d > 0 and abs(b) <= 0.01 * a and abs(c) <= 0.01 * d:
            continue
        x = (float(cast(float, char.get("x0") or 0)) + float(cast(float, char.get("x1") or 0))) / 2
        y = (
            -(
                float(cast(float, char.get("top") or 0))
                + float(cast(float, char.get("bottom") or 0))
            )
            / 2
        )
        norm = max((a * a + b * b) ** 0.5, 1e-6)
        along = (x * a + y * b) / norm
        across = (-x * b + y * a) / norm
        key = (round(a / norm, 2), round(b / norm, 2), round(c, 1), round(across / 2))
        groups.setdefault(key, []).append((along, across, text))
    for found in groups.values():
        found.sort()
        line = "".join(t if (t.isdigit() or t in " -") else "|" for _, _, t in found)
        digits = 0
        gap = 0
        for ch in line:
            if ch.isdigit():
                digits, gap = digits + 1, 0
            elif ch in " -" and digits and gap == 0:
                gap = 1
            else:
                digits, gap = 0, 0
            if digits >= TIN_DIGITS:
                return True
    return False


def _overlap(a: Box, b: Box, slack: float = SLACK) -> bool:
    return (
        a[0] - slack <= b[2]
        and b[0] - slack <= a[2]
        and a[1] - slack <= b[3]
        and b[1] - slack <= a[3]
    )


def _inside(a: Box, space: RenderSpace) -> bool:
    cx, cy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2
    return 0 <= cx <= space.width and 0 <= cy <= space.height


def text_boxes(pdfium_page: PdfPage, space: RenderSpace) -> list[Box]:
    """PDFium's own text runs on the page with any letter or digit, in render space."""
    textpage = pdfium_page.get_textpage()
    try:
        found: list[Box] = []
        for index in range(textpage.count_rects()):
            left, bottom, right, top = textpage.get_rect(index)
            text = textpage.get_text_bounded(left, bottom, right, top)
            if any(c.isalnum() for c in text):
                box = space.user_box(left, bottom, right, top)
                if _inside(box, space):
                    found.append(box)
        return found
    finally:
        textpage.close()


def reconciled(words: Sequence[Box], drawn: Sequence[Box]) -> bool:
    """Every word sits on text PDFium has there, and every run of text PDFium draws is covered
    by a word (H1, H2): one parser saw what the other renders, at the same place."""
    if not drawn:
        return not words
    return all(any(_overlap(w, d) for d in drawn) for w in words) and all(
        any(_overlap(d, w) for w in words) for d in drawn
    )


def _clipped(space: RenderSpace, bounds: tuple[float, float, float, float]) -> Box | None:
    x0, y0, x1, y1 = space.user_box(*bounds)
    x0, y0 = max(0.0, x0), max(0.0, y0)
    x1, y1 = min(space.width, x1), min(space.height, y1)
    return (x0, y0, x1, y1) if x1 > x0 and y1 > y0 else None


def image_content(pdfium_page: PdfPage, space: RenderSpace) -> bool:
    """An image covering `IMAGE_FLOOR` of the page or more and big enough to hold a legible
    number (`IMAGE_LONG` by `IMAGE_SHORT`; review N1). An image inside a form
    XObject counts as its top-level object's whole box (bounds inside a form aren't in page
    space), which can only overcount."""
    raw = _raw()
    area = space.width * space.height
    top: PdfObject | None = None
    for obj in pdfium_page.get_objects(max_depth=15):
        if obj.level == 0:
            top = obj
        if obj.type == raw.FPDF_PAGEOBJ_IMAGE and top is not None:
            box = _clipped(space, top.get_bounds())
            if box is None or area <= 0:
                continue
            wide, tall = box[2] - box[0], box[3] - box[1]
            legible = max(wide, tall) >= IMAGE_LONG and min(wide, tall) >= IMAGE_SHORT
            if legible and wide * tall / area >= IMAGE_FLOOR:
                return True
    return False


def _beziers(obj: PdfObject, raw: _Raw) -> int:
    found = 0
    for n in range(max(0, raw.FPDFPath_CountSegments(obj.raw))):
        segment = raw.FPDFPath_GetPathSegment(obj.raw, n)
        if segment and raw.FPDFPathSegment_GetType(segment) == raw.FPDF_SEGMENT_BEZIERTO:
            found += 1
    return found


def _glyph_sized(box: Box) -> bool:
    return GLYPH_MIN <= box[3] - box[1] <= GLYPH_MAX


def outlined_text(pdfium_page: PdfPage, space: RenderSpace) -> bool:
    """Text drawn as curves, which no word layer holds (review H2, N1): `GLYPH_ROW` or more
    glyph-sized curved paths of similar height on one baseline with glyph-sized gaps, or one
    top-level curved object (a path, or a form holding paths) of `GLYPH_CURVES` or more Bézier
    segments, glyph-tall and at least four times as wide (a line of outlined glyphs)."""
    raw = _raw()
    curved: dict[int, tuple[Box, int]] = {}  # top-level index -> (box, Bézier segments)
    index = -1
    top: PdfObject | None = None
    for obj in pdfium_page.get_objects(max_depth=15):
        if obj.level == 0:
            index, top = index + 1, obj
        if obj.type == raw.FPDF_PAGEOBJ_PATH and top is not None:
            count = _beziers(obj, raw)
            if count:
                box = _clipped(space, top.get_bounds())
                if box is not None:
                    seen = curved.get(index)
                    curved[index] = (box, count + (seen[1] if seen else 0))
    for box, count in curved.values():
        tall, wide = box[3] - box[1], box[2] - box[0]
        if count >= GLYPH_CURVES and _glyph_sized(box) and wide >= 4 * tall:
            return True
    glyphs = sorted(
        (b for b, _ in curved.values() if _glyph_sized(b) and b[2] - b[0] <= 1.5 * (b[3] - b[1])),
        key=lambda b: (round(b[3] / 3), b[0]),
    )
    run: list[Box] = []
    for box in glyphs:
        if run:
            last = run[-1]
            height = last[3] - last[1]
            same_line = abs(box[3] - last[3]) <= 3
            similar = 1 / 1.5 <= (box[3] - box[1]) / max(height, 1e-6) <= 1.5
            close = 0 <= box[0] - last[2] <= 1.5 * height
            if not (same_line and similar and close):
                run = []
        run.append(box)
        if len(run) >= GLYPH_ROW:
            return True
    return False


__all__ = [
    "IMAGE_FLOOR",
    "RenderSpace",
    "flattened",
    "image_content",
    "outlined_text",
    "reconciled",
    "render_space",
    "sideways_number",
    "text_boxes",
]
