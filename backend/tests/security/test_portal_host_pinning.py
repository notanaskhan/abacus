# ac-test-author: ayushkbhatia
"""P-08-T25 (security, pen test #1 scope): a portal session is pinned to the firm and host it was
minted on, and the host is a branding hint only (INV-4).

Written from P-08 Story 1.2 and §3.8, SPEC-320 AC-9, `docs/contracts/portal-identity.md` §2 and
§6 and ADR-163 §5, against the HTTP surface: a portal access token or refresh cookie presented on
another firm's portal host, or on a host that is no portal at all, is answered exactly as no
session; a staff session from the firm app on a portal host is refused the same way; and the
`Host` header (or a tenant header) never moves the authorisation tenant. "Exactly as no session"
is checked against the same request with no credential at all, on the same host.

Sessions are minted through the portal's own pre-session routes; the emailed code is taken where
its email takes it (`identity.api.issue_sign_in_code`). Seeding is the superuser's, a fresh firm
per test. `_pinned` is the one judgement every case uses, and `test_the_judgement_catches_*`
proves it fails on a planted cross-host read.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from http.cookies import SimpleCookie
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import uow
from abacus.modules.identity.api import issue_sign_in_code
from abacus.modules.portal.api import activate_portal_host, add_portal_host

from .support import Net, Person, Seeder, Site

COOKIE = "__Host-abacus-portal"
FLAGS = ("portal.sign_in_v2", "portal.home_v2")
APP_HOST = "app.firm-example.test"  # the firm app's host: no portal there


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    host: str
    admin: Person
    site: Site


@dataclass(frozen=True)
class Session:
    token: str
    cookie: str


async def _firm(seed: Seeder, label: str) -> Firm:
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-08-T25')",
            tenant,
            flag,
        )
    host = f"{label}-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    admin = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, admin.user_id, label)
    return Firm(tenant, host, admin, site)


async def _client(seed: Seeder, firm: Firm, *, user: Person | None = None) -> tuple[Person, str]:
    """A client person of the firm with a `contributor` grant on its engagement (no MFA floor)."""
    who = user or await seed.person(firm.tenant)
    if user is not None:  # a person of another firm becomes a client here as well
        await seed.run(
            "INSERT INTO memberships (tenant_id, user_id, status) VALUES ($1, $2, 'active')",
            firm.tenant,
            who.user_id,
        )
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
    email = cast(str, await seed.value("SELECT email FROM users WHERE id = $1", who.user_id))
    return who, email


async def _sign_in(http: httpx.AsyncClient, host: str, email: str) -> Session:
    start = await http.post("/v1/portal/auth/start", json={"email": email}, headers={"host": host})
    assert start.status_code == 202, start.text
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = await http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers={"host": host},
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["state"] == "signed_in"
    jar = SimpleCookie()
    jar.load(verified.headers["set-cookie"])
    http.cookies.clear()
    return Session(cast(str, verified.json()["access_token"]), jar[COOKIE].value)


def _bearer(token: str, host: str, **extra: str) -> dict[str, str]:
    return {"host": host, "authorization": f"Bearer {token}", **extra}


async def _get(http: httpx.AsyncClient, path: str, headers: dict[str, str]) -> httpx.Response:
    http.cookies.clear()
    return await http.get(path, headers=headers)


async def _refresh(http: httpx.AsyncClient, host: str, cookie: str | None) -> httpx.Response:
    http.cookies.clear()
    if cookie is not None:
        http.cookies.set(COOKIE, cookie)
    response = await http.post(
        "/v1/portal/auth/refresh",
        headers={"host": host, "origin": f"https://{host}", "x-abacus-csrf": "1"},
    )
    http.cookies.clear()
    return response


def _pinned(presented: httpx.Response, anonymous: httpx.Response, *markers: str) -> list[str]:
    """What is wrong with `presented` (a credential on a host it wasn't minted for), judged
    against `anonymous` (the same request with no credential): it must be a 401 with the same
    body, and carry nothing of the other firm."""
    problems: list[str] = []
    if presented.status_code != 401:
        problems.append(f"status {presented.status_code}, not 401")
    if (presented.status_code, presented.text) != (anonymous.status_code, anonymous.text):
        problems.append("answered differently from no session")
    problems += [f"leaks {m}" for m in markers if m in presented.text]
    return problems


def _home(firm: Firm) -> str:
    return f"/v1/portal/home?scope_id={firm.site.engagement_id}"


# --- Story 1.2: a portal session works only on the host it was minted on ------------------------


async def test_story1_2_a_portal_session_reads_its_own_firms_home_on_its_own_host(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    a = await _firm(seed, "pin-a")
    _, email = await _client(seed, a)
    session = await _sign_in(http, a.host, email)
    home = await _get(http, _home(a), _bearer(session.token, a.host))
    assert home.status_code == 200, home.text
    assert a.site.marker in home.text  # the scope's own client, by name


async def test_story1_2_the_token_on_another_firms_portal_host_is_no_session(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    a, b = await _firm(seed, "pin-a"), await _firm(seed, "pin-b")
    _, email = await _client(seed, a)
    session = await _sign_in(http, a.host, email)
    for path in (_home(a), _home(b), "/v1/me"):
        presented = await _get(http, path, _bearer(session.token, b.host))
        anonymous = await _get(http, path, {"host": b.host})
        assert _pinned(presented, anonymous, a.site.marker, b.site.marker) == [], path


async def test_story1_2_a_person_who_is_a_client_of_both_firms_is_pinned_to_the_minting_host(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    """The cross-tenant host swap: one person, a client of firms A and B; a session from A's host
    is no session on B's, though the person could sign in there."""
    a, b = await _firm(seed, "swap-a"), await _firm(seed, "swap-b")
    who, email = await _client(seed, a)
    await _client(seed, b, user=who)
    session = await _sign_in(http, a.host, email)
    presented = await _get(http, _home(b), _bearer(session.token, b.host))
    anonymous = await _get(http, _home(b), {"host": b.host})
    assert _pinned(presented, anonymous, b.site.marker) == []
    # On its own host, the session still reads A and never B's scope.
    assert (await _get(http, _home(a), _bearer(session.token, a.host))).status_code == 200
    swapped = await _get(http, _home(b), _bearer(session.token, a.host))
    assert swapped.status_code in (401, 404), swapped.text
    assert b.site.marker not in swapped.text
    # B's own session works on B's host: the person was refused for the host, not for B.
    own = await _sign_in(http, b.host, email)
    assert (await _get(http, _home(b), _bearer(own.token, b.host))).status_code == 200


async def test_story1_2_a_tenant_header_never_moves_the_portal_sessions_firm(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    a, b = await _firm(seed, "hdr-a"), await _firm(seed, "hdr-b")
    who, email = await _client(seed, a)
    await _client(seed, b, user=who)
    session = await _sign_in(http, a.host, email)
    for tenant in (b.tenant, uuid.uuid4()):
        response = await _get(
            http, _home(b), _bearer(session.token, a.host, **{"x-abacus-tenant": str(tenant)})
        )
        assert response.status_code in (401, 403, 404), response.text
        assert b.site.marker not in response.text


async def test_story1_2_the_token_on_the_firm_app_host_is_no_session(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    a = await _firm(seed, "app")
    _, email = await _client(seed, a)
    session = await _sign_in(http, a.host, email)
    for path in (_home(a), "/v1/me"):
        presented = await _get(http, path, _bearer(session.token, APP_HOST))
        anonymous = await _get(http, path, {"host": APP_HOST})
        assert _pinned(presented, anonymous, a.site.marker) == [], path


async def test_story1_2_the_refresh_cookie_on_another_firms_host_is_no_session(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    a, b = await _firm(seed, "rf-a"), await _firm(seed, "rf-b")
    _, email = await _client(seed, a)
    session = await _sign_in(http, a.host, email)
    presented = await _refresh(http, b.host, session.cookie)
    anonymous = await _refresh(http, b.host, None)
    assert _pinned(presented, anonymous, a.site.marker) == []
    jar = SimpleCookie()
    jar.load(presented.headers.get("set-cookie", ""))
    assert COOKIE not in jar or jar[COOKIE].value in ("", '""')  # no new session, at most a clear
    # Refused on B, the cookie still refreshes on A: the refusal was the host's, not a reuse.
    assert (await _refresh(http, a.host, session.cookie)).status_code == 200


# --- Story 1.2, the reverse: a staff session on a portal host ------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "TASK-1230 (#386; held open: DEC-212 gives this refusal to P-08-T25, and the fix "
        "is in identity authentication, outside this row's fix scope): "
        "a staff (provider) token on a portal host is served as the staff "
        "session (/v1/me 200, other routes 404), not refused as no session (401 "
        "unauthenticated); ADR-163 §5, ADR-168 §3 and consequences, SPEC-320 AC-9"
    ),
)
async def test_story1_2_a_staff_session_on_a_portal_host_is_refused_like_no_session(
    seed: Seeder, http: httpx.AsyncClient, net: Net
) -> None:
    a = await _firm(seed, "staff")
    staff_token = net.idp.token(a.admin.subject, mfa=True)
    found: dict[str, list[str]] = {}
    for path in (_home(a), "/v1/me", f"/v1/clients/{a.site.client_id}/contacts"):
        presented = await _get(http, path, _bearer(staff_token, a.host))
        anonymous = await _get(http, path, {"host": a.host})
        found[path.split("?")[0]] = _pinned(presented, anonymous, a.site.marker)
    assert found == {p.split("?")[0]: [] for p in found}


async def test_story1_2_a_portal_token_is_not_a_staff_session_on_the_firm_app(
    seed: Seeder, http: httpx.AsyncClient
) -> None:
    """The reverse of the reverse: the firm app's own routes refuse a portal token."""
    a = await _firm(seed, "rev")
    _, email = await _client(seed, a)
    session = await _sign_in(http, a.host, email)
    path = f"/v1/engagements/{a.site.engagement_id}"
    presented = await _get(http, path, _bearer(session.token, APP_HOST))
    anonymous = await _get(http, path, {"host": APP_HOST})
    assert _pinned(presented, anonymous, a.site.marker) == []


# --- The judgement itself fails on a planted cross-host read ------------------------------------


def _response(status: int, body: str) -> httpx.Response:
    return httpx.Response(status, text=body, request=httpx.Request("GET", "http://test/"))


def test_the_judgement_catches_a_planted_cross_host_read() -> None:
    anonymous = _response(401, '{"detail":"unauthenticated"}')
    assert _pinned(_response(401, '{"detail":"unauthenticated"}'), anonymous, "Client x") == []
    leaked = _response(200, '{"scope":{"label":"Client x"}}')
    assert _pinned(leaked, anonymous, "Client x") == [
        "status 200, not 401",
        "answered differently from no session",
        "leaks Client x",
    ]
    told_apart = _response(401, '{"detail":"session_host_mismatch"}')
    assert _pinned(told_apart, anonymous) == ["answered differently from no session"]
