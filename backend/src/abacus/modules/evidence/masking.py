"""The masked projection of the word layer (P-03 §4.4; SPEC-322 AC-23, AC-24; DEC-52, DEC-60).
PROTECTED.

What a reader of client text sees: every word whose centre lies in a detected PII region of its
page is replaced by the region's mask token, and a run of such words in one region becomes one
token. Quotes re-read for a citation (P-03-T08) and in-document search (P-03-T09) go through it;
masked renditions burn the same boxes into the page image (P-03-T15). Pure functions, no I/O: the
regions come from `pii_regions` (P-03-T13 writes them), never their sealed values.

Tokens: `•••-••-6081` (SSN, ITIN), `••-•••0287` (EIN), `••••1234` (bank account, routing number),
`••/••/••••` (date of birth); without known last digits the token is `••••`.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from abacus.modules.evidence.citations.matching import Box, WordLike, words_in

MASK: Final = "••••"


class RegionLike(Protocol):
    @property
    def page_no(self) -> int: ...
    @property
    def kind(self) -> str: ...
    @property
    def last4(self) -> str | None: ...


@dataclass(frozen=True)
class MaskRegion:
    """A detected region in page points (top-left origin), with what its token shows."""

    page_no: int
    box: Box
    kind: str
    last4: str | None


def mask_token(kind: str, last4: str | None) -> str:
    """The display a masked value carries everywhere (P-03 §4.4)."""
    if kind == "dob":
        return "••/••/••••"
    if not last4:
        return MASK
    if kind in ("ssn", "itin"):
        return f"•••-••-{last4}"
    if kind == "ein":
        return f"••-•••{last4}"
    return f"••••{last4}"


@dataclass(frozen=True)
class MaskedWord:
    """A word as a reader may see it: its own text, or a region's token over its box."""

    text: str
    x0: float
    top: float
    x1: float
    bottom: float
    masked: bool = False


def masked_words(
    words: Sequence[WordLike], regions: Sequence[MaskRegion], page_no: int
) -> list[MaskedWord]:
    """The page's words with every word inside a region of that page replaced by the region's
    token; consecutive words of one region collapse into one token spanning their box."""
    mine = [r for r in regions if r.page_no == page_no]
    owner: dict[int, int] = {}
    for index, region in enumerate(mine):
        for word in words_in(words, region.box):
            owner.setdefault(id(word), index)
    out: list[MaskedWord] = []
    last: int | None = None
    for word in words:
        found = owner.get(id(word))
        if found is None:
            out.append(MaskedWord(word.text, word.x0, word.top, word.x1, word.bottom))
            last = None
            continue
        if found == last and out:
            prior = out[-1]
            out[-1] = MaskedWord(
                prior.text,
                min(prior.x0, word.x0),
                min(prior.top, word.top),
                max(prior.x1, word.x1),
                max(prior.bottom, word.bottom),
                True,
            )
            continue
        region = mine[found]
        token = mask_token(region.kind, region.last4)
        out.append(MaskedWord(token, word.x0, word.top, word.x1, word.bottom, True))
        last = found
    return out


def masked_text(words: Sequence[WordLike], regions: Sequence[MaskRegion], page_no: int) -> str:
    """The words as one line of text, masked."""
    return " ".join(w.text for w in masked_words(words, regions, page_no))


__all__ = ["MASK", "MaskRegion", "MaskedWord", "mask_token", "masked_text", "masked_words"]
