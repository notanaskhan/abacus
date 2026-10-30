# The part of WeasyPrint's URL fetching the renderer uses (ADR-320, P-11-T02).
class FatalURLFetchingError(BaseException): ...
class URLFetchingError(IOError): ...

class URLFetcherResponse:
    def __init__(
        self,
        url: str,
        body: bytes | str | None = ...,
        headers: dict[str, str] | None = ...,
        status: int = ...,
        **kwargs: object,
    ) -> None: ...

class URLFetcher:
    def __init__(
        self,
        timeout: int = ...,
        ssl_context: object = ...,
        http_headers: dict[str, str] | None = ...,
        allowed_protocols: set[str] | None = ...,
        allow_redirects: bool = ...,
        fail_on_errors: bool = ...,
        **kwargs: object,
    ) -> None: ...
    def fetch(self, url: str, headers: dict[str, str] | None = ...) -> URLFetcherResponse: ...
    def __call__(self, url: str) -> URLFetcherResponse: ...
