"""TASK-6990 (DEC-3990, DEC-3902): the connect-host hand-off's `origin_host` is the viewer's host.

Behind the portal edge the request's `Host` is the internal load balancer's name and the portal
address the person used arrives as `X-Forwarded-Host`. A start from the load balancer (a peer in
`proxy_trusted_hosts`) stores the forwarded host, so the hand-off sends the browser back to the
portal it came from; a start from any other peer stores its own `Host` and never a forwarded one.
Over HTTP through `create_app()` with A-02-T33's world (demo ledger, a client admin, two firms'
portal hosts).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Final

import httpx
import pytest
from fastapi import FastAPI

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus_tools.fakes.identity import FakeIdentityProvider

# A-02-T33's world and its fixtures (the demo ledger is autouse there, so it is named here).
from .test_a02t33_connect_host_handoff import (
    World,
    demo_ledger,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- a fixture, autouse
    world,  # noqa: F401  # pyright: ignore[reportUnusedImport] -- a fixture
)

ALB: Final = "127.0.0.1"  # the in-process client's peer stands for the load balancer
STRANGER: Final = "198.51.100.7"
ORIGIN: Final = "internal-abacus-api.example.internal"  # what CloudFront sends as `Host`


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> FastAPI:
    monkeypatch.setenv("ABACUS_PROXY_TRUSTED_HOSTS", ALB)
    settings.cache_clear()
    return create_app()


@pytest.fixture
async def http(app: FastAPI, idp: FakeIdentityProvider) -> AsyncIterator[httpx.AsyncClient]:
    """This module's `net.http`: the app reached from the load balancer."""
    del idp  # the verifier is configured by the fixture
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False, client=(ALB, 4000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def stranger(app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False, client=(STRANGER, 4000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def test_a_start_through_the_edge_stores_the_forwarded_portal_host(
    world: World,  # noqa: F811
) -> None:
    headers = {**world.firm_headers(ORIGIN), "x-forwarded-host": world.portal_host.upper()}
    handed = await world.start(headers)
    assert await world.stored_origin() == [world.portal_host]
    bounced = await world.http.post(  # the connect host's page, also through the edge
        "/v1/connections/handoff",
        json={"state": handed["state"]},
        headers={"host": ORIGIN, "x-forwarded-host": "connect.portal-example.test"},
    )
    assert bounced.status_code == 200, bounced.text
    assert bounced.json() == {"origin_host": world.portal_host}


async def test_a_strangers_forwarded_host_is_never_stored(
    world: World,  # noqa: F811
    stranger: httpx.AsyncClient,
) -> None:
    headers = {
        **world.firm_headers(world.portal_host),
        "x-forwarded-host": world.other_portal_host,
        "Idempotency-Key": f"t6990-{uuid.uuid4().hex}",
    }
    started = await stranger.post(
        world.start_path, json={"consent_version": 1, "authorized": True}, headers=headers
    )
    assert started.status_code == 201, started.text
    assert await world.stored_origin() == [world.portal_host]
