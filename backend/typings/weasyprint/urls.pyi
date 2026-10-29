# The part of WeasyPrint's URL fetching the renderer uses (ADR-320, P-11-T02).
from typing import Any

class FatalURLFetchingError(BaseException): ...
class URLFetchingError(IOError): ...

class URLFetcherResponse:
    def __init__(
        self,
        url: str,
        body: bytes | str | None = ...,
        headers: dict[str, str] | None = ...,
        status: int = ...,
        **kwargs: Any,
    ) -> None: ...

class URLFetcher:
    def __init__(
        self,
        timeout: int = ...,
        ssl_context: Any = ...,
        http_headers: dict[str, str] | None = ...,
        allowed_protocols: set[str] | None = ...,
        allow_redirects: bool = ...,
        fail_on_errors: bool = ...,
        **kwargs: Any,
    ) -> None: ...
    def fetch(self, url: str, headers: dict[str, str] | None = ...) -> URLFetcherResponse: ...
    def __call__(self, url: str) -> URLFetcherResponse: ...
