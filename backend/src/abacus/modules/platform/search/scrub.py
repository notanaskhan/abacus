"""Code-only scrubbing of the hostile strings a search document carries (P-02-T06, P-02-T07;
ADR-241 decision 4; ADR-052). A client's name, a file name or a mail subject is client content:
before it is stored, control characters and the Unicode bidi overrides and isolates that reorder
text on screen are removed, and runs of whitespace collapse to one space.

P-02-T07 (DEC-4613) adds the code-only PII and amount pass: a TIN-shaped token (SSN, ITIN, EIN,
nine digits run together), any longer digit run (an account number) and a currency amount are
replaced by `•••`, so no index row holds a TIN or an amount even when a file was named after one
("Feld 900-45-6789 W-2.pdf"). No model is involved (ADR-050).
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Final

from abacus.modules.platform.search.spec import RelatedParty, SearchIndexDocument

# C0 and C1 controls, and the bidi embeddings, overrides and isolates (U+202A-U+202E,
# U+2066-U+2069), the marks U+200E/U+200F and the zero-width joiners and BOM.
# Written as escapes, never literal characters (bandit B613, trojan source; Q-03-T268).
_HOSTILE: Final = re.compile(
    "[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f"
    "\u200b-\u200f\u202a-\u202e\u2060-\u2069\ufeff]"
)
_SPACES: Final = re.compile(r"\s+")
_MASK: Final = "•••"
# SSN/ITIN 3-2-4 and EIN 2-7 with or without separators; nine or more digits run together.
_TIN: Final = re.compile(r"(?<![\d-])(?:\d{3}[- ]?\d{2}[- ]?\d{4}|\d{2}-\d{7})(?![\d-])")
_LONG_DIGITS: Final = re.compile(r"\d{9,}")
_AMOUNT: Final = re.compile(r"[$€£]\s?\d[\d,]*(?:\.\d+)?|\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b")


def mask_pii(value: str) -> str:
    """TINs, long digit runs and amounts replaced by `•••` (code only)."""
    return _AMOUNT.sub(_MASK, _LONG_DIGITS.sub(_MASK, _TIN.sub(_MASK, value)))


def clean(value: str) -> str:
    """The string without hostile characters or PII, whitespace collapsed and trimmed."""
    return mask_pii(_SPACES.sub(" ", _HOSTILE.sub("", value)).strip())


def _maybe(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = clean(value)
    return cleaned or None


def scrub_document(doc: SearchIndexDocument) -> SearchIndexDocument:
    """The document with every free-text field cleaned (identifiers and codes are checked, not
    cleaned, by `spec.check_document`)."""
    return replace(
        doc,
        title=clean(doc.title),
        context=_maybe(doc.context),
        identifiers=tuple(i for i in (clean(x) for x in doc.identifiers) if i),
        related=tuple(
            RelatedParty(name=clean(r.name), label=clean(r.label))
            for r in doc.related
            if clean(r.name)
        ),
    )
