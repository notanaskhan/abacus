"""PDF from HTML through WeasyPrint (ADR-320 §3; SPEC-520 AC-6, AC-7, AC-9; P-11-T02).

Byte stability: the creation and modification dates come from the snapshot's `as_of` through the
document's `dcterms` meta (WeasyPrint writes no clock time otherwise); the PDF identifier is
derived from the content hash; fonts are the vendored faces only; compression is on and fixed.
"""

from __future__ import annotations

import hashlib
from datetime import datetime

from weasyprint import CSS, HTML
from weasyprint.urls import FatalURLFetchingError

from abacus.modules.reporting.render.assets import font_assets, font_face_css
from abacus.modules.reporting.render.fetcher import ASSET_SCHEME, AssetFetcher


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


def render_pdf(html: str, css: str, *, content_hash: str) -> bytes:
    """`html` is a complete document from a code-owned layout (variables already escaped);
    `css` is the layout's stylesheet. Fails `asset_not_allowed` on any URL that is not a known
    in-memory asset."""
    fetcher = AssetFetcher(font_assets())
    try:
        document = HTML(string=html, base_url=ASSET_SCHEME, url_fetcher=fetcher)
        sheets = [
            CSS(string=font_face_css(), base_url=ASSET_SCHEME, url_fetcher=fetcher),
            CSS(string=css, base_url=ASSET_SCHEME, url_fetcher=fetcher),
        ]
        out = document.write_pdf(
            stylesheets=sheets,
            pdf_identifier=pdf_identifier(content_hash),
            uncompressed_pdf=False,
            optimize_images=False,
            full_fonts=False,
            hinting=False,
        )
    except FatalURLFetchingError as error:
        raise RenderRefused("asset_not_allowed") from error
    if fetcher.refused:
        raise RenderRefused("asset_not_allowed")
    return out
