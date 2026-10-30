"""What every render shares and needs no Pango (P-11-T07): the refusal type, the pinned metadata
head and the PDF identifier. `pdf.py` imports WeasyPrint; this module does not, so HTML can be
built and checked outside the isolated child.
"""

from __future__ import annotations

import hashlib
from datetime import datetime


class RenderRefused(RuntimeError):
    """A render refused for a reason the caller reports as a C11 error code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def pdf_identifier(content_hash: str) -> bytes:
    """The PDF /ID: 16 bytes of the content hash, so the same inputs give the same file."""
    return hashlib.sha256(content_hash.encode("ascii")).digest()[:16]


def _w3c(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def dated_head(title: str, as_of: datetime) -> str:
    """The <head> metadata WeasyPrint reads: title, and both dates pinned to `as_of`."""
    stamp = _w3c(as_of)
    return (
        "<meta charset='utf-8'>"
        f"<title>{title}</title>"
        f"<meta name='dcterms.created' content='{stamp}'>"
        f"<meta name='dcterms.modified' content='{stamp}'>"
        "<meta name='generator' content='abacus-reporting'>"
    )
