"""G-04-T14 (TASK-8548; DEC-5532): the console BFF on the staff issuer, against Postgres.

- A sign-in goes to the staff provider with server-side state and PKCE; the callback sets the
  `__Host-abacus-console` cookie (Secure, HttpOnly, SameSite=Strict) and lands on the console's
  `/signin/callback` with a same-origin path only.
- A staff token without MFA, or without a console role, starts no session (`?error=` instead).
- A refresh needs the cookie, `X-Abacus-CSRF: 1` and the console's own Origin; it rotates the
  cookie, and a rotated-out value presented again ends the whole session.
- Signing out ends the session behind the cookie; its value no longer refreshes.
- Every answer is `Cache-Control: no-store`.

The provider is an in-process `StaffIdp` signing staff tokens with `FakeIdentityProvider`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Protocol
from urllib.parse import parse_qs, urlparse

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.identity.platform_staff_session import (
    COOKIE_NAME,
    configure_platform_staff_idp,
)
from abacus.modules.identity.staff_session import ProviderRefused, ProviderTokens
from abacus.modules.identity.tokens import configure_staff_verifier
from abacus_tools.fakes.identity import FakeIdentityProvider

CONSOLE = "https://console.test"
HEADERS = {"X-Abacus-CSRF": "1", "Origin": CONSOLE}

pytestmark = pytest.mark.asyncio


class Migrated(Protocol):
    app_url: str
    identity_url: str
    superuser_dsn: str


class StaffIdp:
    """Codes name a staff subject, whether it did MFA, and its console roles."""

    def __init__(self, signer: FakeIdentityProvider) -> None:
        self.signer = signer
        self.codes: dict[str, tuple[str, bool, list[str]]] = {}
        self.refresh_tokens: dict[str, tuple[str, bool, list[str]]] = {}

    def authorize_url(
        self, *, state: str, challenge: str, redirect_uri: str, reauthenticate: bool
    ) -> str:
        return f"https://staff-idp.test/authorize?state={state}&code_challenge={challenge}"

    def issue(self, subject: str, *, mfa: bool = True, roles: list[str] | None = None) -> str:
        code = uuid.uuid4().hex
        self.codes[code] = (subject, mfa, ["platform_admin"] if roles is None else roles)
        return code

    def _tokens(self, subject: str, mfa: bool, roles: list[str]) -> ProviderTokens:
        refresh = uuid.uuid4().hex
        self.refresh_tokens[refresh] = (subject, mfa, roles)
        token = self.signer.token(subject, mfa=mfa, expires_in=600, platform_roles=roles)
        return ProviderTokens(token, 600, refresh)

    async def exchange(self, *, code: str, verifier: str, redirect_uri: str) -> ProviderTokens:
        if code not in self.codes:
            raise ProviderRefused("authorization_code")
        return self._tokens(*self.codes.pop(code))

    async def refresh(self, refresh_token: str) -> ProviderTokens:
        found = self.refresh_tokens.pop(refresh_token, None)
        if found is None:
            raise ProviderRefused("refresh_token")
        return self._tokens(*found)

    async def revoke(self, refresh_token: str) -> None:
        return None


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    monkeypatch.setenv("ABACUS_CONSOLE_ORIGIN", CONSOLE)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def idp() -> Iterator[StaffIdp]:
    signer = FakeIdentityProvider(issuer="https://staff-idp.test", audience="console")
    configure_staff_verifier(signer.verifier())
    fake = StaffIdp(signer)
    configure_platform_staff_idp(fake)
    yield fake
    configure_platform_staff_idp(None)
    configure_staff_verifier(None)


@pytest.fixture
async def http(idp: StaffIdp) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url=CONSOLE) as client:
        yield client


async def _sign_in(
    http: httpx.AsyncClient, idp: StaffIdp, code: str, return_to: str = "/tenants"
) -> httpx.Response:
    started = await http.get("/v1/platform/auth/sign-in", params={"return_to": return_to})
    assert started.status_code == 302
    assert started.headers["cache-control"] == "no-store"
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    return await http.get("/v1/platform/auth/callback", params={"code": code, "state": state})


async def test_a_console_staff_member_signs_in_and_lands_on_a_safe_path(
    http: httpx.AsyncClient, idp: StaffIdp
) -> None:
    landed = await _sign_in(http, idp, idp.issue("staff-rowan"))
    assert landed.status_code == 302
    assert landed.headers["location"] == f"{CONSOLE}/signin/callback?to=%2Ftenants"
    cookie = landed.headers["set-cookie"]
    assert cookie.startswith(f"{COOKIE_NAME}=")
    for attribute in ("Secure", "HttpOnly", "SameSite=strict", "Path=/"):
        assert attribute.lower() in cookie.lower(), attribute
    other = await _sign_in(http, idp, idp.issue("staff-rowan"), return_to="//evil.test/x")
    assert other.headers["location"] == f"{CONSOLE}/signin/callback?to=%2F"


@pytest.mark.parametrize(
    ("mfa", "roles", "code"),
    [(False, ["platform_admin"], "mfa_required_at_sign_in"), (True, [], "no_console_role")],
)
async def test_no_session_without_mfa_or_a_console_role(
    http: httpx.AsyncClient, idp: StaffIdp, mfa: bool, roles: list[str], code: str
) -> None:
    landed = await _sign_in(http, idp, idp.issue("staff-x", mfa=mfa, roles=roles))
    assert landed.headers["location"] == f"{CONSOLE}/signin/callback?error={code}"
    assert http.cookies.get(COOKIE_NAME) in (None, "")


async def test_refresh_rotates_and_a_reused_cookie_ends_the_session(
    http: httpx.AsyncClient, idp: StaffIdp
) -> None:
    await _sign_in(http, idp, idp.issue("staff-rowan"))
    first = http.cookies.get(COOKIE_NAME)
    assert first
    ok = await http.post("/v1/platform/auth/refresh", headers=HEADERS)
    assert ok.status_code == 200 and ok.json()["expires_in"] == 600
    assert ok.headers["cache-control"] == "no-store"
    second = http.cookies.get(COOKIE_NAME)
    assert second and second != first
    reused = await http.post(
        "/v1/platform/auth/refresh", headers=HEADERS, cookies={COOKIE_NAME: first}
    )
    assert reused.status_code == 401 and reused.json()["detail"] == "session_refresh_reused"
    dead = await http.post(
        "/v1/platform/auth/refresh", headers=HEADERS, cookies={COOKIE_NAME: second}
    )
    assert dead.status_code == 401 and dead.json()["detail"] == "session_expired"


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": CONSOLE},
        {"X-Abacus-CSRF": "1", "Origin": "https://app.test"},
        {"X-Abacus-CSRF": "1"},
    ],
)
async def test_refresh_needs_the_csrf_header_and_the_consoles_origin(
    http: httpx.AsyncClient, idp: StaffIdp, headers: dict[str, str]
) -> None:
    await _sign_in(http, idp, idp.issue("staff-rowan"))
    refused = await http.post("/v1/platform/auth/refresh", headers=headers)
    assert refused.status_code == 403


async def test_sign_out_ends_the_session(http: httpx.AsyncClient, idp: StaffIdp) -> None:
    await _sign_in(http, idp, idp.issue("staff-rowan"))
    cookie = http.cookies.get(COOKIE_NAME)
    out = await http.post("/v1/platform/auth/sign-out", headers=HEADERS)
    assert out.status_code == 200 and out.json() == {"ended": True}
    again = await http.post(
        "/v1/platform/auth/refresh", headers=HEADERS, cookies={COOKIE_NAME: cookie or ""}
    )
    assert again.status_code == 401
