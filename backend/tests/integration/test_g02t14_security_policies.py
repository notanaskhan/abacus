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
from typing import Final, Protocol, cast
from urllib.parse import parse_qs, urlparse

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.modules.identity import security_policies, support
from abacus.modules.identity.api import AuthContext, configure_verifier, reset_verifier
from abacus.modules.identity.governance_errors import SsoNotVerified, SupportRequestsDisabled
from abacus.modules.identity.staff_session import (
    COOKIE_NAME,
    ProviderRefused,
    ProviderTokens,
    auth_method_of,
    configure_staff_idp,
)
from abacus.modules.identity.support import Staff
from abacus.modules.platform.audit_resolvers import security_policy_values
from abacus.modules.platform.audit_slots import AuditEventRef
from abacus_tools.fakes.identity import ISSUER, FakeIdentityProvider

from .agent_tests.support import Seeder

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
        self.codes: dict[str, tuple[str, str | None, str | None]] = {}
        self.refresh_tokens: dict[str, tuple[str, str | None, str | None]] = {}

    def authorize_url(
        self, *, state: str, challenge: str, redirect_uri: str, reauthenticate: bool
    ) -> str:
        return f"https://idp.test/authorize?state={state}&code_challenge={challenge}"

    def issue(self, subject: str, method: str | None, org: str | None = None) -> str:
        code = uuid.uuid4().hex
        self.codes[code] = (subject, method, org)
        return code

    def _tokens(self, subject: str, method: str | None, org: str | None) -> ProviderTokens:
        refresh = uuid.uuid4().hex
        self.refresh_tokens[refresh] = (subject, method, org)
        token = self.signer.token(subject, mfa=True, expires_in=600)
        return ProviderTokens(token, 600, refresh, auth_method_of(method), org)

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


@pytest.fixture
def seed(dsn: str) -> Seeder:
    return Seeder(dsn)


_POLICY_COLUMNS: Final = (
    "require_sso",
    "sso_enforced_at",
    "sso_enforced_by",
    "session_absolute_minutes",
    "session_idle_minutes",
    "sso_exempt_user_id",
    "sso_connection_org",
)
_INSERT_POLICY: Final = (
    "INSERT INTO security_policies (tenant_id, updated_by, require_sso, sso_enforced_at, "
    "sso_enforced_by, session_absolute_minutes, session_idle_minutes, sso_exempt_user_id, "
    "sso_connection_org) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)"
)


async def _policy(seed: Seeder, tenant_id: uuid.UUID, by: uuid.UUID, **columns: object) -> None:
    """A policy row as the person `by` (the table's trigger reads the transaction's actor)."""
    defaults: dict[str, object] = {
        "require_sso": False,
        "sso_enforced_at": None,
        "sso_enforced_by": None,
        "session_absolute_minutes": 720,
        "session_idle_minutes": 30,
        "sso_exempt_user_id": None,
        "sso_connection_org": None,
    }
    values = {**defaults, **columns}
    await seed.as_actor(
        tenant_id,
        ("human", str(by)),
        _INSERT_POLICY,
        tenant_id,
        by,
        *(values[c] for c in _POLICY_COLUMNS),
    )


async def _firm(seed: Seeder) -> uuid.UUID:
    return await seed.firm()


async def _person(seed: Seeder, *firms: uuid.UUID) -> tuple[uuid.UUID, str]:
    subject = f"sub-{uuid.uuid4().hex}"
    user_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
            "VALUES ($1, $2, $3, 'Staff Person') RETURNING id",
            ISSUER,
            subject,
            f"{subject}@example.test",
        ),
    )
    for tenant_id in firms:
        await seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, 'security_admin', 'active')",
            tenant_id,
            user_id,
        )
    return user_id, subject


def _cookie(response: httpx.Response) -> str:
    [header] = [h for h in response.headers.get_list("set-cookie") if h.startswith(COOKIE_NAME)]
    return header.split(";", 1)[0].split("=", 1)[1]


async def _sign_in(
    http: httpx.AsyncClient,
    idp: MethodIdp,
    subject: str,
    method: str | None,
    org: str | None = None,
) -> httpx.Response:
    started = await http.get("/v1/auth/sign-in", params={"return_to": "/x"})
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    response = await http.get(
        "/v1/auth/callback", params={"code": idp.issue(subject, method, org), "state": state}
    )
    http.cookies.clear()
    return response


def _refused(response: httpx.Response) -> str | None:
    query = parse_qs(urlparse(response.headers["location"]).query)
    return query["error"][0] if "error" in query else None


