"""Code-only clause segmentation of a governing instrument (T-07-T12; TASK-8039; T-07 §3.1;
SPEC-656 AC-1.3; ADR-050: code reads structure, never a model).

Input: the instrument's word layer, page by page (`evidence.api.version_word_layers`; text-layer
words, or OCR words with their confidence). Output: the clause list `instrument_clauses` keeps —
labels, headings, ordinals, parents, page spans, regions and a text hash — never the text.

Rules (the trust-agreement grammar of TXT-01):
- **Lines.** Words on a page group into lines by their vertical centre (half a line height).
- **Articles.** A line that starts "ARTICLE <roman>" opens article clause `Art. <roman>`; the rest
  of the line is its heading ("ARTICLE III — DISTRIBUTIONS" → heading "DISTRIBUTIONS").
- **Sub-clauses.** A line that starts "(a)" to "(z)" inside an article opens `Art. <roman>(a)`,
  a child of the article.
- **Hanging indents.** Every other line continues the clause open above it, across pages.
  Lines before the first article (the title block, the preamble) belong to no clause.
- **Regions.** Per page, the union box of the clause's lines; a clause over a page break has a
  region on each page.
- **Confidence.** The share of the body's lines (from the first article on) whose words read at
  the OCR bar or better, times the share of articles numbered in sequence; below `REVIEW_BAR` the
  segmentation is `needs_review` and a person marks the clauses (`ClauseMarkIn`).
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Protocol

SEGMENTATION_VERSION: Final = "1.0"
REVIEW_BAR: Final = Decimal("0.9000")
OCR_WORD_BAR: Final = 0.85
_ARTICLE: Final = re.compile(r"^ARTICLE\s+([IVXLC]+)\b[\s.:\-—–]*(.*)$", re.IGNORECASE)  # noqa: RUF001
_SUBCLAUSE: Final = re.compile(r"^\(([a-z])\)")
_ROMAN: Final = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


class WordLike(Protocol):
    @property
    def text(self) -> str: ...
    @property
    def x0(self) -> float: ...
    @property
    def top(self) -> float: ...
    @property
    def x1(self) -> float: ...
    @property
    def bottom(self) -> float: ...
    @property
    def confidence(self) -> float: ...


class PageLike(Protocol):
    @property
    def page(self) -> int: ...
    @property
    def words(self) -> Sequence[WordLike]: ...


@dataclass(frozen=True, slots=True)
class Line:
    page: int
    words: tuple[WordLike, ...]

    @property
    def text(self) -> str:
        return " ".join(w.text for w in self.words)

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (
            min(w.x0 for w in self.words),
            min(w.top for w in self.words),
            max(w.x1 for w in self.words),
            max(w.bottom for w in self.words),
        )

    @property
    def confident(self) -> bool:
        return all(w.confidence >= OCR_WORD_BAR for w in self.words)


@dataclass(slots=True)
class Clause:
    label: str
    heading: str | None
    ordinal: int
    parent: str | None
    lines: list[Line] = field(default_factory=lambda: list[Line]())

    @property
    def page_from(self) -> int:
        return min(line.page for line in self.lines)

    @property
    def page_to(self) -> int:
        return max(line.page for line in self.lines)

    def regions(self) -> list[dict[str, object]]:
        by_page: dict[int, list[tuple[float, float, float, float]]] = {}
        for line in self.lines:
            by_page.setdefault(line.page, []).append(line.box)
        return [
            {
                "page": page,
                "bbox": [
                    round(min(b[0] for b in boxes), 2),
                    round(min(b[1] for b in boxes), 2),
                    round(max(b[2] for b in boxes), 2),
                    round(max(b[3] for b in boxes), 2),
                ],
            }
            for page, boxes in sorted(by_page.items())
        ]

    def text_sha256(self) -> str:
        words = " ".join(" ".join(line.text.split()) for line in self.lines)
        return hashlib.sha256(words.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class Segmentation:
    clauses: tuple[Clause, ...]
    confidence: Decimal
    layer_sha256: str
    text_source: str

    @property
    def status(self) -> str:
        return "segmented" if self.clauses and self.confidence >= REVIEW_BAR else "needs_review"


def roman(numeral: str) -> int:
    total, last = 0, 0
    for ch in reversed(numeral.upper()):
        value = _ROMAN[ch]
        total = total - value if value < last else total + value
        last = max(last, value)
    return total


def lines_of(pages: Sequence[PageLike]) -> list[Line]:
    """Words into lines, top to bottom then left to right, page by page."""
    out: list[Line] = []
    for page in sorted(pages, key=lambda p: p.page):
        words = sorted(page.words, key=lambda w: ((w.top + w.bottom) / 2, w.x0))
        current: list[WordLike] = []
        centre = 0.0
        for word in words:
            mid = (word.top + word.bottom) / 2
            height = max(word.bottom - word.top, 1.0)
            if current and abs(mid - centre) > height / 2:
                out.append(Line(page.page, tuple(sorted(current, key=lambda w: w.x0))))
                current = []
            if not current:
                centre = mid
            current.append(word)
        if current:
            out.append(Line(page.page, tuple(sorted(current, key=lambda w: w.x0))))
    return out


def segment(pages: Sequence[PageLike], *, text_source: str = "text_layer") -> Segmentation:
    lines = lines_of(pages)
    clauses: list[Clause] = []
    article: Clause | None = None
    current: Clause | None = None
    body = 0
    confident = 0
    numbers: list[int] = []
    for line in lines:
        text = line.text.strip()
        found = _ARTICLE.match(text)
        if found:
            numeral = found.group(1).upper()
            numbers.append(roman(numeral))
            heading = found.group(2).strip() or None
            article = Clause(f"Art. {numeral}", heading, len(clauses), None, [line])
            clauses.append(article)
            current = article
        elif article is not None and (sub := _SUBCLAUSE.match(text)):
            current = Clause(
                f"{article.label}({sub.group(1)})", None, len(clauses), article.label, [line]
            )
            clauses.append(current)
        elif current is not None:
            current.lines.append(line)  # a hanging indent or a continuation
        if article is not None:
            body += 1
            confident += line.confident
    in_sequence = sum(1 for i, n in enumerate(numbers) if n == i + 1)
    share = Decimal(confident) / Decimal(body) if body else Decimal(0)
    ordered = Decimal(in_sequence) / Decimal(len(numbers)) if numbers else Decimal(0)
    confidence = (share * ordered).quantize(Decimal("0.0001"), ROUND_HALF_UP)
    layer = hashlib.sha256(
        "\n".join(f"{line.page}:{line.text}" for line in lines).encode("utf-8")
    ).hexdigest()
    return Segmentation(tuple(clauses), confidence, layer, text_source)
