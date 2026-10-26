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
  PDFium draws that no word covers), or when its words pass the extractor's cap.
- **Unread content (reviews N1, R1 to R3):** what a scan can't read before OCR (P-11) is a picture
  big enough to hold a number (`image_content`), vector shapes the size of glyphs (`drawn_glyphs`:
  text drawn as outlines), and any digit set sideways, upside down or mirrored (`upright`: read
  out of order). A page showing any of them keeps its upright words (still detected and masked
  for everyone; sideways words are left out of the layer) but is marked `unread`, so it is never
  served to a reader who may not read unmasked content. Broad on purpose: an offshore reader
  loses a page rather than see a number no scan read.
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

# DEC-369 (reviews N1, R1): an image is unread content when it could hold a nine-digit number at
# the smallest size a person might read (about 4 pt): 20 pt along and 4 pt across, whatever its
# share of the page. Only hairlines and specks are left.
IMAGE_LONG: Final = 20.0
IMAGE_SHORT: Final = 4.0
# DEC-369 (review R2): text drawn as outlines is `GLYPHS` or more glyph-sized vector objects
# (straight or curved; 4 to 40 pt), anywhere on the page, or one object glyph-tall, four times as
# wide and of `GLYPH_SEGMENTS` or more segments (a line of glyphs in one path).
GLYPHS: Final = 9
GLYPH_SEGMENTS: Final = 20
GLYPH_MIN: Final = 4.0  # points: the smallest and largest a glyph may be
GLYPH_MAX: Final = 40.0
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


def upright(char: dict[str, object]) -> bool:
    """A character set upright and unmirrored in the content (a text matrix with a positive
    diagonal and no shear). Anything else is read out of order (review R3)."""
    matrix = char.get("matrix")
    values = cast(Sequence[float], matrix) if isinstance(matrix, tuple | list) else ()
    if len(values) < 4:
        return False
    a, b, c, d = (float(v) for v in values[:4])
    return a > 0 and d > 0 and abs(b) <= 0.01 * a and abs(c) <= 0.01 * d


def sideways_digits(chars: Sequence[dict[str, object]]) -> bool:
    """Any digit not set upright (review R3, broadened): its number can't be read in order, so
    the page holds unread content."""
    return any(
        any(c.isdigit() for c in str(char.get("text") or "")) and not upright(char)
        for char in chars
    )


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
    """An image big enough to hold a legible number (`IMAGE_LONG` by `IMAGE_SHORT`; reviews N1,
    R1). An image inside a form XObject counts as its top-level object's whole box (bounds
    inside a form aren't in page space), which can only overcount."""
    raw = _raw()
    top: PdfObject | None = None
    for obj in pdfium_page.get_objects(max_depth=15):
        if obj.level == 0:
            top = obj
        if obj.type == raw.FPDF_PAGEOBJ_IMAGE and top is not None:
            box = _clipped(space, top.get_bounds())
            if box is None:
                continue
            wide, tall = box[2] - box[0], box[3] - box[1]
            if max(wide, tall) >= IMAGE_LONG and min(wide, tall) >= IMAGE_SHORT:
                return True
    return False


def _segments(obj: PdfObject, raw: _Raw) -> int:
    return max(0, raw.FPDFPath_CountSegments(obj.raw))


def drawn_glyphs(pdfium_page: PdfPage, space: RenderSpace) -> bool:
    """Vector shapes that could be text drawn as outlines (review R2, broadened): `GLYPHS` or more
    top-level objects holding paths, each glyph-sized (no side over `GLYPH_MAX`, one side at
    least `GLYPH_MIN`; straight or curved, overlapping or not), anywhere on the page; or one such
    object glyph-tall, at least four times as wide, of `GLYPH_SEGMENTS` or more segments. A form
    XObject holding `GLYPHS` or more paths counts too (its inner bounds aren't in page space)."""
    raw = _raw()
    pathed: dict[int, tuple[Box, int, int]] = {}  # top-level index -> (box, paths, segments)
    index = -1
    top: PdfObject | None = None
    for obj in pdfium_page.get_objects(max_depth=15):
        if obj.level == 0:
            index, top = index + 1, obj
        if obj.type == raw.FPDF_PAGEOBJ_PATH and top is not None:
            box = _clipped(space, top.get_bounds())
            if box is None:
                continue
            seen = pathed.get(index)
            paths, segments = (seen[1], seen[2]) if seen else (0, 0)
            pathed[index] = (box, paths + 1, segments + _segments(obj, raw))
    glyphs = 0
    for box, paths, segments in pathed.values():
        wide, tall = box[2] - box[0], box[3] - box[1]
        if paths >= GLYPHS:
            return True  # a form of many paths, or many subpaths drawn as one object
        if max(wide, tall) <= GLYPH_MAX and max(wide, tall) >= GLYPH_MIN:
            glyphs += 1
        elif GLYPH_MIN <= tall <= GLYPH_MAX and wide >= 4 * tall and segments >= GLYPH_SEGMENTS:
            return True
        if glyphs >= GLYPHS:
            return True
    return False


__all__ = [
    "RenderSpace",
    "drawn_glyphs",
    "flattened",
    "image_content",
    "reconciled",
    "render_space",
    "sideways_digits",
    "text_boxes",
    "upright",
]
