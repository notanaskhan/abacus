"""TASK-6990 (DEC-3990; ADR-163 amendment; SPEC-050 AC-24): `TrustedHosts` judges the viewer's
host, the same value every host-dependent route reads.

Behind CloudFront the request's `Host` is the origin's own name (the internal load balancer) and
the viewer's host arrives only as `X-Forwarded-Host`, written by the edge function over anything
the viewer sent. So from a peer in `proxy_trusted_hosts` the forwarded host is the one judged and
read; from any other peer it is ignored and `Host` is judged, as before (Q-01-T24's AC-24 tests
run with no trusted peer and are unchanged). The app is `create_app()` over ASGI, with a probe
route that reports the viewer host it was given.
"""

from __future__ import annotations

from collections.abc import Mapping

import httpx
from fastapi import FastAPI, Request

from abacus.api import create_app
from abacus.kernel.viewer_host import ViewerHost

from .support import cached_app

ALB = "10.0.0.5"
STRANGER = "198.51.100.7"
ORIGIN = "internal-abacus-api.example.internal"  # the name CloudFront sends as `Host`
API = "app.example.test"
PORTALS = "portal.example.test"
EDGE = {
    "ABACUS_ENVIRONMENT": "local",
    "ABACUS_TRUSTED_HOSTS": API,
    "ABACUS_PORTAL_BASE_DOMAIN": PORTALS,
    "ABACUS_PROXY_TRUSTED_HOSTS": ALB,
}
PROBE = "/__viewer_host"

_PROBED: dict[tuple[tuple[str, str], ...], FastAPI] = {}


def probed(environment: Mapping[str, str]) -> FastAPI:
    """The app under `environment`, with a route that answers the viewer host it depends on."""
    key = tuple(sorted(environment.items()))
    if key not in _PROBED:
        app = cached_app(environment) if environment else create_app()

        async def viewer(host: ViewerHost, request: Request) -> dict[str, str | None]:
            return {"viewer_host": host, "client": request.client.host if request.client else None}

        app.add_api_route(PROBE, viewer, methods=["GET"])
        _PROBED[key] = app
    return _PROBED[key]


async def ask(peer: str, headers: dict[str, str]) -> httpx.Response:
    transport = httpx.ASGITransport(
        app=probed(EDGE), raise_app_exceptions=False, client=(peer, 40000)
    )
    async with httpx.AsyncClient(transport=transport, base_url=f"http://{API}") as http:
        return await http.get(PROBE, headers=headers)


async def test_a_trusted_peers_forwarded_host_is_judged_and_read() -> None:
    response = await ask(ALB, {"Host": ORIGIN, "X-Forwarded-Host": "Acme.Portal.Example.Test:443"})
    assert response.status_code == 200, response.text
    assert response.json()["viewer_host"] == "acme.portal.example.test"


async def test_the_firm_app_host_through_the_edge_is_served() -> None:
    response = await ask(ALB, {"Host": ORIGIN, "X-Forwarded-Host": API})
    assert response.json()["viewer_host"] == API


async def test_trusted_hosts_refuses_an_unknown_forwarded_host() -> None:
    """The origin's `Host` is trusted here on purpose: the forwarded host alone is refused."""
    for host in (API, ORIGIN):
        response = await ask(ALB, {"Host": host, "X-Forwarded-Host": "evil.example.test"})
        assert response.status_code == 400, host
        assert response.json() == {"detail": "invalid host"}


async def test_an_ambiguous_forwarded_host_from_a_trusted_peer_is_refused() -> None:
    chained = f"acme.{PORTALS}, {API}"
    response = await ask(ALB, {"Host": API, "X-Forwarded-Host": chained})
    assert response.status_code == 400


async def test_a_spoofed_forwarded_host_from_an_untrusted_peer_is_ignored() -> None:
    response = await ask(STRANGER, {"Host": API, "X-Forwarded-Host": "evil.example.test"})
    assert response.status_code == 200, response.text
    assert response.json()["viewer_host"] == API
    portal = await ask(STRANGER, {"Host": f"acme.{PORTALS}", "X-Forwarded-Host": f"b.{PORTALS}"})
    assert portal.json()["viewer_host"] == f"acme.{PORTALS}"


async def test_an_untrusted_peer_cannot_borrow_a_trusted_forwarded_host() -> None:
    response = await ask(STRANGER, {"Host": ORIGIN, "X-Forwarded-Host": API})
    assert response.status_code == 400


async def test_a_trusted_peer_without_a_forwarded_host_is_judged_on_host() -> None:
    """The load balancer's own probes carry no forwarded host."""
    assert (await ask(ALB, {"Host": API})).json()["viewer_host"] == API
    assert (await ask(ALB, {"Host": ORIGIN})).status_code == 400


async def test_proxy_headers_still_correct_the_client_after_the_host_is_judged() -> None:
    """`TrustedHosts` now sits outside uvicorn's proxy middleware (it must see the real peer);
    the client address the app believes is still the forwarded one."""
    response = await ask(
        ALB, {"Host": ORIGIN, "X-Forwarded-Host": API, "X-Forwarded-For": "203.0.113.9"}
    )
    assert response.json() == {"viewer_host": API, "client": "203.0.113.9"}
    stranger = await ask(STRANGER, {"Host": API, "X-Forwarded-For": "203.0.113.9"})
    assert stranger.json() == {"viewer_host": API, "client": STRANGER}