async def _refresh(http: httpx.AsyncClient, cookie: str, *, active: bool = True) -> httpx.Response:
    activity = {"X-Abacus-Activity": "user"} if active else {}
    response = await http.post(
        "/v1/auth/refresh",
        headers={**REFRESH_HEADERS, **activity, "Cookie": f"{COOKIE_NAME}={cookie}"},
    )
    http.cookies.clear()
    return response


# --- AC-17: the firm's limits, at every refresh --------------------------------------------------


async def test_ac17_an_idle_session_past_the_firms_limit_must_sign_in_again(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    firm = await _firm(seed)
    user, subject = await _person(seed, firm)
    await _policy(seed, firm, user, session_idle_minutes=10)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    idle = await seed.value(
        "SELECT extract(epoch FROM idle_expires_at - created_at)::int FROM auth_sessions "
        "WHERE user_id = $1",
        user,
    )
    assert 590 <= cast(int, idle) <= 600  # started with the firm's 10 minutes, not 30
    await seed.run(
        "UPDATE auth_sessions SET last_seen_at = now() - interval '11 minutes', "
        "idle_expires_at = now() + interval '19 minutes' WHERE user_id = $1",
        user,
    )
    refused = await _refresh(http, cookie)
    assert refused.status_code == 401 and refused.json()["detail"] == "session_expired"
    reason = await seed.value("SELECT end_reason FROM auth_sessions WHERE user_id = $1", user)
    assert reason == "idle"


async def test_ac17_the_strictest_firm_applies_and_a_fresh_session_refreshes(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    lenient, strict = await _firm(seed), await _firm(seed)
    user, subject = await _person(seed, lenient, strict)
    await _policy(seed, strict, user, session_absolute_minutes=60)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    assert (await _refresh(http, cookie)).status_code == 200
    absolute = await seed.value(
        "SELECT extract(epoch FROM absolute_expires_at - created_at)::int FROM auth_sessions "
        "WHERE user_id = $1",
        user,
    )
    assert 3590 <= cast(int, absolute) <= 3600


# --- AC-15, AC-18: Require SSO at sign-in --------------------------------------------------------


@pytest.mark.parametrize("method", ["MagicAuth", None])
async def test_ac15_with_sso_required_another_method_is_refused(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder, method: str | None
) -> None:
    firm = await _firm(seed)
    user, subject = await _person(seed, firm)
    await _policy(
        seed,
        firm,
        user,
        require_sso=True,
        sso_enforced_by=user,
        sso_enforced_at=_NOW,
        sso_connection_org="org_brightwater",
    )
    assert _refused(await _sign_in(http, idp, subject, method)) == "sso_required"
    assert _refused(await _sign_in(http, idp, subject, "SSO", "org_brightwater")) is None


async def test_m1_sso_through_another_firms_connection_does_not_count(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    firm = await _firm(seed)
    user, subject = await _person(seed, firm)
    await _policy(
        seed,
        firm,
        user,
        require_sso=True,
        sso_enforced_by=user,
        sso_enforced_at=_NOW,
        sso_connection_org="org_brightwater",
    )
    assert _refused(await _sign_in(http, idp, subject, "SSO", "org_elsewhere")) == "sso_required"
    assert _refused(await _sign_in(http, idp, subject, "SSO")) == "sso_required"


async def test_m1_require_sso_needs_the_firms_own_connection(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    firm = await _firm(seed)
    user, subject = await _person(seed, firm)
    # An admin's SSO sign-in through some other organisation verifies nothing here.
    assert _refused(await _sign_in(http, idp, subject, "SSO", "org_elsewhere")) is None
    membership = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2", firm, user
        ),
    )
    ctx = AuthContext(
        TenantContext(firm, "human", str(user)),
        user,
        membership,
        "security_admin",
        datetime.now(UTC),
    )
    with pytest.raises(SsoNotVerified) as missing:
        await security_policies.put_sign_in(
            ctx,
            require_sso=True,
            session_absolute_minutes=720,
            session_idle_minutes=30,
            idp_mfa_attested=False,
            version=0,
        )
    assert missing.value.facts == {"reason": "connection_missing"}


async def test_ac18_the_exempt_account_passes_with_its_passkey_and_is_stamped(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    firm = await _firm(seed)
    felix, _ = await _person(seed, firm)
    exempt, subject = await _person(seed, firm)
    await _policy(
        seed,
        firm,
        felix,
        require_sso=True,
        sso_enforced_by=felix,
        sso_enforced_at=_NOW,
        sso_exempt_user_id=exempt,
        sso_connection_org="org_brightwater",
    )
    assert _refused(await _sign_in(http, idp, subject, "MagicAuth")) == "sso_required"
    assert _refused(await _sign_in(http, idp, subject, "Passkey")) is None
    stamped = await seed.value(
        "SELECT sso_exempt_tested_at FROM security_policies WHERE tenant_id = $1", firm
    )
    assert stamped is not None
    logged = await seed.value(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'sso_exempt_account.tested'",
        firm,
    )
    assert logged == str(exempt)


async def test_ac18_nobody_designates_themselves_even_past_the_service(seed: Seeder) -> None:
    firm = await _firm(seed)
    felix, _ = await _person(seed, firm)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await _policy(seed, firm, felix, sso_exempt_user_id=felix)


# --- AC-20: sign out of one firm -----------------------------------------------------------------


async def test_ac20_a_session_signed_out_of_a_firm_acts_there_no_more_but_elsewhere_does(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    here, elsewhere = await _firm(seed), await _firm(seed)
    user, subject = await _person(seed, here, elsewhere)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    refreshed = await _refresh(http, cookie)
    cookie, token = _cookie(refreshed), refreshed.json()["access_token"]
    session = await seed.value("SELECT id FROM auth_sessions WHERE user_id = $1", user)
    await seed.as_actor(
        here,
        ("human", str(user)),
        "INSERT INTO auth_session_tenant_revocations (tenant_id, session_id, user_id, "
        "revoked_by) VALUES ($1, $2, $3, $4)",
        here,
        session,
        user,
        user,
    )

    def headers(firm: uuid.UUID, *, with_cookie: bool = True) -> dict[str, str]:
        sent = {"Authorization": f"Bearer {token}", "X-Abacus-Tenant": str(firm)}
        return {**sent, "Cookie": f"{COOKIE_NAME}={cookie}"} if with_cookie else sent

    refused = await http.get("/v1/firm/time-zone", headers=headers(here))
    assert refused.status_code == 401 and refused.json()["detail"] == "session_signed_out"
    assert (await http.get("/v1/firm/time-zone", headers=headers(elsewhere))).status_code != 401
    ended = await seed.value("SELECT ended_at FROM auth_sessions WHERE id = $1", session)
    assert ended is None
    # H1: the person signs in again elsewhere (a second live session). The stolen session's
    # bearer token alone, or with a junk cookie, still acts here no more.
    _cookie(await _sign_in(http, idp, subject, "sso"))
    bare = await http.get("/v1/firm/time-zone", headers=headers(here, with_cookie=False))
    assert bare.status_code == 401
    junk = {**headers(here, with_cookie=False), "Cookie": f"{COOKIE_NAME}=junk"}
    assert (await http.get("/v1/firm/time-zone", headers=junk)).status_code == 401
    # The stolen cookie still refreshes for the firm it was not signed out of, and the token it
    # gets is refused here again.
    again = await _refresh(http, cookie)
    assert again.status_code == 200
    cookie, token = _cookie(again), again.json()["access_token"]
    assert (await http.get("/v1/firm/time-zone", headers=headers(here))).status_code == 401
    assert (
        await http.get("/v1/firm/time-zone", headers=headers(here, with_cookie=False))
    ).status_code == 401


async def test_h1_a_session_signed_out_of_all_its_firms_gets_no_token(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    firm = await _firm(seed)
    user, subject = await _person(seed, firm)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    session = await seed.value("SELECT id FROM auth_sessions WHERE user_id = $1", user)
    await seed.as_actor(
        firm,
        ("human", str(user)),
        "INSERT INTO auth_session_tenant_revocations (tenant_id, session_id, user_id, "
        "revoked_by) VALUES ($1, $2, $3, $4)",
        firm,
        session,
        user,
        user,
    )
    refused = await _refresh(http, cookie)
    assert refused.status_code == 401
    reason = await seed.value("SELECT end_reason FROM auth_sessions WHERE id = $1", session)
    assert reason == "revoked"


async def test_m3_a_background_refresh_does_not_move_the_idle_clock(
    http: httpx.AsyncClient, idp: MethodIdp, seed: Seeder
) -> None:
    firm = await _firm(seed)
    user, subject = await _person(seed, firm)
    cookie = _cookie(await _sign_in(http, idp, subject, "sso"))
    await seed.run(
        "UPDATE auth_sessions SET last_seen_at = now() - interval '20 minutes', "
        "idle_expires_at = now() + interval '10 minutes' WHERE user_id = $1",
        user,
    )
    polled = await _refresh(http, cookie, active=False)
    assert polled.status_code == 200
    idle_left = await seed.value(
        "SELECT extract(epoch FROM idle_expires_at - now())::int FROM auth_sessions "
        "WHERE user_id = $1",
        user,
    )
    assert cast(int, idle_left) <= 600  # not pushed back to 30 minutes
    used = await _refresh(http, _cookie(polled), active=True)
    assert used.status_code == 200
    idle_left = await seed.value(
        "SELECT extract(epoch FROM idle_expires_at - now())::int FROM auth_sessions "
        "WHERE user_id = $1",
        user,
    )
    assert cast(int, idle_left) > 1700


# --- AC-19: the portal session length ------------------------------------------------------------


async def test_ac19_the_portal_length_is_the_firms_and_never_over_eight_hours(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    user, _ = await _person(seed, firm)
    assert await security_policies.portal_session_seconds(firm) == 480 * 60
    await seed.run(
        "INSERT INTO portal_security_policies (tenant_id, portal_session_minutes, updated_by) "
        "VALUES ($1, 120, $2)",
        firm,
        user,
    )
    assert await security_policies.portal_session_seconds(firm) == 120 * 60
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "UPDATE portal_security_policies SET portal_session_minutes = 600, updated_by = $2 "
            "WHERE tenant_id = $1",
            firm,
            user,
        )


# --- the purge, and the policies' audit values ---------------------------------------------------


async def test_sessions_ended_over_a_year_ago_are_purged_and_live_ones_stay(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    user, _ = await _person(seed, firm)
    old = await seed.value(
        "INSERT INTO auth_sessions (user_id, provider, idle_expires_at, absolute_expires_at, "
        "ended_at, end_reason) VALUES ($1, 'oidc', now() - interval '400 days', "
        "now() - interval '400 days', now() - interval '400 days', 'sign_out') RETURNING id",
        user,
    )
    live = await seed.value(
        "INSERT INTO auth_sessions (user_id, provider, idle_expires_at, absolute_expires_at) "
        "VALUES ($1, 'oidc', now() + interval '30 minutes', now() + interval '12 hours') "
        "RETURNING id",
        user,
    )
    await seed.run(
        "INSERT INTO auth_session_cookies (cookie_sha256, session_id) VALUES ($1, $2)",
        "a" * 64,
        old,
    )
    assert await security_policies.purge_auth_sessions() >= 1
    left = await seed.value("SELECT count(*) FROM auth_sessions WHERE id = ANY($1)", [old, live])
    assert left == 1
    assert (
        await seed.value("SELECT count(*) FROM auth_session_cookies WHERE session_id = $1", old)
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


# --- M2: the support switch holds for pending requests ---------------------------------------


def _security_admin(tenant: uuid.UUID, user: uuid.UUID, membership: uuid.UUID) -> AuthContext:
    return AuthContext(
        TenantContext(tenant, "human", str(user)),
        user,
        membership,
        "security_admin",
        datetime.now(UTC),
    )


async def test_m2_switching_off_closes_pending_requests_and_nothing_pending_is_granted(
    seed: Seeder,
) -> None:
    firm = await _firm(seed)
    felix, _ = await _person(seed, firm)
    membership = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2", firm, felix
        ),
    )
    ctx = _security_admin(firm, felix, membership)
    reason = "Investigating an integration settings question for the firm"
    staff = Staff(uuid.uuid4(), "staff-probe", datetime.now(UTC))
    pending = await support.request_session(staff, firm, reason, "metadata", 60, False)
    await security_policies.put_support_access(ctx, allow=False, version=0)
    closed = await seed.value("SELECT status FROM support_sessions WHERE id = $1", pending.id)
    assert closed == "revoked"

    # A request made before a switch-off written straight to the row is still never granted.
    other = await _firm(seed)
    grace, _ = await _person(seed, other)
    grace_membership = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2", other, grace
        ),
    )
    waiting = await support.request_session(staff, other, reason, "metadata", 60, True)
    await seed.as_actor(
        other,
        ("human", str(grace)),
        "INSERT INTO security_policies (tenant_id, updated_by, allow_support_requests) "
        "VALUES ($1, $2, false)",
        other,
        grace,
    )
    with pytest.raises(SupportRequestsDisabled):
        await support.approve_session(_security_admin(other, grace, grace_membership), waiting.id)
    second = Staff(uuid.uuid4(), "staff-second", datetime.now(UTC))
    with pytest.raises(SupportRequestsDisabled):
        await support.emergency_approve(second, other, waiting.id)
