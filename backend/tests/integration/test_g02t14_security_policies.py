"""G-02-T14 (SPEC-349 AC-15, AC-17 to AC-20; DEC-524 to DEC-531): what the BFF enforces from the
firm's security policies, against a real Postgres as the app role.

- AC-17: an idle session past the firm's limit fails its next refresh and must sign in again;
  the strictest of the person's firms applies, from the session's own times.
- AC-15: with Require SSO on, a sign-in by any other method is refused (`sso_required`), and so
  is a method the provider did not report; an SSO sign-in passes.
- AC-18: the exempt account passes with a passkey only, and its sign-in stamps "last tested".
- AC-20: a session signed out of one firm answers 401 there and still works in its other firm.
- AC-19: a new portal session lasts the firm's portal length, never over 8 hours.
- The year-old purge, and the policies' audit values from the event's own references.

The provider is an in-process `StaffIdp` signing with `FakeIdentityProvider` (no network).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime
from typing import Protocol, cast
from urllib.parse import parse_qs, urlparse

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity import security_policies
from abacus.modules.identity.api import AuthContext, configure_verifier, reset_verifier
from abacus.modules.identity.staff_session import (
    COOKIE_NAME,
    ProviderRefused,
    ProviderTokens,
    auth_method_of,
    configure_staff_idp,
)
from abacus.modules.platform.audit_resolvers import security_policy_values
from abacus.modules.platform.audit_slots import AuditEventRef
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

ORIGIN = "https://app.test"
REFRESH_HEADERS = {"X-Abacus-CSRF": "1", "Origin": ORIGIN}
_NOW = datetime.now(UTC)


class Migrated(Protocol):
    app_url: str
    identity_url: str
    superuser_dsn: str


class MethodIdp:
    """The provider half: codes name a subject and the method the provider reports."""

    def __init__(self, signer: FakeIdentityProvider) -> None:
        self.signer = signer
        self.codes: dict[str, tuple[str, str | None]] = {}
        self.refresh_tokens: dict[str, tuple[str, str | None]] = {}

    def authorize_url(
        self, *, state: str, challenge: str, redirect_uri: str, reauthenticate: bool
    ) -> str:
        return f"https://idp.test/authorize?state={state}&code_challenge={challenge}"

    def issue(self, subject: str, method: str | None) -> str:
        code = uuid.uuid4().hex
        self.codes[code] = (subject, method)
        return code

    def _tokens(self, subject: str, method: str | None) -> ProviderTokens:
        refresh = uuid.uuid4().hex
        self.refresh_tokens[refresh] = (subject, method)
        token = self.signer.token(subject, mfa=True, expires_in=600)
        return ProviderTokens(token, 600, refresh, auth_method_of(method))

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


def _plain(url: str) -> str:
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


@pytest.fixture
def dsn(migrated_db: Migrated) -> str:
    return _plain(migrated_db.superuser_dsn)


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
def idp() -> Iterator[MethodIdp]:
    signer = FakeIdentityProvider()
    configure_verifier(signer.verifier())
    fake = MethodIdp(signer)
    configure_staff_idp(fake)
    yield fake
    configure_staff_idp(None)
    reset_verifier()


@pytest.fixture
async def http(idp: MethodIdp) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url=ORIGIN) as client:
        yield client


async def _value(dsn: str, sql: str, *args: object) -> object:
    conn = await asyncpg.connect(dsn)
    try:
        return await conn.fetchval(sql, *args)
    finally:
        await conn.close()


async def _run(dsn: str, sql: str, *args: object, actor: uuid.UUID | None = None) -> None:
    """As the superuser; `actor` sets the person the policy triggers expect."""
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            if actor is not None:
                await conn.execute(
                    "SELECT set_config('app.actor_kind', 'human', true), "
                    "set_config('app.actor_id', $1, true)",
                    str(actor),
                )
            await conn.execute(sql, *args)
    finally:
        await conn.close()


async def _firm(dsn: str) -> uuid.UUID:
    tenant_id = uuid.uuid4()
    await _run(dsn, "INSERT INTO firms (tenant_id, name) VALUES ($1, 'Firm')", tenant_id)
    return tenant_id


async def _person(dsn: str, *firms: uuid.UUID) -> tuple[uuid.UUID, str]:
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = cast(
        uuid.UUID,
        await _value(
            dsn,
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, 'Staff Person') RETURNING id",
            ISSUER,
            subject,
            f"{subject}@example.test",
        ),
    )
    for tenant_id in firms:
        await _run(
            dsn,
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, 'security_admin', 'active')",
            tenant_id,
            user_id,
        )
    return user_id, subject


async def _policy(dsn: str, tenant_id: uuid.UUID, by: uuid.UUID, **columns: object) -> None:
    names = ["tenant_id", "updated_by", *columns]
    marks = ", ".join(f"${i}" for i in range(1, len(names) + 1))
    await _run(
        dsn,
        f"INSERT INTO security_policies ({', '.join(names)}) VALUES ({marks})",  # noqa: S608 -- test column names
        tenant_id,
        by,
        *columns.values(),
        actor=by,
    )


def _cookie(response: httpx.Response) -> str:
    [header] = [h for h in response.headers.get_list("set-cookie") if h.startswith(COOKIE_NAME)]
    return header.split(";", 1)[0].split("=", 1)[1]


async def _sign_in(
    http: httpx.AsyncClient, idp: MethodIdp, subject: str, method: str | None
) -> httpx.Response:
    started = await http.get("/v1/auth/sign-in", params={"return_to": "/x"})
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    response = await http.get(
        "/v1/auth/callback", params={"code": idp.issue(subject, method), "state": state}
    )
    http.cookies.clear()
    return response


def _refused(response: httpx.Response) -> str | None:
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["error"][0] if "error" in query else None


async def _refresh(http: httpx.AsyncClient, cookie: str) -> httpx.Response:
    response = await http.post(
        "/v1/auth/refresh", headers={**REFRESH_HEADERS, "Cookie": f"{COOKIE_NAME}={cookie}"}
    )
    http.cookies.clear()
    return response


# --- AC-17: the firm's limits, at every refresh --------------------------------------------------


async def test_ac17_an_idle_session_past_the_firms_limit_must_sign_in_again(
    http: httpx.AsyncClient, idp: MethodIdp, dsn: str
) -> None:
    firm = await _firm(dsn)
    user, subject = await _person(dsn, firm)
    await _policy(dsn, firm, user, session_idle_minutes=10)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    idle = await _value(
        dsn,
        "SELECT extract(epoch FROM idle_expires_at - created_at)::int FROM auth_sessions "
        "WHERE user_id = $1",
        user,
    )
    assert 590 <= cast(int, idle) <= 600  # started with the firm's 10 minutes, not 30
    await _run(
        dsn,
        "UPDATE auth_sessions SET last_seen_at = now() - interval '11 minutes', "
        "idle_expires_at = now() + interval '19 minutes' WHERE user_id = $1",
        user,
    )
    refused = await _refresh(http, cookie)
    assert refused.status_code == 401 and refused.json()["detail"] == "session_expired"
    reason = await _value(dsn, "SELECT end_reason FROM auth_sessions WHERE user_id = $1", user)
    assert reason == "idle"


async def test_ac17_the_strictest_firm_applies_and_a_fresh_session_refreshes(
    http: httpx.AsyncClient, idp: MethodIdp, dsn: str
) -> None:
    lenient, strict = await _firm(dsn), await _firm(dsn)
    user, subject = await _person(dsn, lenient, strict)
    await _policy(dsn, strict, user, session_absolute_minutes=60)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    assert (await _refresh(http, cookie)).status_code == 200
    absolute = await _value(
        dsn,
        "SELECT extract(epoch FROM absolute_expires_at - created_at)::int FROM auth_sessions "
        "WHERE user_id = $1",
        user,
    )
    assert 3590 <= cast(int, absolute) <= 3600


# --- AC-15, AC-18: Require SSO at sign-in --------------------------------------------------------


@pytest.mark.parametrize("method", ["MagicAuth", None])
async def test_ac15_with_sso_required_another_method_is_refused(
    http: httpx.AsyncClient, idp: MethodIdp, dsn: str, method: str | None
) -> None:
    firm = await _firm(dsn)
    user, subject = await _person(dsn, firm)
    await _policy(dsn, firm, user, require_sso=True, sso_enforced_by=user, sso_enforced_at=_NOW)
    assert _refused(await _sign_in(http, idp, subject, method)) == "sso_required"
    assert _refused(await _sign_in(http, idp, subject, "SSO")) is None


async def test_ac18_the_exempt_account_passes_with_its_passkey_and_is_stamped(
    http: httpx.AsyncClient, idp: MethodIdp, dsn: str
) -> None:
    firm = await _firm(dsn)
    felix, _ = await _person(dsn, firm)
    exempt, subject = await _person(dsn, firm)
    await _policy(
        dsn,
        firm,
        felix,
        require_sso=True,
        sso_enforced_by=felix,
        sso_enforced_at=_NOW,
        sso_exempt_user_id=exempt,
    )
    assert _refused(await _sign_in(http, idp, subject, "MagicAuth")) == "sso_required"
    assert _refused(await _sign_in(http, idp, subject, "Passkey")) is None
    stamped = await _value(
        dsn, "SELECT sso_exempt_tested_at FROM security_policies WHERE tenant_id = $1", firm
    )
    assert stamped is not None
    logged = await _value(
        dsn,
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'sso_exempt_account.tested'",
        firm,
    )
    assert logged == str(exempt)


async def test_ac18_nobody_designates_themselves_even_past_the_service(dsn: str) -> None:
    firm = await _firm(dsn)
    felix, _ = await _person(dsn, firm)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await _policy(dsn, firm, felix, sso_exempt_user_id=felix)


# --- AC-20: sign out of one firm -----------------------------------------------------------------


async def test_ac20_a_session_signed_out_of_a_firm_acts_there_no_more_but_elsewhere_does(
    http: httpx.AsyncClient, idp: MethodIdp, dsn: str
) -> None:
    here, elsewhere = await _firm(dsn), await _firm(dsn)
    user, subject = await _person(dsn, here, elsewhere)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    refreshed = await _refresh(http, cookie)
    cookie, token = _cookie(refreshed), refreshed.json()["access_token"]
    session = await _value(dsn, "SELECT id FROM auth_sessions WHERE user_id = $1", user)
    await _run(
        dsn,
        "INSERT INTO auth_session_tenant_revocations (tenant_id, session_id, revoked_by) "
        "VALUES ($1, $2, $3)",
        here,
        session,
        user,
        actor=user,
    )

    def headers(firm: uuid.UUID, *, with_cookie: bool = True) -> dict[str, str]:
        sent = {"Authorization": f"Bearer {token}", "X-Abacus-Tenant": str(firm)}
        return {**sent, "Cookie": f"{COOKIE_NAME}={cookie}"} if with_cookie else sent

    refused = await http.get("/v1/firm/time-zone", headers=headers(here))
    assert refused.status_code == 401 and refused.json()["detail"] == "session_signed_out"
    # A bearer token alone does not get round it while no other live session is untouched.
    bare = await http.get("/v1/firm/time-zone", headers=headers(here, with_cookie=False))
    assert bare.status_code == 401
    assert (await http.get("/v1/firm/time-zone", headers=headers(elsewhere))).status_code != 401
    ended = await _value(dsn, "SELECT ended_at FROM auth_sessions WHERE id = $1", session)
    assert ended is None


# --- AC-19: the portal session length ------------------------------------------------------------


async def test_ac19_the_portal_length_is_the_firms_and_never_over_eight_hours(dsn: str) -> None:
    firm = await _firm(dsn)
    user, _ = await _person(dsn, firm)
    assert await security_policies.portal_session_seconds(firm) == 480 * 60
    await _run(
        dsn,
        "INSERT INTO portal_security_policies (tenant_id, portal_session_minutes, updated_by) "
        "VALUES ($1, 120, $2)",
        firm,
        user,
        actor=user,
    )
    assert await security_policies.portal_session_seconds(firm) == 120 * 60
    with pytest.raises(asyncpg.CheckViolationError):
        await _run(
            dsn,
            "UPDATE portal_security_policies SET portal_session_minutes = 600, updated_by = $2 "
            "WHERE tenant_id = $1",
            firm,
            user,
            actor=user,
        )


# --- the purge, and the policies' audit values ---------------------------------------------------


async def test_sessions_ended_over_a_year_ago_are_purged_and_live_ones_stay(dsn: str) -> None:
    firm = await _firm(dsn)
    user, _ = await _person(dsn, firm)
    old = await _value(
        dsn,
        "INSERT INTO auth_sessions (user_id, provider, idle_expires_at, absolute_expires_at, "
        "ended_at, end_reason) VALUES ($1, 'oidc', now() - interval '400 days', "
        "now() - interval '400 days', now() - interval '400 days', 'sign_out') RETURNING id",
        user,
    )
    live = await _value(
        dsn,
        "INSERT INTO auth_sessions (user_id, provider, idle_expires_at, absolute_expires_at) "
        "VALUES ($1, 'oidc', now() + interval '30 minutes', now() + interval '12 hours') "
        "RETURNING id",
        user,
    )
    await _run(
        dsn,
        "INSERT INTO auth_session_cookies (cookie_sha256, session_id) VALUES ($1, $2)",
        "a" * 64,
        old,
    )
    assert await security_policies.purge_auth_sessions() >= 1
    left = await _value(dsn, "SELECT count(*) FROM auth_sessions WHERE id = ANY($1)", [old, live])
    assert left == 1
    assert (
        await _value(dsn, "SELECT count(*) FROM auth_session_cookies WHERE session_id = $1", old)
        == 0
    )


async def test_dec529_policy_values_come_from_the_events_own_references() -> None:
    viewer = AuthContext(
        TenantContext(uuid.uuid4(), "human", "u"), uuid.uuid4(), uuid.uuid4(), None, None
    )
    event = AuditEventRef(
        seq=1,
        action="security_policy.updated",
        target_type="security_policy",
        target_id=str(viewer.tenant_id),
        before_ref={"require_sso": 0, "session_idle_minutes": 30, "version": 1},
        after_ref={"require_sso": 1, "session_idle_minutes": 20, "version": 2},
    )
    values = await security_policy_values(viewer, event)
    assert values.status == "resolved"
    rows = {r.field: (r.before, r.after) for r in values.rows}
    assert rows == {"require_sso": ("false", "true"), "session_idle_minutes": ("30", "20")}
