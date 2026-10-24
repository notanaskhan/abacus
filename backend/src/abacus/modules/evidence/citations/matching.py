"""The comparisons citation verifiers make, by code (P-03-T06; ADR-066, ADR-166; DEC-218).
PROTECTED.

Pure functions, no I/O: v2's registered verifiers use them on the word layer and the extraction,
and the agents' legacy verifiers (`agents.citations`, `agents.document_citations`) are adapters
over the same rules, so one rule decides what "the quote is there" means.

- Text is compared after Unicode NFKC, case folding, dropping invisible format and control
  characters, and collapsing whitespace.
- v2 (`quote_at`, `quote_span`): the whole quote, its lines joined by a space, must appear
  contiguously and on word boundaries: never inside a longer word or number (`16,500` is not in
  `16,500,000.00`). On the word layer the region is the run of words it covers, and the stored
  hash is of that run's normalised text, so a reader re-reading the region gets the same digest.
- Legacy (`quote_in`, the agents' adapters only): every line of the quote is somewhere on the
  page, the rule SPEC-030 shipped with; v2 never uses it (security review).
- A quote longer than `MAX_QUOTE` characters is never searched.
- A box resolves when words sit inside it: a word belongs to a box when its centre does.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from bisect import bisect_right
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
QuoteRule = Literal["exact", "lines", "contiguous"]

_CELL: Final = re.compile(r"^([A-Z]{1,3})([1-9][0-9]*)$")
_AMOUNT: Final = re.compile(r"^\(?-?\$?\(?[0-9][0-9,]*(\.[0-9]+)?\)?-?$")
MAX_QUOTE: Final = 2000  # characters: a longer quote is never searched (quote_not_found)


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
    """Legacy (SPEC-030; the agents' adapters only): every line of the quote appears somewhere in
    the text. v2 verification uses `quote_at`."""
    parts = [normalised(line) for line in quote.splitlines() if normalised(line)]
    haystack = normalised(text)
    return bool(parts) and all(part in haystack for part in parts)


def _target(quote: str) -> str:
    return normalised(" ".join(quote.splitlines())) if len(quote) <= MAX_QUOTE else ""


def _bounded(target: str) -> re.Pattern[str]:
    """The target on word boundaries: not inside a longer word, nor a longer number."""
    return re.compile(r"(?<!\w)(?<!\d[.,])" + re.escape(target) + r"(?!\w)(?![.,]\d)")


def quote_at(quote: str, text: str) -> bool:
    """v2: the whole quote is in the text, contiguously, on word boundaries."""
    target = _target(quote)
    return bool(target) and _bounded(target).search(normalised(text)) is not None


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
    quote_rule: QuoteRule,
) -> Reason | None:
    """A cited cell: it must exist; a quote must be its text (`exact`, the screener), every line
    of it in the text (`lines`, the legacy upload reviewer) or in it contiguously on word
    boundaries (`contiguous`, v2); a value must equal its number."""
    if text is None:
        return "cell_not_found"
    if quote is not None:
        found = (
            text == quote
            if quote_rule == "exact"
            else quote_in(quote, text)
            if quote_rule == "lines"
            else quote_at(quote, text)
        )
        if not found:
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
    """The run of consecutive words the whole quote covers, on word boundaries, or None. One pass
    over the page: each word is normalised once and the quote is searched in the joined text."""
    target = _target(quote)
    if not target:
        return None
    kept: list[WordLike] = []
    starts: list[int] = []
    tokens: list[str] = []
    at = 0
    for word in words:
        token = normalised(word.text)
        if not token:
            continue
        kept.append(word)
        starts.append(at)
        tokens.append(token)
        at += len(token) + 1
    found = _bounded(target).search(" ".join(tokens))
    if found is None:
        return None
    first = bisect_right(starts, found.start()) - 1
    last = bisect_right(starts, found.end() - 1) - 1
    return kept[first : last + 1]


def quote_spans(words: Sequence[WordLike], query: str, *, limit: int) -> list[list[WordLike]]:
    """P-03-T09 (in-document search): every run of consecutive words holding `query` whole and
    on word boundaries, left to right without overlaps, at most `limit` runs."""
    target = _target(query)
    if not target or limit < 1:
        return []
    kept: list[WordLike] = []
    starts: list[int] = []
    tokens: list[str] = []
    at = 0
    for word in words:
        token = normalised(word.text)
        if not token:
            continue
        kept.append(word)
        starts.append(at)
        tokens.append(token)
        at += len(token) + 1
    runs: list[list[WordLike]] = []
    for found in _bounded(target).finditer(" ".join(tokens)):
        first = bisect_right(starts, found.start()) - 1
        last = bisect_right(starts, found.end() - 1) - 1
        runs.append(kept[first : last + 1])
        if len(runs) >= limit:
            break
    return runs


def line_rects(run: Sequence[WordLike]) -> list[Box]:
    """A run's boxes, one per printed line: a word starts a new line when its top is below the
    current line's middle."""
    rects: list[Box] = []
    line: list[WordLike] = []
    for word in run:
        if line and word.top > (line[0].top + line[0].bottom) / 2:
            rects.append(union(line))
            line = []
        line.append(word)
    if line:
        rects.append(union(line))
    return rects


_EDGE: Final = 0.011  # stored boxes are rounded to 2 decimals (verifiers._round)


def _near(a: float, b: float) -> bool:
    return abs(a - b) <= _EDGE


def reread_span(
    words: Sequence[WordLike], box: Box, sha256: bytes, *, max_words: int = 2000
) -> list[WordLike] | None:
    """P-03-T08: the run of consecutive words inside `box` whose normalised text hashes to
    `sha256` (the run a verifier resolved the quote to), or None when no run does (the layer no
    longer holds the quote: `changed`). The run's union is the stored box, so it starts on the
    box's top edge and ends on its bottom edge; only those pairs are hashed."""
    inside = [w for w in words_in(words, box) if normalised(w.text)][:max_words]
    starts = [i for i, w in enumerate(inside) if _near(round(w.top, 2), box[1])]
    ends = [j for j, w in enumerate(inside) if _near(round(w.bottom, 2), box[3])]
    for i in starts:
        for j in ends:
            if j < i:
                continue
            run = inside[i : j + 1]
            found = union(run)
            if not (_near(round(found[0], 2), box[0]) and _near(round(found[2], 2), box[2])):
                continue
            if layer_sha256(run) == sha256:
                return run
    return None


@dataclass(frozen=True)
class LayerVerdict:
    reason: Reason | None
    box: Box | None  # the resolved region, when there is one
    sha256: bytes | None  # of the matched quote's normalised text, when a quote was cited
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
    """A `document_text` claim on one page (DEC-218, amended by the security review):
    - a claim with no box, no quote and no value checks nothing: `locator_invalid`;
    - a box with no words in it is `bbox_mismatch`;
    - a quote must be inside the box (else `bbox_mismatch` when it is elsewhere on the page,
      `quote_not_found` when it isn't on the page); the region becomes the quote's words;
    - with no box, the region is the quote's words; a quote on the page text but in no run of
      words is verified with no region, its hash that of the matched text, never failed for that;
    - a value must be one of the region's printed amounts (the page's, with no region; the
      region is then the word that prints it).
    A verified verdict always carries a hash, a region or a printed value."""
    if box is None and quote is None and value is None:
        return LayerVerdict("locator_invalid", None, None, None)
    region: list[WordLike] | None = None
    digest: bytes | None = None
    if box is not None:
        inside = words_in(words, box)
        if not inside:
            return LayerVerdict("bbox_mismatch", None, None, None)
        region = inside
    if quote is not None:
        if region is not None:
            span = quote_span(region, quote)
            if span is None:
                elsewhere = quote_span(words, quote) is not None or quote_at(quote, page_text)
                return LayerVerdict(
                    "bbox_mismatch" if elsewhere else "quote_not_found", None, None, None
                )
            region = span
        else:
            region = quote_span(words, quote)
            if region is None:
                if not quote_at(quote, page_text):
                    return LayerVerdict("quote_not_found", None, None, None)
                digest = hashlib.sha256(_target(quote).encode()).digest()
        if region is not None:
            digest = layer_sha256(region)
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
    return LayerVerdict(None, union(region) if region else None, digest, printed)


__all__ = [
    "MAX_QUOTE",
    "Box",
    "LayerVerdict",
    "QuoteRule",
    "Reason",
    "amount",
    "cell_reason",
    "cell_text",
    "column_index",
    "column_letters",
    "joined",
    "layer_sha256",
    "line_rects",
    "normalised",
    "page_quote_reason",
    "quote_at",
    "quote_in",
    "quote_span",
    "quote_spans",
    "reread_span",
    "union",
    "verify_on_layer",
    "words_in",
]
