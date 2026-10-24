"""P-08-T10 against Postgres (SPEC-320 AC-6 to AC-8; ADR-168): sign-in by emailed code without an
oracle, the 10-minute code, the lock after three wrong codes, the 60-second resend, and a portal
session pinned to its tenant and host, refreshed with rotation and reuse detection."""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from collections.abc import AsyncIterator
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.identity import portal_session
from abacus.modules.identity.portal_session import (
    CodeExpired,
    CodeMismatch,
    PortalSessionEnded,
    ResendTooSoon,
    SignInLocked,
    issue_sign_in_code,
    landing_of,
    portal_context,
    refresh_portal_session,
    resend_code,
    start_sign_in,
    verify_code,
)
from abacus.modules.portal.branding import activate_portal_host, add_portal_host

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)

    async def on(_tenant: object, _flag: object) -> bool:
        return True

    monkeypatch.setattr(portal_session, "flag_enabled", on)  # `portal.sign_in_v2` on
    monkeypatch.setattr(portal_session, "FLOOR_SECONDS", 0.0)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def _portal(seed: Seeder) -> tuple[uuid.UUID, str, Person, str]:
    """A firm with an active portal host and one client person (Claire) with a grant. A
    `contributor` grant: the MFA floor (P-08-T17) asks an `owner` for a second step, which
    `test_portal_mfa.py` covers."""
    tenant = await seed.firm()
    host = f"brightwaterhale-{uuid.uuid4().hex[:8]}.portal-example.test"
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    async with uow(ctx) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    partner = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    claire = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        claire.user_id,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'contributor', 'engagement', $3)",
        tenant,
        claire.user_id,
        engagement,
    )
    email = cast(str, await seed.value("SELECT email FROM users WHERE id = $1", claire.user_id))
    return tenant, host, claire, email


async def _events(seed: Seeder, tenant: uuid.UUID) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'portal.sign_in_code_requested'",
            tenant,
        ),
    )


