"""TASK-6990 (DEC-3990; ADR-163 §5 and its amendment, ADR-168): behind the portal edge the API
reads the viewer's host, not the origin's.

CloudFront sends the internal load balancer's name as `Host` and the portal address the person
used as `X-Forwarded-Host` (the edge function replaces any the viewer sent). Through `create_app()`
and the migrated database, with one app reached from two peers: the load balancer (in
`proxy_trusted_hosts`) and a stranger. From the load balancer the forwarded host chooses the
branding, mints and pins the portal session and is the refresh's own origin; from a stranger a
forwarded host changes nothing and `Host` decides, as before. The host still never decides a
tenant (INV-4): a session minted through the edge on firm A's host is no session on firm B's.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import issue_sign_in_code
from abacus.modules.portal.api import activate_portal_host, add_portal_host
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Seeder, Site

ALB = "10.0.0.5"
STRANGER = "198.51.100.7"
ORIGIN = "internal-abacus-api.example.internal"  # what CloudFront sends as `Host`
COOKIE = "__Host-abacus-portal"
FLAGS = ("portal.sign_in_v2", "portal.home_v2")


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    host: str
    name: str
    site: Site


@dataclass(frozen=True)
class Peers:
    edge: httpx.AsyncClient  # the load balancer, trusted
    stranger: httpx.AsyncClient  # anyone else


@pytest.fixture
async def peers(
    idp: FakeIdentityProvider, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Peers]:
    del idp  # the verifier is configured by the fixture
    monkeypatch.setenv("ABACUS_PROXY_TRUSTED_HOSTS", ALB)
    settings.cache_clear()
    app = create_app()

    def client(peer: str) -> httpx.AsyncClient:
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False, client=(peer, 4000))
        return httpx.AsyncClient(transport=transport, base_url="http://test")

    async with client(ALB) as edge, client(STRANGER) as stranger:
        yield Peers(edge, stranger)


def via_edge(host: str, **extra: str) -> dict[str, str]:
    return {"host": ORIGIN, "x-forwarded-host": host, **extra}


async def _firm(seed: Seeder, label: str) -> Firm:
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'TASK-6990')",
            tenant,
            flag,
        )
    host = f"{label}-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    admin = await seed.person(tenant, "firm_admin")
    name = f"Firm {label} {uuid.uuid4().hex[:6]}"
    await seed.run(
        "INSERT INTO portal_branding (tenant_id, display_name, updated_by) VALUES ($1, $2, $3)",
        tenant,
        name,
        admin.user_id,
    )
    site = await seed.site(tenant, admin.user_id, label)
    return Firm(tenant, host, name, site)


async def _client_email(seed: Seeder, firm: Firm) -> str:
    who = await seed.person(firm.tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client', firm_role = NULL "
        "WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant,
        who.user_id,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'contributor', 'engagement', $3)",
        firm.tenant,
        who.user_id,
        firm.site.engagement_id,
    )
    return cast(str, await seed.value("SELECT email FROM users WHERE id = $1", who.user_id))


async def _sign_in(
    http: httpx.AsyncClient, headers: dict[str, str], email: str
) -> tuple[str, str]:
    """A portal session minted with `headers`: its access token and refresh cookie."""
    http.cookies.clear()
    start = await http.post("/v1/portal/auth/start", json={"email": email}, headers=headers)
    assert start.status_code == 202, start.text
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = await http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers=headers,
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["state"] == "signed_in"
    jar = SimpleCookie()
    jar.load(verified.headers["set-cookie"])
    http.cookies.clear()
    return cast(str, verified.json()["access_token"]), jar[COOKIE].value


async def _home(http: httpx.AsyncClient, firm: Firm, headers: dict[str, str]) -> httpx.Response:
    http.cookies.clear()
    return await http.get(f"/v1/portal/home?scope_id={firm.site.engagement_id}", headers=headers)


async def _branding(http: httpx.AsyncClient, headers: dict[str, str]) -> dict[str, object]:
    response = await http.get("/v1/portal/branding", headers=headers)
    assert response.status_code == 200, response.text
    return cast(dict[str, object], response.json())


# --- branding ----------------------------------------------------------------------------------


async def test_branding_through_the_edge_is_the_forwarded_hosts_firm(
    seed: Seeder, peers: Peers
) -> None:
    a = await _firm(seed, "vh-a")
    edge = await _branding(peers.edge, via_edge(a.host))
    direct = await _branding(peers.stranger, {"host": a.host})
    assert edge["firm_name"] == a.name
    assert edge == direct
    assert (await _branding(peers.edge, {"host": ORIGIN})) != edge  # `Host` alone is no firm


async def test_a_strangers_forwarded_host_never_chooses_the_branding(
    seed: Seeder, peers: Peers
) -> None:
    a = await _firm(seed, "vh-a")
    neutral = await _branding(peers.stranger, {"host": "unknown.portal-example.test"})
    spoofed = await _branding(
        peers.stranger, {"host": "unknown.portal-example.test", "x-forwarded-host": a.host}
    )
    assert neutral["firm_name"] != a.name
    assert spoofed == neutral


# --- pinning -----------------------------------------------------------------------------------


async def test_a_session_minted_through_the_edge_is_pinned_to_the_forwarded_host(
    seed: Seeder, peers: Peers
) -> None:
    a, b = await _firm(seed, "vh-a"), await _firm(seed, "vh-b")
    token, _ = await _sign_in(peers.edge, via_edge(a.host), await _client_email(seed, a))
    bearer = {"authorization": f"Bearer {token}"}
    home = await _home(peers.edge, a, via_edge(a.host, **bearer))
    assert home.status_code == 200, home.text
    assert a.site.marker in home.text
    elsewhere = await _home(peers.edge, a, via_edge(b.host, **bearer))
    anonymous = await _home(peers.edge, a, via_edge(b.host))
    assert elsewhere.status_code == 401
    assert (elsewhere.status_code, elsewhere.text) == (anonymous.status_code, anonymous.text)
    assert (await _home(peers.edge, a, {"host": ORIGIN, **bearer})).status_code == 401


async def test_a_strangers_forwarded_host_never_moves_the_pin(seed: Seeder, peers: Peers) -> None:
    a, b = await _firm(seed, "vh-a"), await _firm(seed, "vh-b")
    token, _ = await _sign_in(peers.stranger, {"host": a.host}, await _client_email(seed, a))
    bearer = {"authorization": f"Bearer {token}"}
    kept = await _home(peers.stranger, a, {"host": a.host, "x-forwarded-host": b.host, **bearer})
    assert kept.status_code == 200, kept.text
    moved = await _home(peers.stranger, a, {"host": b.host, "x-forwarded-host": a.host, **bearer})
    assert moved.status_code == 401


async def test_the_refresh_through_the_edge_checks_the_forwarded_hosts_origin(
    seed: Seeder, peers: Peers
) -> None:
    a, b = await _firm(seed, "vh-a"), await _firm(seed, "vh-b")
    _, cookie = await _sign_in(peers.edge, via_edge(a.host), await _client_email(seed, a))

    async def refresh(host: str, origin: str) -> httpx.Response:
        http = peers.edge
        http.cookies.clear()
        http.cookies.set(COOKIE, cookie)
        response = await http.post(
            "/v1/portal/auth/refresh",
            headers=via_edge(host, origin=f"https://{origin}", **{"x-abacus-csrf": "1"}),
        )
        http.cookies.clear()
        return response

    assert (await refresh(b.host, b.host)).status_code == 401  # another firm's host
    assert (await refresh(a.host, ORIGIN)).status_code != 200  # not the viewer's origin
    refreshed = await refresh(a.host, a.host)
    assert refreshed.status_code == 200, refreshed.text
