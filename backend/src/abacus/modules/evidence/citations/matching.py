"""The comparisons citation verifiers make, by code (P-03-T06; ADR-066, ADR-166; DEC-218).
PROTECTED.

Pure functions, no I/O: v2's registered verifiers use them on the word layer and the extraction,
and the agents' legacy verifiers (`agents.citations`, `agents.document_citations`) are adapters
over the same rules, so one rule decides what "the quote is there" means.

- Text is compared after Unicode NFKC, case folding, dropping invisible format and control
  characters, and collapsing whitespace. A quote joining several lines counts when every line is
  there.
- On the word layer a quote is a run of consecutive words whose normalised text holds it. The
  region is the union of that run's boxes; the stored hash is of the run's normalised text, so a
  reader re-reading the words in the region gets the same digest (`quote_state`).
- A box resolves when words sit inside it: a word belongs to a box when its centre does.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, Protocol

Reason = Literal[
    "page_not_found",
    "cell_not_found",
    "quote_not_found",
    "value_mismatch",
    "bbox_mismatch",
    "source_not_found",
    "source_not_visible",
    "locator_invalid",
]
Box = tuple[float, float, float, float]  # x0, top, x1, bottom in page points

_CELL: Final = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
_AMOUNT: Final = re.compile(r"^\(?-?\$?\(?[0-9][0-9,]*(\.[0-9]+)?\)?-?$")
MAX_SPAN_WORDS: Final = 400  # a quote longer than this many words isn't matched to a region


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


def normalised(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    kept = "".join(
        c for c in folded if unicodedata.category(c) not in ("Cf", "Cc") or c in "\n\t "
    )
    return " ".join(kept.split())


def quote_in(quote: str, text: str) -> bool:
    """Every line of the quote appears in the text (a quote may join lines from one page)."""
    parts = [normalised(line) for line in quote.splitlines() if normalised(line)]
    haystack = normalised(text)
    return bool(parts) and all(part in haystack for part in parts)


def page_quote_reason(pages: Mapping[int, str], page: int, quote: str) -> Reason | None:
    """A quote on a page of extracted text: `page_not_found`, `quote_not_found` or None."""
    text = pages.get(page)
    if text is None:
        return "page_not_found"
    return None if quote_in(quote, text) else "quote_not_found"


# --- Cells ---------------------------------------------------------------------------------------


def column_index(letters: str) -> int:
    index = 0
    for letter in letters:
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def column_letters(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA (the inverse of `column_index`)."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def cell_text(rows: Sequence[Sequence[str]], cell: str) -> str | None:
    """The text of a cell (`C14`) in extracted rows (row 1 is the first), or None."""
    found = _CELL.match(cell)
    if found is None:
        return None
    column, row = column_index(found.group(1)), int(found.group(2)) - 1
    if row >= len(rows) or column >= len(rows[row]):
        return None
    return rows[row][column]


def amount(text: str) -> Decimal | None:
    """A printed amount as a number: `1,650.00`, `$1,650.00`, `(1,650.00)` and `1,650.00-`."""
    token = text.strip()
    if not token or not _AMOUNT.match(token):
        return None
    negative = token.startswith(("(", "-")) or token.endswith((")", "-"))
    digits = token.strip("()-$").replace(",", "").lstrip("$(")
    try:
        found = Decimal(digits)
    except InvalidOperation:
        return None
    return -found if negative else found


def cell_reason(
    text: str | None,
    number: Decimal | None,
    quote: str | None,
    value: Decimal | None,
    *,
    exact_quote: bool,
) -> Reason | None:
    """A cited cell: it must exist; a quote must be its text (exactly, or contained after
    normalisation); a value must equal its number."""
    if text is None:
        return "cell_not_found"
    if quote is not None and not (text == quote if exact_quote else quote_in(quote, text)):
        return "quote_not_found"
    if value is not None and number != value:
        return "value_mismatch"
    return None


# --- The word layer ------------------------------------------------------------------------------


def _centre_in(word: WordLike, box: Box, slack: float = 1.0) -> bool:
    x, y = (word.x0 + word.x1) / 2, (word.top + word.bottom) / 2
    return box[0] - slack <= x <= box[2] + slack and box[1] - slack <= y <= box[3] + slack


def words_in(words: Sequence[WordLike], box: Box) -> list[WordLike]:
    return [w for w in words if _centre_in(w, box)]


def joined(words: Sequence[WordLike]) -> str:
    return normalised(" ".join(w.text for w in words))


def layer_sha256(words: Sequence[WordLike]) -> bytes:
    """The digest stored for a quote: of the normalised text of the region's words."""
    return hashlib.sha256(joined(words).encode()).digest()