async def _signed_in(host: str, email: str) -> portal_session.PortalTokens:
    started = await start_sign_in(host, email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    return await verify_code(host, started.challenge_id, issued.code)


async def test_ac6_every_email_gets_the_same_answer_and_only_a_client_gets_a_code(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host, _, email = await _portal(seed)
    staff = await seed.person(tenant)
    staff_email = await seed.value("SELECT email FROM users WHERE id = $1", staff.user_id)
    answers: list[set[str]] = []
    for asked in (email, "nobody@example.test", staff_email, email.upper()):
        response = await client.post(
            "/v1/portal/auth/start", json={"email": asked}, headers={"host": host}
        )
        assert response.status_code == 202
        answers.append(set(cast(dict[str, object], response.json())))
    assert all(a == {"challenge_id", "code_expires_at", "resend_available_at"} for a in answers)
    # Claire once: the case-folded second start within 60 s sends nothing more (no mail bombing).
    assert await _events(seed, tenant) == 1
    other_host = await client.post(
        "/v1/portal/auth/start", json={"email": email}, headers={"host": "unknown.example.test"}
    )
    assert other_host.status_code == 202
    assert await _events(seed, tenant) == 1
    assert (
        await seed.value(
            "SELECT count(*) FROM sign_in_challenges WHERE host = 'unknown.example.test'"
        )
        == 0
    )  # a host no firm has active writes nothing
    # Nothing is issued for a challenge without a person.
    unknown = await start_sign_in(host, "nobody@example.test")
    assert await issue_sign_in_code(unknown.challenge_id) is None


async def test_ac7_a_verified_code_starts_a_session_pinned_to_tenant_and_host(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tenant, host, claire, email = await _portal(seed)
    started = await start_sign_in(host, email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None and issued.user_id == claire.user_id
    assert await issue_sign_in_code(started.challenge_id) is None  # issued once
    response = await client.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": str(started.challenge_id), "code": issued.code},
        headers={"host": host},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "signed_in" and body["landing"] == "home"
    assert "__Host-abacus-portal=" in response.headers["set-cookie"]
    token = body["access_token"]

    ctx = await portal_context(token, host)
    assert ctx is not None and ctx.tenant_id == tenant and ctx.user_id == claire.user_id
    assert ctx.client and ctx.firm_role is None
    assert await portal_context(token, "other.portal-example.test") is None
    assert await portal_context(token, None) is None
    # Stored only as its SHA-256.
    stored = await seed.value(
        "SELECT access_sha256 FROM auth_sessions WHERE user_id = $1", claire.user_id
    )
    assert stored == hashlib.sha256(token.encode()).hexdigest()
    # The same code twice: the challenge is used.
    with pytest.raises(CodeExpired):
        await verify_code(host, started.challenge_id, issued.code)


async def test_ac7_three_wrong_codes_lock_the_email_on_the_host_for_15_minutes(
    seed: Seeder,
) -> None:
    tenant, host, _, email = await _portal(seed)
    started = await start_sign_in(host, email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    wrong = "000000" if issued.code != "000000" else "111111"
    with pytest.raises(CodeMismatch) as first:
        await verify_code(host, started.challenge_id, wrong)
    assert first.value.tries_left == 2
    with pytest.raises(CodeMismatch):
        await verify_code(host, started.challenge_id, wrong)
    with pytest.raises(SignInLocked) as locked:
        await verify_code(host, started.challenge_id, wrong)
    minutes = await seed.value(
        "SELECT extract(epoch FROM locked_until - now()) / 60 FROM sign_in_locks "
        "WHERE host_tenant_id = $1 AND locked_until IS NOT NULL",
        tenant,
    )
    assert 14 < float(cast(float, minutes)) <= 15 and locked.value.locked_until
    # A new start sends nothing while locked, and its verify is locked too.
    before = await _events(seed, tenant)
    again = await start_sign_in(host, email)
    assert await _events(seed, tenant) == before
    with pytest.raises(SignInLocked):
        await verify_code(host, again.challenge_id, issued.code)
    # An unknown email locks the same way (no oracle).
    nobody = await start_sign_in(host, "nobody@example.test")
    for _ in range(2):
        with pytest.raises(CodeMismatch):
            await verify_code(host, nobody.challenge_id, "123456")
    with pytest.raises(SignInLocked):
        await verify_code(host, nobody.challenge_id, "123456")


async def test_ac7_codes_expire_and_resend_waits_a_minute_keeping_the_tries(seed: Seeder) -> None:
    _, host, _, email = await _portal(seed)
    started = await start_sign_in(host, email)
    first = await issue_sign_in_code(started.challenge_id)
    assert first is not None
    with pytest.raises(ResendTooSoon):
        await resend_code(host, started.challenge_id)
    wrong = "000000" if first.code != "000000" else "111111"
    with pytest.raises(CodeMismatch):
        await verify_code(host, started.challenge_id, wrong)
    await seed.run(
        "UPDATE sign_in_challenges SET resend_available_at = now() - interval '1 second' "
        "WHERE id = $1",
        started.challenge_id,
    )
    await resend_code(host, started.challenge_id)
    second = await issue_sign_in_code(started.challenge_id)
    assert second is not None
    if second.code != first.code:
        with pytest.raises(CodeMismatch) as kept:  # the old code is void; tries kept
            await verify_code(host, started.challenge_id, first.code)
        assert kept.value.tries_left == 1
    await seed.run(
        "UPDATE sign_in_challenges SET code_expires_at = now() - interval '1 second' "
        "WHERE id = $1",
        started.challenge_id,
    )
    with pytest.raises(CodeExpired):
        await verify_code(host, started.challenge_id, second.code)
    with pytest.raises(CodeExpired):  # another host never sees the challenge
        await verify_code("other.portal-example.test", started.challenge_id, second.code)


async def test_ac7_refresh_rotates_and_a_reused_cookie_ends_the_session(seed: Seeder) -> None:
    _, host, _, email = await _portal(seed)
    tokens = await _signed_in(host, email)
    with pytest.raises(PortalSessionEnded):  # another host's refresh is no session
        await refresh_portal_session(tokens.cookie, "other.portal-example.test")
    rotated = await refresh_portal_session(tokens.cookie, host)
    assert rotated.cookie != tokens.cookie and rotated.access_token != tokens.access_token
    assert await portal_context(tokens.access_token, host) is None  # the old token is gone
    assert await portal_context(rotated.access_token, host) is not None
    with pytest.raises(PortalSessionEnded):
        await refresh_portal_session(tokens.cookie, host)  # reuse ends the session
    assert await portal_context(rotated.access_token, host) is None
    with pytest.raises(PortalSessionEnded):
        await refresh_portal_session(rotated.cookie, host)


async def test_ac7_refresh_needs_the_csrf_header_and_the_hosts_origin(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    _, host, _, email = await _portal(seed)
    tokens = await _signed_in(host, email)
    cookie = {"__Host-abacus-portal": tokens.cookie}
    for headers in (
        {"host": host, "origin": f"https://{host}"},
        {"host": host, "origin": "https://evil.example.test", "x-abacus-csrf": "1"},
    ):
        client.cookies.clear()
        refused = await client.post("/v1/portal/auth/refresh", headers=headers, cookies=cookie)
        assert refused.status_code == 403
    client.cookies.clear()
    ok = await client.post(
        "/v1/portal/auth/refresh",
        headers={"host": host, "origin": f"https://{host}", "x-abacus-csrf": "1"},
        cookies=cookie,
    )
    assert ok.status_code == 200 and ok.json()["access_token"] != tokens.access_token


async def test_ac7_the_portal_token_authenticates_only_on_its_host_and_sign_out_ends_it(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    _, host, _, email = await _portal(seed)
    tokens = await _signed_in(host, email)
    bearer = {"authorization": f"Bearer {tokens.access_token}"}
    home = await client.get("/v1/portal/home", headers={"host": host, **bearer})
    assert home.status_code == 404  # authenticated; `portal.home_v2` is off for the firm
    elsewhere = await client.get(
        "/v1/portal/home", headers={"host": "other.portal-example.test", **bearer}
    )
    assert elsewhere.status_code == 401
    client.cookies.clear()
    out = await client.post(
        "/v1/portal/auth/sign-out",
        headers={"host": host, **bearer},
        cookies={"__Host-abacus-portal": tokens.cookie},
    )
    assert out.status_code == 200 and out.json() == {"ended": True}
    after = await client.get("/v1/portal/home", headers={"host": host, **bearer})
    assert after.status_code == 401


def test_ac8_landing_follows_the_role_union() -> None:
    assert landing_of(["taxpayer", "k1_recipient"]) == "home"
    assert landing_of(["k1_recipient"]) == "k1s"
    assert landing_of(["third_party"]) == "requests"
    assert landing_of(["tcwg"]) == "governance"
    assert landing_of(["prospect"]) == "intake"
    assert landing_of(["component_auditor"]) == "component_room"
    assert landing_of([]) == "none"


async def test_ac7_parallel_or_fresh_challenges_never_get_more_than_three_guesses(
    seed: Seeder,
) -> None:
    """Each guess is counted before it is compared, per firm and email over every challenge."""
    _, host, _, email = await _portal(seed)
    started = await start_sign_in(host, email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    wrong = "000000" if issued.code != "000000" else "111111"
    outcomes = await asyncio.gather(
        *(verify_code(host, started.challenge_id, wrong) for _ in range(8)),
        return_exceptions=True,
    )
    assert sum(isinstance(o, CodeMismatch) for o in outcomes) <= 2
    assert all(isinstance(o, CodeMismatch | SignInLocked | CodeExpired) for o in outcomes)
    with pytest.raises(SignInLocked):  # the right code no longer helps
        await verify_code(host, started.challenge_id, issued.code)

    _, host, _, email = await _portal(seed)
    fresh = [await start_sign_in(host, email) for _ in range(3)]
    for challenge in fresh[:2]:
        with pytest.raises(CodeMismatch):
            await verify_code(host, challenge.challenge_id, "123456")
    with pytest.raises(SignInLocked):
        await verify_code(host, fresh[2].challenge_id, "123456")


async def test_ac7_a_revoked_grant_ends_what_the_token_reaches(seed: Seeder) -> None:
    tenant, host, claire, email = await _portal(seed)
    tokens = await _signed_in(host, email)
    assert await portal_context(tokens.access_token, host) is not None
    await seed.run(
        "UPDATE client_access_grants SET status = 'revoked' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        claire.user_id,
    )
    assert await portal_context(tokens.access_token, host) is None


async def test_ac7_sign_out_without_the_cookie_still_ends_the_token(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    _, host, _, email = await _portal(seed)
    tokens = await _signed_in(host, email)
    bearer = {"authorization": f"Bearer {tokens.access_token}", "host": host}
    client.cookies.clear()
    out = await client.post("/v1/portal/auth/sign-out", headers=bearer)
    assert out.status_code == 200 and out.json() == {"ended": True}
    assert await portal_context(tokens.access_token, host) is None
    with pytest.raises(PortalSessionEnded):  # the session behind the cookie is gone too
        await refresh_portal_session(tokens.cookie, host)


async def test_ac6_resend_and_wrong_codes_wait_for_the_same_floor(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A known and an unknown email's resend and wrong code take at least the floor."""
    monkeypatch.setattr(portal_session, "FLOOR_SECONDS", 0.3)
    _, host, _, email = await _portal(seed)
    for asked in (email, "nobody@example.test"):
        started = await start_sign_in(host, asked)
        await seed.run(
            "UPDATE sign_in_challenges SET resend_available_at = now() WHERE id = $1",
            started.challenge_id,
        )
        loop = asyncio.get_running_loop()
        began = loop.time()
        await resend_code(host, started.challenge_id)
        assert loop.time() - began >= 0.3
        began = loop.time()
        with pytest.raises(CodeMismatch):
            await verify_code(host, started.challenge_id, "123456")
        assert loop.time() - began >= 0.3
