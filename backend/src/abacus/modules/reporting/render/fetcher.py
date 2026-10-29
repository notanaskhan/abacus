"""The renderer's URL fetcher (ADR-320 §4; SPEC-520 AC-9): it refuses every scheme but `asset:`,
and `asset:` resolves only from the in-memory map, so a render never touches the network or the
file system (no `http://169.254.169.254/…`, no `file:///etc/passwd`, no `data:`).
"""

from __future__ import annotations

from collections.abc import Mapping

from weasyprint.urls import URLFetcher, URLFetcherResponse

ASSET_SCHEME = "asset:"

_TYPES = {".woff": "font/woff", ".png": "image/png", ".css": "text/css"}


class AssetNotAllowed(ValueError):
    """`asset_not_allowed`: a URL that is not a known in-memory asset."""


class AssetFetcher(URLFetcher):
    """Serves `asset:<id>` from `assets`; anything else fails the whole render (fail_on_errors)."""

    def __init__(self, assets: Mapping[str, bytes]) -> None:
        super().__init__(fail_on_errors=True, allowed_protocols=set(), allow_redirects=False)
        self._assets = dict(assets)
        self.refused: list[str] = []

    def fetch(self, url: str, headers: dict[str, str] | None = None) -> URLFetcherResponse:
        if not url.startswith(ASSET_SCHEME):
            self.refused.append(url[:80])
            raise AssetNotAllowed("asset_not_allowed")
        key = url[len(ASSET_SCHEME) :]
        data = self._assets.get(key)
        if data is None:
            self.refused.append(url[:80])
            raise AssetNotAllowed("asset_not_allowed")
        suffix = key[key.rfind(".") :] if "." in key else ""
        return URLFetcherResponse(
            url, data, {"Content-Type": _TYPES.get(suffix, "application/octet-stream")}
        )