def union(words: Sequence[WordLike]) -> Box:
    return (
        min(w.x0 for w in words),
        min(w.top for w in words),
        max(w.x1 for w in words),
        max(w.bottom for w in words),
    )


def quote_span(words: Sequence[WordLike], quote: str) -> list[WordLike] | None:
    """The shortest run of consecutive words whose normalised text holds the whole quote (its
    lines joined by a space), or None."""
    target = normalised(" ".join(quote.splitlines()))
    if not target:
        return None
    best: list[WordLike] | None = None
    for start in range(len(words)):
        # Past this length the quote would have to start after the first word: a later start.
        limit = len(target) + len(normalised(words[start].text)) + 1
        text = ""
        for end in range(start, min(len(words), start + MAX_SPAN_WORDS)):
            text = normalised(f"{text} {words[end].text}")
            if target in text:
                if best is None or end + 1 - start < len(best):
                    best = list(words[start : end + 1])
                break
            if len(text) > limit:
                break
    return best


@dataclass(frozen=True)
class LayerVerdict:
    reason: Reason | None
    box: Box | None  # the resolved region, when there is one
    sha256: bytes | None  # of the region's words, when there is a region and a quote
    value_text: str | None  # the printed value, when a cited value was found


def _value_in(words: Sequence[WordLike], value: Decimal) -> WordLike | None:
    return next((w for w in words if amount(w.text) == value), None)


def verify_on_layer(
    words: Sequence[WordLike],
    page_text: str,
    *,
    box: Box | None,
    quote: str | None,
    value: Decimal | None,
) -> LayerVerdict:
    """A `document_text` claim on one page (DEC-218):
    - a box with no words in it is `bbox_mismatch`;
    - a quote must be inside the box (else `bbox_mismatch` when it is elsewhere on the page,
      `quote_not_found` when it isn't on the page); the region becomes the quote's words;
    - with no box, the region is the quote's words; a quote found on the page but in no run of
      words (rotated or multi-column text) is verified with no region, never failed for that;
    - a value must be one of the region's printed amounts (the page's, with no region; the
      region is then the word that prints it)."""
    region: list[WordLike] | None = None
    if box is not None:
        inside = words_in(words, box)
        if not inside:
            return LayerVerdict("bbox_mismatch", None, None, None)
        region = inside
    if quote is not None:
        if region is not None:
            span = quote_span(region, quote)
            if span is None:
                elsewhere = quote_span(words, quote) is not None or quote_in(quote, page_text)
                return LayerVerdict(
                    "bbox_mismatch" if elsewhere else "quote_not_found", None, None, None
                )
            region = span
        else:
            region = quote_span(words, quote)
            if region is None and not quote_in(quote, page_text):
                return LayerVerdict("quote_not_found", None, None, None)
    printed: str | None = None
    if value is not None:
        word = _value_in(region if region is not None else words, value)
        if word is not None:
            printed = word.text
            region = region if region is not None else [word]  # the value lights alone
        elif region is None:
            printed = next((t for t in page_text.split() if amount(t.strip(",;:")) == value), None)
        if printed is None:
            return LayerVerdict("value_mismatch", None, None, None)
    if region is None:
        return LayerVerdict(None, None, None, printed)
    digest = layer_sha256(region) if quote is not None else None
    return LayerVerdict(None, union(region), digest, printed)


__all__ = [
    "MAX_SPAN_WORDS",
    "Box",
    "LayerVerdict",
    "Reason",
    "amount",
    "cell_reason",
    "cell_text",
    "column_index",
    "column_letters",
    "joined",
    "layer_sha256",
    "normalised",
    "page_quote_reason",
    "quote_in",
    "quote_span",
    "union",
    "verify_on_layer",
    "words_in",
]
