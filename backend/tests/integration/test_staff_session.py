"""P-01-T09 (ADR-165; DEC-140): the staff session BFF against a real Postgres.

AC 5.1.2 (callback and session), AC 5.1.4 (refresh, reuse, timeouts) and AC 2.1.6 (sign-out).
The provider is an in-process `StaffIdp` that signs with `FakeIdentityProvider`, so the access
token is verified exactly as a bearer token is. The API runs as the app role, so every definer
grant is exercised. Seed rows and checks go through the superuser.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Protocol, cast
from urllib.parse import parse_qs, urlparse

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import configure_engine, dispose_engine
from abacus.modules.identity.api import configure_verifier, reset_verifier
from abacus.modules.identity.staff_session import (
    COOKIE_NAME,
    ProviderRefused,
    ProviderTokens,
    configure_staff_idp,
)
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

ORIGIN = "https://app.test"
REFRESH_HEADERS = {"X-Abacus-CSRF": "1", "Origin": ORIGIN}


class Migrated(Protocol):
    app_url: str
    identity_url: str
    superuser_dsn: str


class FakeStaffIdp:
    """The provider half: codes name a subject and whether they did MFA."""

    def __init__(self, signer: FakeIdentityProvider) -> None:
        self.signer = signer
        self.codes: dict[str, tuple[str, bool]] = {}
        self.refresh_tokens: dict[str, str] = {}
        self.revoked: list[str] = []
        self.challenges: list[str] = []

    def authorize_url(
        self, *, state: str, challenge: str, redirect_uri: str, reauthenticate: bool
    ) -> str:
        self.challenges.append(challenge)
        prompt = "&prompt=login" if reauthenticate else ""
        return (
            f"https://idp.test/authorize?state={state}&code_challenge={challenge}"
            f"&code_challenge_method=S256&redirect_uri={redirect_uri}{prompt}"
        )

    def issue(self, subject: str, *, mfa: bool = True) -> str:
        code = uuid.uuid4().hex
        self.codes[code] = (subject, mfa)
        return code

    def _tokens(self, subject: str, mfa: bool) -> ProviderTokens:
        refresh = uuid.uuid4().hex
        self.refresh_tokens[refresh] = subject
        return ProviderTokens(self.signer.token(subject, mfa=mfa, expires_in=600), 600, refresh)

    async def exchange(self, *, code: str, verifier: str, redirect_uri: str) -> ProviderTokens:
        assert redirect_uri == f"{ORIGIN}/v1/auth/callback"
        assert 43 <= len(verifier) <= 128
        if code not in self.codes:
            raise ProviderRefused("authorization_code")
        subject, mfa = self.codes.pop(code)
        return self._tokens(subject, mfa)

    async def refresh(self, refresh_token: str) -> ProviderTokens:
        subject = self.refresh_tokens.pop(refresh_token, None)
        if subject is None:
            raise ProviderRefused("refresh_token")
        return self._tokens(subject, True)

    async def revoke(self, refresh_token: str) -> None:
        self.revoked.append(refresh_token)


async def _value(dsn: str, sql: str, *args: object) -> object:
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


async def _run(dsn: str, sql: str, *args: object) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        await conn.execute(sql, *args)
    finally:
        await conn.close()


@pytest.fixture
def dsn(migrated_db: Migrated) -> str:
    return _plain(migrated_db.superuser_dsn)


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.fixture(autouse=True)
async def engines(migrated_db: Migrated, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    monkeypatch.setenv("ABACUS_WEB_ORIGIN", ORIGIN)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def idp() -> Iterator[FakeStaffIdp]:
    signer = FakeIdentityProvider()
    configure_verifier(signer.verifier())
    fake = FakeStaffIdp(signer)
    configure_staff_idp(fake)
    yield fake
    configure_staff_idp(None)
    reset_verifier()


@pytest.fixture
async def http(idp: FakeStaffIdp) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        yield client


async def _member(dsn: str) -> tuple[uuid.UUID, uuid.UUID, str]:
    """A firm, a user with an active membership; (tenant, user, subject)."""
    tenant_id, subject = uuid.uuid4(), f"sub-{uuid.uuid4().hex}"
    await _run(dsn, "INSERT INTO firms (tenant_id, name) VALUES ($1, $2)", tenant_id, "Firm")
    user_id = cast(
        uuid.UUID,
        await _value(
            dsn,
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            ISSUER,
            subject,
            f"{subject}@example.test",
            "Staff Person",
        ),
    )
    await _run(
        dsn,
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
        "VALUES ($1, $2, NULL, 'active')",
        tenant_id,
        user_id,
    )
    return tenant_id, user_id, subject


def _cookie_header(response: httpx.Response) -> str:
    [header] = [h for h in response.headers.get_list("set-cookie") if h.startswith(COOKIE_NAME)]
    return header


def _cookie_value(response: httpx.Response) -> str:
    return _cookie_header(response).split(";", 1)[0].split("=", 1)[1]


def _send(cookie: str) -> dict[str, str]:
    return {"Cookie": f"{COOKIE_NAME}={cookie}"}


async def _sign_in(
    http: httpx.AsyncClient, idp: FakeStaffIdp, subject: str, *, mfa: bool = True, to: str = "/x"
) -> httpx.Response:
    started = await http.get("/v1/auth/sign-in", params={"return_to": to})
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    response = await http.get(
        "/v1/auth/callback", params={"code": idp.issue(subject, mfa=mfa), "state": state}
    )
    http.cookies.clear()
    return response


async def _refresh(http: httpx.AsyncClient, cookie: str) -> httpx.Response:
    response = await http.post("/v1/auth/refresh", headers={**REFRESH_HEADERS, **_send(cookie)})
    http.cookies.clear()
    return response


async def _audits(dsn: str, action: str, target: object) -> int:
    return cast(
        int,
        await _value(
            dsn,
            "SELECT count(*) FROM audit_events WHERE action = $1 AND target_id = $2",
            action,
            str(target),
        ),
    )


# --- AC 5.1.2: sign-in and callback --------------------------------------------------------------


async def test_ac512_sign_in_redirects_to_the_provider_with_state_and_pkce(
    http: httpx.AsyncClient, idp: FakeStaffIdp
) -> None:
    response = await http.get("/v1/auth/sign-in", params={"return_to": "/engagements"})
    assert response.status_code == 302
    assert response.headers["cache-control"] == "no-store"
    query = parse_qs(urlparse(response.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == idp.challenges
    assert len(query["state"][0]) >= 32
    assert query["redirect_uri"] == [f"{ORIGIN}/v1/auth/callback"]


async def test_ac515_step_up_forces_reauthentication(
    http: httpx.AsyncClient, idp: FakeStaffIdp
) -> None:
    response = await http.get("/v1/auth/sign-in", params={"reauthenticate": "true"})
    assert parse_qs(urlparse(response.headers["location"]).query)["prompt"] == ["login"]


async def test_ac512_callback_starts_a_session_with_host_cookie_flags(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    tenant_id, user_id, subject = await _member(dsn)
    response = await _sign_in(http, idp, subject, to="/engagements")
    assert response.status_code == 302
    assert response.headers["location"] == f"{ORIGIN}/signin/callback?to=%2Fengagements"
    header = _cookie_header(response)
    flags = {part.strip().lower() for part in header.split(";")[1:]}
    assert {"httponly", "secure", "samesite=strict", "path=/"} <= flags
    assert not any(flag.startswith("domain") for flag in flags)
    session_id = await _value(
        dsn, "SELECT id FROM auth_sessions WHERE user_id = $1 AND ended_at IS NULL", user_id
    )
    assert session_id is not None
    assert await _value(
        dsn, "SELECT mfa_at IS NOT NULL FROM auth_sessions WHERE id = $1", session_id
    )
    sealed = await _value(
        dsn, "SELECT provider_refresh_enc FROM auth_sessions WHERE id = $1", session_id
    )
    assert isinstance(sealed, bytes)
    assert not any(token.encode() in sealed for token in idp.refresh_tokens)
    stored = await _value(
        dsn, "SELECT cookie_sha256 FROM auth_session_cookies WHERE session_id = $1", session_id
    )
    assert stored != _cookie_value(response)  # only a SHA-256 is kept
    assert (
        await _value(
            dsn,
            "SELECT count(*) FROM audit_events WHERE action = 'session.started' "
            "AND tenant_id = $1 AND target_id = $2",
            tenant_id,
            str(session_id),
        )
        == 1
    )


async def test_ac512_a_session_without_a_second_factor_is_refused(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, user_id, subject = await _member(dsn)
    response = await _sign_in(http, idp, subject, mfa=False)
    assert (
        response.headers["location"] == f"{ORIGIN}/signin/callback?error=mfa_required_at_sign_in"
    )
    assert "max-age=0" in _cookie_header(
        response
    ).lower() or 'abacus-session=""' in _cookie_header(response)
    assert await _value(dsn, "SELECT count(*) FROM auth_sessions WHERE user_id = $1", user_id) == 0
    assert await _audits(dsn, "auth.sign_in_refused", user_id) == 1


async def test_ac512_an_unknown_user_is_refused(
    http: httpx.AsyncClient, idp: FakeStaffIdp
) -> None:
    response = await _sign_in(http, idp, f"stranger-{uuid.uuid4().hex}")
    assert response.headers["location"] == f"{ORIGIN}/signin/callback?error=unknown_staff_user"


async def test_ac512_state_is_single_use_and_must_be_known(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, _, subject = await _member(dsn)
    started = await http.get("/v1/auth/sign-in")
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    first = await http.get(
        "/v1/auth/callback", params={"code": idp.issue(subject), "state": state}
    )
    assert "to=" in first.headers["location"]
    http.cookies.clear()
    for params in (
        {"code": idp.issue(subject), "state": state},
        {"code": idp.issue(subject), "state": "made-up"},
        {"code": idp.issue(subject)},
    ):
        again = await http.get("/v1/auth/callback", params=params)
        assert again.headers["location"] == f"{ORIGIN}/signin/callback?error=sign_in_failed"


@pytest.mark.parametrize("unsafe", ["//evil.test/x", "/\\evil.test", "https://evil.test/"])
async def test_ac512_an_unsafe_return_path_lands_on_the_root(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str, unsafe: str
) -> None:
    _, _, subject = await _member(dsn)
    response = await _sign_in(http, idp, subject, to=unsafe)
    assert response.headers["location"] == f"{ORIGIN}/signin/callback?to=%2F"


# --- AC 5.1.4: refresh, reuse and timeouts -------------------------------------------------------


async def test_ac514_refresh_rotates_the_cookie_and_returns_an_access_token(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, _, subject = await _member(dsn)
    cookie = _cookie_value(await _sign_in(http, idp, subject))
    response = await _refresh(http, cookie)
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    assert body["expires_in"] == 600
    assert idp.signer.verifier().verify(body["access_token"]).subject == subject
    assert _cookie_value(response) != cookie
    me = await http.get("/v1/me", headers={"Authorization": f"Bearer {body['access_token']}"})
    assert me.status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        {"Origin": ORIGIN},
        {"X-Abacus-CSRF": "1"},
        {"X-Abacus-CSRF": "1", "Origin": "https://evil.test"},
        {"X-Abacus-CSRF": "yes", "Origin": ORIGIN},
    ],
)
async def test_ac514_refresh_needs_the_csrf_header_and_the_app_origin(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str, headers: dict[str, str]
) -> None:
    _, _, subject = await _member(dsn)
    cookie = _cookie_value(await _sign_in(http, idp, subject))
    response = await http.post("/v1/auth/refresh", headers={**headers, **_send(cookie)})
    assert (response.status_code, response.json()) == (403, {"detail": "forbidden"})
    assert (await _refresh(http, cookie)).status_code == 200  # the cookie was not spent


async def test_ac514_a_reused_cookie_revokes_the_session(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, user_id, subject = await _member(dsn)
    first = _cookie_value(await _sign_in(http, idp, subject))
    second = _cookie_value(await _refresh(http, first))
    reused = await _refresh(http, first)
    assert (reused.status_code, reused.json()) == (401, {"detail": "session_refresh_reused"})
    session_id = await _value(dsn, "SELECT id FROM auth_sessions WHERE user_id = $1", user_id)
    assert (
        await _value(dsn, "SELECT end_reason FROM auth_sessions WHERE id = $1", session_id)
        == "reuse_detected"
    )
    assert await _audits(dsn, "session.refresh_reused", session_id) == 1
    after = await _refresh(http, second)  # the live value dies with the session
    assert (after.status_code, after.json()) == (401, {"detail": "session_expired"})


_PAST_LIMIT = {
    "idle": "UPDATE auth_sessions SET idle_expires_at = now() - interval '1 second' "
    "WHERE user_id = $1",
    "absolute": "UPDATE auth_sessions SET absolute_expires_at = now() - interval '1 second' "
    "WHERE user_id = $1",
}


@pytest.mark.parametrize("reason", ["idle", "absolute"])
async def test_ac514_a_session_past_its_limit_is_expired(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str, reason: str
) -> None:
    _, user_id, subject = await _member(dsn)
    cookie = _cookie_value(await _sign_in(http, idp, subject))
    await _run(dsn, _PAST_LIMIT[reason], user_id)
    response = await _refresh(http, cookie)
    assert (response.status_code, response.json()) == (401, {"detail": "session_expired"})
    assert (
        await _value(dsn, "SELECT end_reason FROM auth_sessions WHERE user_id = $1", user_id)
        == reason
    )


async def test_ac514_the_limits_are_dec_140(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, user_id, subject = await _member(dsn)
    await _sign_in(http, idp, subject)
    idle, absolute = await _limits(dsn, user_id)
    assert 29 * 60 < idle <= 30 * 60
    assert 11.9 * 3600 < absolute <= 12 * 3600


async def _limits(dsn: str, user_id: uuid.UUID) -> tuple[float, float]:
    conn = await asyncpg.connect(dsn)
    try:
        row = await conn.fetchrow(
            "SELECT extract(epoch FROM idle_expires_at - created_at) AS idle, "
            "extract(epoch FROM absolute_expires_at - created_at) AS absolute "
            "FROM auth_sessions WHERE user_id = $1",
            user_id,
        )
    finally:
        await conn.close()
    assert row is not None
    return float(row["idle"]), float(row["absolute"])


async def test_ac514_an_unknown_cookie_is_expired(
    http: httpx.AsyncClient, idp: FakeStaffIdp
) -> None:
    response = await _refresh(http, "not-a-session")
    assert (response.status_code, response.json()) == (401, {"detail": "session_expired"})


async def test_ac514_a_provider_refusal_ends_the_session(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, user_id, subject = await _member(dsn)
    cookie = _cookie_value(await _sign_in(http, idp, subject))
    idp.refresh_tokens.clear()  # the provider session was revoked elsewhere
    response = await _refresh(http, cookie)
    assert response.status_code == 401
    assert (
        await _value(dsn, "SELECT end_reason FROM auth_sessions WHERE user_id = $1", user_id)
        == "revoked"
    )


# --- AC 2.1.6: sign-out --------------------------------------------------------------------------


async def test_ac216_sign_out_ends_the_session_and_the_old_cookie_no_longer_refreshes(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, user_id, subject = await _member(dsn)
    cookie = _cookie_value(await _sign_in(http, idp, subject))
    token = idp.signer.token(subject, mfa=True)
    response = await http.post(
        "/v1/auth/sign-out", headers={"Authorization": f"Bearer {token}", **_send(cookie)}
    )
    http.cookies.clear()
    assert (response.status_code, response.json()) == (200, {"ended": True})
    assert "max-age=0" in _cookie_header(
        response
    ).lower() or 'abacus-session=""' in _cookie_header(response)
    assert idp.revoked  # the provider is told
    session_id = await _value(dsn, "SELECT id FROM auth_sessions WHERE user_id = $1", user_id)
    assert (
        await _value(dsn, "SELECT end_reason FROM auth_sessions WHERE id = $1", session_id)
        == "sign_out"
    )
    assert await _audits(dsn, "session.ended", session_id) == 1
    replay = await _refresh(http, cookie)
    assert (replay.status_code, replay.json()) == (401, {"detail": "session_expired"})


async def test_ac216_sign_out_never_ends_someone_elses_session(
    http: httpx.AsyncClient, idp: FakeStaffIdp, dsn: str
) -> None:
    _, _, owner = await _member(dsn)
    _, _, other = await _member(dsn)
    cookie = _cookie_value(await _sign_in(http, idp, owner))
    token = idp.signer.token(other, mfa=True)
    response = await http.post(
        "/v1/auth/sign-out", headers={"Authorization": f"Bearer {token}", **_send(cookie)}
    )
    http.cookies.clear()
    assert response.json() == {"ended": False}
    assert (await _refresh(http, cookie)).status_code == 200


async def test_ac216_sign_out_needs_a_bearer_token(
    http: httpx.AsyncClient, idp: FakeStaffIdp
) -> None:
    assert (await http.post("/v1/auth/sign-out")).status_code == 401


# --- ADR-165: the stores are reachable only through the definers ---------------------------------


_READ = {
    "auth_login_states": "SELECT * FROM auth_login_states",
    "auth_sessions": "SELECT * FROM auth_sessions",
    "auth_session_cookies": "SELECT * FROM auth_session_cookies",
}


@pytest.mark.parametrize("table", sorted(_READ))
async def test_adr165_the_app_role_cannot_read_the_session_tables(
    migrated_db: Migrated, table: str
) -> None:
    conn = await asyncpg.connect(_plain(migrated_db.app_url))
    try:
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await conn.fetch(_READ[table])
    finally:
        await conn.close()
