"""PDF words with boxes and page images, read in an isolated child (K-01-T20; ADR-110, ADR-052).

Shared by the evidence extractor and previews (`problem_of`, `png_of`) and by the methodology
importer (`read_words`, `render_page`; K-01-T20/T21). The readers run on hostile bytes, so callers
use the `*_isolated` wrappers, which run them in `kernel.isolation`'s short-lived child with CPU,
memory and time limits. A file that cannot be read comes back as a problem code, never a raise:

- `encrypted`: it needs a password;
- `damaged`: pdfplumber and PDFium both refuse it (malformed, truncated, not a PDF);
- `too_many_pages`: more than `MAX_PAGES` (nothing past the cap is read);
- `crashed`: the child died or hit a limit (`IsolationFailed`).

Words are pdfplumber's, each with its box as fractions of the page (x0, top, x1, bottom), so a
region maps onto the page image at any size. Text is cleaned (control characters dropped, length
capped) before it leaves the child. No module is imported here.
"""

from __future__ import annotations

import io
import unicodedata
from dataclasses import dataclass
from typing import Final, Literal

from abacus.kernel.isolation import IsolationFailed, Limits, run_isolated_with

MAX_PAGES: Final = 400
MAX_WORDS_PER_PAGE: Final = 5000
MAX_WORD: Final = 200
PAGE_WIDTH_PX: Final = 1200
# A 400-page methodology manual is a long read: more time than an upload's preview gets.
LIMITS: Final = Limits(timeout_seconds=120, cpu_seconds=100)
_REFUSED: Final = frozenset({"Cc", "Cf", "Cs", "Co"})

Problem = Literal["encrypted", "damaged", "too_many_pages", "crashed"]


@dataclass(frozen=True)
class Word:
    text: str
    box: tuple[float, float, float, float]


@dataclass(frozen=True)
class PageWords:
    page: int  # from 1
    words: tuple[Word, ...]
    # The page's size in points (K-01-T21 keeps it with the words, `methodology_source_pages`).
    width: float = 0.0
    height: float = 0.0

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)


@dataclass(frozen=True)
class PdfWords:
    page_count: int
    pages: tuple[PageWords, ...] = ()
    problem: Problem | None = None


@dataclass(frozen=True)
class PagePng:
    page: int
    page_count: int
    png: bytes = b""
    width: int = 0
    height: int = 0
    problem: Problem | Literal["page_out_of_range"] | None = None


def clean(value: object, limit: int = MAX_WORD) -> str:
    """Plain text: control and format characters dropped, length capped (ADR-052)."""
    text = "" if value is None else str(value)
    kept = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) not in _REFUSED)
    return kept[:limit].strip()


def problem_of(exc: BaseException) -> Problem:
    """`encrypted` when a password is needed (pdfplumber wraps pdfminer's error), else `damaged`.
    The evidence extractor's reason for an unreadable PDF (unchanged since TASK-334)."""
    from pdfminer.pdfdocument import PDFEncryptionError, PDFPasswordIncorrect

    causes = (exc, *exc.args, exc.__cause__)
    if any(isinstance(c, (PDFPasswordIncorrect, PDFEncryptionError)) for c in causes):
        return "encrypted"
    return "damaged"


def png_of(image: object) -> tuple[bytes, int, int]:
    """A Pillow image as PNG bytes with its width and height (previews and the importer). The
    image is redrawn in RGB or RGBA first, so no metadata is carried over."""
    from PIL import Image

    if not isinstance(image, Image.Image):
        raise TypeError("png_of needs a Pillow image")
    clean_image = image.convert("RGBA" if image.mode in ("RGBA", "LA", "P") else "RGB")
    out = io.BytesIO()
    clean_image.save(out, format="PNG", optimize=True)
    return out.getvalue(), clean_image.width, clean_image.height


def _fraction(value: object, size: float) -> float:
    number = float(value) if isinstance(value, (int, float)) else 0.0
    return min(max(number / size, 0.0), 1.0) if size > 0 else 0.0


def read_words(
    content: bytes, max_pages: int = MAX_PAGES, first: int = 1, last: int | None = None
) -> PdfWords:
    """Every page's words with their boxes, or pages `first` to `last` only (K-01-T21's batches;
    `page_count` is still the file's); run it through `read_words_isolated`."""
    import pdfplumber

    try:
        pdf = pdfplumber.open(io.BytesIO(content))
    except Exception as exc:  # a hostile, damaged or password-protected file
        return PdfWords(0, problem=problem_of(exc))
    try:
        count = len(pdf.pages)
        if count > max_pages:
            return PdfWords(count, problem="too_many_pages")
        pages: list[PageWords] = []
        end = count if last is None else min(last, count)
        for number in range(max(first, 1), end + 1):
            page = pdf.pages[number - 1]
            width = float(page.width)
            height = float(page.height)
            words: list[Word] = []
            for found in page.extract_words()[:MAX_WORDS_PER_PAGE]:
                text = clean(found.get("text"))
                if text == "":
                    continue
                words.append(
                    Word(
                        text,
                        (
                            _fraction(found.get("x0"), width),
                            _fraction(found.get("top"), height),
                            _fraction(found.get("x1"), width),
                            _fraction(found.get("bottom"), height),
                        ),
                    )
                )
            pages.append(PageWords(number, tuple(words), width, height))
        return PdfWords(count, tuple(pages))
    except Exception as exc:  # pdfminer raises several kinds on a hostile page
        return PdfWords(0, problem=problem_of(exc))
    finally:
        pdf.close()


def render_page(content: bytes, page: int, width_px: int = PAGE_WIDTH_PX) -> PagePng:
    """One page as a PNG `width_px` wide (PDFium); run it through `render_page_isolated`."""
    import pypdfium2 as pdfium

    try:
        document = pdfium.PdfDocument(content)
    except Exception as exc:  # PDFium raises PdfiumError for a password or a damaged file
        text = str(exc).lower()
        return PagePng(page, 0, problem="encrypted" if "password" in text else "damaged")
    try:
        count = len(document)
        if count > MAX_PAGES:
            return PagePng(page, count, problem="too_many_pages")
        if not 1 <= page <= count:
            return PagePng(page, count, problem="page_out_of_range")
        found = document[page - 1]
        try:
            points, _ = found.get_size()
            image = found.render(scale=width_px / max(points, 1.0)).to_pil()
            png, width, height = png_of(image)
        finally:
            found.close()
        return PagePng(page, count, png, width, height)
    except Exception:  # a hostile page
        return PagePng(page, 0, problem="damaged")
    finally:
        document.close()


def read_words_isolated(
    content: bytes, max_pages: int = MAX_PAGES, first: int = 1, last: int | None = None
) -> PdfWords:
    try:
        return run_isolated_with(LIMITS, read_words, content, max_pages, first, last)
    except IsolationFailed:
        return PdfWords(0, problem="crashed")


def render_page_isolated(content: bytes, page: int, width_px: int = PAGE_WIDTH_PX) -> PagePng:
    try:
        return run_isolated_with(LIMITS, render_page, content, page, width_px)
    except IsolationFailed:
        return PagePng(page, 0, problem="crashed")


__all__ = [
    "MAX_PAGES",
    "PagePng",
    "PageWords",
    "PdfWords",
    "Problem",
    "Word",
    "clean",
    "png_of",
    "problem_of",
    "read_words",
    "read_words_isolated",
    "render_page",
    "render_page_isolated",
]
