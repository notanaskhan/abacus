"""Q-01-T24 / SPEC-050 AC-24: the HTTP edge middleware, written from the spec text.

Spec: "Given middleware, JSON bodies over 1 MB and uploads over 50 MB (`MAX_CONTENT_BYTES`) are
refused before parsing, a `Host` not matching `trusted_hosts` gets 400, and proxy headers are
honoured only from the ALB. CloudFront forwards `Host` as `X-Forwarded-Host` and the API uses it
only as a branding hint; tenant resolution still comes from membership or grant (ADR-002, INV-4)."

The numbers are tested on both sides of every reading of "1 MB" and "50 MB" (decimal and binary),
so a limit anywhere in the gap between the readings is not asserted. A refused body is 413 (the
HTTP status for a payload over a limit); a refused host is 400, as the spec says. The app is
driven in process over ASGI with `create_app()`; the settings names are those of epic Q-01 4.10.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import FastAPI, Request

from abacus.api import create_app

from .support import Json, cached_app, use_environment, use_staging

MIB = 1024 * 1024
JSON_UNDER = 900_000  # under a decimal MB
JSON_OVER = MIB + 1  # over a binary MB
UPLOAD_UNDER = 49_999_999  # under a decimal 50 MB
UPLOAD_OVER = 50 * MIB + 1  # over a binary 50 MB
ENDPOINT = "/v1/engagements"  # an existing route; the edge refuses before the route is reached

LOCAL = {"ABACUS_ENVIRONMENT": "local"}
# A body with no declared length is refused while it streams in. The spec fixes "refused", not the
# status: 413 is the exact one; 400 is what a framework's aborted body read becomes. Either way it
# is a refusal and the route (401 without a token, 2xx with one) never answers.
REFUSED_WHILE_STREAMING = {400, 413}


def client(app: FastAPI, *, peer: tuple[str, int] | None = None) -> httpx.AsyncClient:
    transport = httpx.ASGITransport(
        app=app, raise_app_exceptions=False, client=peer or ("127.0.0.1", 5000)
    )
    return httpx.AsyncClient(transport=transport, base_url="http://api.example.test")


def json_body(size: int) -> bytes:
    prefix, suffix = b'{"note": "', b'"}'
    return prefix + b"x" * (size - len(prefix) - len(suffix)) + suffix


async def chunks(total: int, *, size: int = 256 * 1024) -> AsyncIterator[bytes]:
    sent = 0
    while sent < total:
        piece = min(size, total - sent)
        sent += piece
        yield b"u" * piece


# --- body size ----------------------------------------------------------------------------------


@pytest.fixture
def app() -> FastAPI:
    return cached_app(LOCAL)


async def test_ac24_a_json_body_under_1_mb_is_not_refused_for_its_size(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.post(
            ENDPOINT, content=json_body(JSON_UNDER), headers={"Content-Type": "application/json"}
        )
    assert response.status_code != 413
    assert response.status_code == 401  # unauthenticated: it got past the edge


async def test_ac24_a_json_body_over_1_mb_is_refused(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.post(
            ENDPOINT, content=json_body(JSON_OVER), headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 413


async def test_ac24_an_oversize_json_body_is_refused_before_it_is_parsed(app: FastAPI) -> None:
    """A body that is not JSON at all, over the limit: refused for its size, not as a 400/422
    parse error, and not as 401 either (the edge answers before routing)."""
    async with client(app) as http:
        response = await http.post(
            ENDPOINT, content=b"{" * JSON_OVER, headers={"Content-Type": "application/json"}
        )
    assert response.status_code == 413


async def test_ac24_a_json_body_over_1_mb_with_a_structured_suffix_type_is_refused(
    app: FastAPI,
) -> None:
    async with client(app) as http:
        response = await http.post(
            ENDPOINT,
            content=json_body(JSON_OVER),
            headers={"Content-Type": "application/problem+json"},
        )
    assert response.status_code == 413


async def test_ac24_a_chunked_json_body_over_1_mb_is_refused_without_a_content_length(
    app: FastAPI,
) -> None:
    async with client(app) as http:
        response = await http.post(
            ENDPOINT,
            content=chunks(JSON_OVER),
            headers={"Content-Type": "application/json"},
        )
    assert response.status_code in REFUSED_WHILE_STREAMING


async def test_ac24_an_upload_over_1_mb_but_under_50_mb_is_not_refused_for_its_size(
    app: FastAPI,
) -> None:
    async with client(app) as http:
        response = await http.post(
            ENDPOINT,
            content=b"u" * (2 * MIB),
            headers={"Content-Type": "application/octet-stream"},
        )
    assert response.status_code == 401


async def test_ac24_an_upload_under_50_mb_is_not_refused_for_its_size(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.post(
            ENDPOINT,
            content=chunks(UPLOAD_UNDER),
            headers={"Content-Type": "application/octet-stream"},
        )
    assert response.status_code == 401


async def test_ac24_an_upload_over_50_mb_is_refused_when_chunked(app: FastAPI) -> None:
    async with client(app) as http:
        response = await http.post(
            ENDPOINT,
            content=chunks(UPLOAD_OVER),
            headers={"Content-Type": "application/octet-stream"},
        )
    assert response.status_code in REFUSED_WHILE_STREAMING


async def test_ac24_an_upload_over_50_mb_is_refused_on_its_declared_length_without_reading_it(
    app: FastAPI,
) -> None:
    delivered = 0
    status = 0

    async def receive() -> Json:
        nonlocal delivered
        delivered += 256 * 1024
        return {"type": "http.request", "body": b"u" * 256 * 1024, "more_body": True}

    async def send(message: Json) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]

    scope: Json = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "POST",
        "scheme": "http",
        "path": ENDPOINT,
        "raw_path": ENDPOINT.encode(),
        "query_string": b"",
        "headers": [
            (b"host", b"api.example.test"),
            (b"content-type", b"application/octet-stream"),
            (b"content-length", str(UPLOAD_OVER + 100 * MIB).encode()),
        ],
        "client": ("127.0.0.1", 5000),
        "server": ("api.example.test", 80),
    }
    await app(scope, receive, send)  # pyright: ignore[reportArgumentType] -- the scope is a plain dict
    assert status == 413
    assert delivered < 10 * MIB  # it did not sit there reading 150 MB first


async def test_ac24_a_get_is_never_refused_for_a_body_limit(app: FastAPI) -> None:
    async with client(app) as http:
        assert (await http.get("/healthz")).status_code == 200


# --- trusted hosts ------------------------------------------------------------------------------


@pytest.fixture
def hosted() -> FastAPI:
    return cached_app({**LOCAL, "ABACUS_TRUSTED_HOSTS": "api.example.test"})


@pytest.mark.parametrize("path", ["/healthz", "/readyz", ENDPOINT, "/nowhere"])
@pytest.mark.parametrize(
    "host",
    [
        "evil.example.test",
        "api.example.test.evil.test",
        "evilapi.example.test",
        "example.test",
        "169.254.169.254",
        "localhost",
    ],
)
async def test_ac24_a_host_not_in_trusted_hosts_gets_400(
    hosted: FastAPI, host: str, path: str
) -> None:
    async with client(hosted) as http:
        response = await http.get(path, headers={"Host": host})
    assert response.status_code == 400


@pytest.mark.parametrize("host", ["api.example.test", "API.EXAMPLE.TEST", "api.example.test:8443"])
async def test_ac24_a_trusted_host_is_served(hosted: FastAPI, host: str) -> None:
    async with client(hosted) as http:
        response = await http.get("/healthz", headers={"Host": host})
    assert response.status_code == 200


async def test_ac24_several_trusted_hosts_may_be_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    use_environment(
        monkeypatch,
        {**LOCAL, "ABACUS_TRUSTED_HOSTS": "api.example.test,staging.example.test"},
    )
    async with client(create_app()) as http:
        for host in ("api.example.test", "staging.example.test"):
            assert (await http.get("/healthz", headers={"Host": host})).status_code == 200
        assert (
            await http.get("/healthz", headers={"Host": "other.example.test"})
        ).status_code == 400


async def test_ac24_x_forwarded_host_cannot_make_an_untrusted_host_trusted(
    hosted: FastAPI,
) -> None:
    async with client(hosted) as http:
        response = await http.get(
            "/healthz",
            headers={"Host": "evil.example.test", "X-Forwarded-Host": "api.example.test"},
        )
    assert response.status_code == 400


async def test_ac24_x_forwarded_host_is_only_a_hint_not_a_host_check(hosted: FastAPI) -> None:
    """CloudFront forwards the portal host as `X-Forwarded-Host`; the request is judged on
    `Host`."""
    async with client(hosted) as http:
        response = await http.get(
            "/healthz",
            headers={"Host": "api.example.test", "X-Forwarded-Host": "acme.portal.example.test"},
        )
    assert response.status_code == 200


async def test_ac24_a_request_without_a_host_is_refused(hosted: FastAPI) -> None:
    status = 0

    async def receive() -> Json:
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message: Json) -> None:
        nonlocal status
        if message["type"] == "http.response.start":
            status = message["status"]

    scope: Json = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.0",
        "method": "GET",
        "scheme": "http",
        "path": "/healthz",
        "raw_path": b"/healthz",
        "query_string": b"",
        "headers": [],
        "client": ("127.0.0.1", 5000),
        "server": ("api.example.test", 80),
    }
    await hosted(scope, receive, send)  # pyright: ignore[reportArgumentType] -- the scope is a plain dict
    assert status == 400


# --- proxy headers, from the load balancer only -------------------------------------------------

ALB = "10.0.0.5"
STRANGER = "198.51.100.7"
FORWARDED = {"X-Forwarded-For": "203.0.113.9", "X-Forwarded-Proto": "https"}


def with_probe(app: FastAPI) -> FastAPI:
    """A route on this test's app that reports what the app believes about the caller."""

    async def whoami(request: Request) -> dict[str, str]:
        return {
            "client": request.client.host if request.client else "",
            "scheme": request.url.scheme,
        }

    app.add_api_route("/__whoami", whoami, methods=["GET"])
    return app


