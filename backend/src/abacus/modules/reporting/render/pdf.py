"""PDF from HTML through WeasyPrint (ADR-320 §3; SPEC-520 AC-6, AC-7, AC-9; P-11-T02).

Byte stability: the creation and modification dates come from the snapshot's `as_of` through the
document's `dcterms` meta (WeasyPrint writes no clock time otherwise); the PDF identifier is
derived from the content hash; fonts are the vendored faces only; compression is on and fixed.
"""

from __future__ import annotations

from weasyprint import CSS, HTML
from weasyprint.urls import FatalURLFetchingError

from abacus.modules.reporting.render.assets import font_assets
from abacus.modules.reporting.render.fetcher import ASSET_SCHEME, AssetFetcher
from abacus.modules.reporting.render.head import RenderRefused, dated_head, pdf_identifier

__all__ = ["RenderRefused", "dated_head", "pdf_identifier", "render_pdf"]


def render_pdf(
    html: str, css: str, *, content_hash: str, assets: dict[str, bytes] | None = None
) -> bytes:
    """`html` is a complete document from a code-owned layout (variables already escaped);
    `css` is the layout's stylesheet. Fails `asset_not_allowed` on any URL that is not a known
    in-memory asset."""
    # The vendored faces are checked against their manifest before any text is shaped; fontconfig
    # then finds them by family name (fonts.conf lists only their directory).
    fetcher = AssetFetcher({**font_assets(), **(assets or {})})
    try:
        document = HTML(string=html, base_url=ASSET_SCHEME, url_fetcher=fetcher)
        sheets = [CSS(string=css, base_url=ASSET_SCHEME, url_fetcher=fetcher)]
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
