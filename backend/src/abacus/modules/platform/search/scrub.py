"""Code-only scrubbing of the hostile strings a search document carries (P-02-T06 hook; P-02-T07
fills the PII detector; ADR-241 decision 4; ADR-052). A client's name, a file name or a mail
subject is client content: before it is stored, control characters and the Unicode bidi overrides
and isolates that reorder text on screen are removed, and runs of whitespace collapse to one space.
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Final

from abacus.modules.platform.search.spec import RelatedParty, SearchIndexDocument

# C0 and C1 controls, and the bidi embeddings, overrides and isolates (U+202A-U+202E,
# U+2066-U+2069), the marks U+200E/U+200F and the zero-width joiners and BOM.
_HOSTILE: Final = re.compile("[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f-\u009f​-‏‪-‮⁠-⁩﻿]")
_SPACES: Final = re.compile(r"\s+")


def clean(value: str) -> str:
    """The string without hostile characters, whitespace collapsed and trimmed."""
    return _SPACES.sub(" ", _HOSTILE.sub("", value)).strip()


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