async def believed(app: FastAPI, peer: str) -> dict[str, str]:
    async with client(with_probe(app), peer=(peer, 40000)) as http:
        response = await http.get("/__whoami", headers=FORWARDED)
    assert response.status_code == 200
    return response.json()


async def test_ac24_proxy_headers_are_honoured_from_the_load_balancer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_environment(monkeypatch, {**LOCAL, "ABACUS_PROXY_TRUSTED_HOSTS": ALB})
    assert await believed(create_app(), ALB) == {"client": "203.0.113.9", "scheme": "https"}


async def test_ac24_proxy_headers_are_ignored_from_anyone_else(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_environment(monkeypatch, {**LOCAL, "ABACUS_PROXY_TRUSTED_HOSTS": ALB})
    assert await believed(create_app(), STRANGER) == {"client": STRANGER, "scheme": "http"}


async def test_ac24_proxy_headers_are_ignored_when_no_load_balancer_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_environment(monkeypatch, LOCAL)
    assert await believed(create_app(), ALB) == {"client": ALB, "scheme": "http"}


async def test_ac24_a_forged_chain_does_not_launder_an_untrusted_peer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_environment(monkeypatch, {**LOCAL, "ABACUS_PROXY_TRUSTED_HOSTS": ALB})
    app = with_probe(create_app())
    async with client(app, peer=(STRANGER, 40000)) as http:
        response = await http.get(
            "/__whoami", headers={"X-Forwarded-For": f"203.0.113.9, {ALB}", **FORWARDED}
        )
    assert response.json()["client"] == STRANGER


@pytest.mark.parametrize("name", ["staging", "production"])
def test_ac24_outside_local_the_proxy_list_may_not_trust_everyone(
    monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    from abacus.kernel.config import settings

    use_staging(monkeypatch, ABACUS_ENVIRONMENT=name, ABACUS_PROXY_TRUSTED_HOSTS="*")
    with pytest.raises(ValueError):
        settings()
