"""Field regions on a rendered PDF (P-11-T11; P-11 §4.4 "Field regions"; SPEC-520 AC-22).

The plan's method is WeasyPrint's page anchors refined against the PDF's word boxes, with text
search for the value as the fallback. The layouts do not emit per-variable anchors yet, so v1
uses the fallback alone (DEC-1561): each variable's value is found as a run of consecutive words
in the PDF's word layer (pdfplumber, the isolated child only) and its box is the union of those
words' boxes, in PDF points with a top-left origin. Every occurrence is kept, in reading order.
A value that is not found (a variable used only inside a disabled clause) has no region.
"""

from __future__ import annotations

import io
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

_TRAILING = ",.;:)"
_LEADING = "("


@dataclass(frozen=True)
class Region:
    field_key: str
    occurrence: int
    page: int
    rect_pt: tuple[float, float, float, float]
    value_text: str


@dataclass(frozen=True)
class PageSize:
    width_pt: float
    height_pt: float


def _norm(word: str) -> str:
    return word.lstrip(_LEADING).rstrip(_TRAILING)


def _find(words: Sequence[str], tokens: Sequence[str]) -> list[int]:
    """Start indexes where `tokens` match consecutive words (punctuation-tolerant at the ends)."""
    if not tokens:
        return []
    starts: list[int] = []
    width = len(tokens)
    for i in range(len(words) - width + 1):
        if all(_norm(words[i + j]) == _norm(tokens[j]) for j in range(width)):
            starts.append(i)
    return starts


def locate(pdf: bytes, values: Mapping[str, str]) -> tuple[list[Region], list[PageSize]]:
    """Every occurrence of every value, and each page's size (the child only: pdfplumber)."""
    import pdfplumber

    regions: list[Region] = []
    sizes: list[PageSize] = []
    counts: dict[str, int] = {}
    with pdfplumber.open(io.BytesIO(pdf)) as document:
        for page_no, page in enumerate(document.pages, start=1):
            sizes.append(PageSize(float(page.width), float(page.height)))
            words = page.extract_words(keep_blank_chars=False, use_text_flow=True)
            texts = [str(w["text"]) for w in words]
            for key in sorted(values):
                value = values[key]
                tokens = value.split()
                for start in _find(texts, tokens):
                    hit = words[start : start + len(tokens)]
                    counts[key] = counts.get(key, 0) + 1
                    regions.append(
                        Region(
                            field_key=key,
                            occurrence=counts[key],
                            page=page_no,
                            rect_pt=(
                                round(min(float(w["x0"]) for w in hit), 2),
                                round(min(float(w["top"]) for w in hit), 2),
                                round(max(float(w["x1"]) for w in hit), 2),
                                round(max(float(w["bottom"]) for w in hit), 2),
                            ),
                            value_text=value[:4000],
                        )
                    )
    return regions, sizes
