# The part of WeasyPrint the renderer uses (ADR-320, P-11-T02); it ships no stubs.
from typing import Any

from .urls import URLFetcher

__version__: str

class CSS:
    def __init__(
        self,
        *,
        string: str | None = ...,
        base_url: str | None = ...,
        url_fetcher: URLFetcher | None = ...,
    ) -> None: ...

class Document:
    def write_pdf(self, target: None = ..., **options: Any) -> bytes: ...

class HTML:
    def __init__(
        self,
        *,
        string: str | None = ...,
        base_url: str | None = ...,
        url_fetcher: URLFetcher | None = ...,
    ) -> None: ...
    def render(self, **options: Any) -> Document: ...
    def write_pdf(self, target: None = ..., **options: Any) -> bytes: ...
