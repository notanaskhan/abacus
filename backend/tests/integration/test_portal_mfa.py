"""P-08-T17 against Postgres (SPEC-320 AC-10, AC-11; DEC-34; DEC-250): the MFA floor failing
closed, TOTP setup and the second step, 8 backup codes shown once and used once, the 15-minute
lock after three wrong second-step codes, 30-day trusted devices under the firm's stricter-only
policy, and revocation on `access.changed`.

Acceptance: Tess Moreno (an `owner`) cannot finish sign-in without a second factor, Claire Feld (a
`taxpayer`) is not asked for one before the TRI predicate exists, and a raising predicate makes
MFA required."""

from __future__ import annotations

import asyncio
import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import cast
from urllib.parse import parse_qs, unquote, urlparse

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.engagements.api import designate_contact
from abacus.modules.identity import mfa_floor, portal_mfa, portal_session
from abacus.modules.identity.mfa_floor import mfa_required
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp, totp_at
from abacus.modules.identity.portal_mfa import (
    MfaExpired,
    MfaLocked,
    MfaMismatch,
    revoke_portal_access,
    second_step,
    setup_second_step,
    verify_setup,
)
from abacus.modules.identity.portal_session import (
    SecondStepRequired,
    SignInLocked,
    issue_sign_in_code,
    portal_context,
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
    monkeypatch.setattr(portal_mfa, "FLOOR_SECONDS", 0.0)
    configure_portal_idp(InMemoryPortalIdp())
    yield
    configure_portal_idp(None)
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


@dataclass(frozen=True)
class Portal:
    tenant: uuid.UUID
    host: str
    person: Person
    email: str
    client_id: uuid.UUID
    engagement: uuid.UUID


async def _portal(seed: Seeder, role: str = "owner", scope: str = "engagement") -> Portal:
    """A firm with an active portal host and one client person with one grant."""
    tenant = await seed.firm()
    host = f"brightwaterhale-{uuid.uuid4().hex[:8]}.portal-example.test"
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    async with uow(ctx) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    partner = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, partner.user_id)
    client_id = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    person = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        person.user_id,
    )
    scope_id = client_id if scope == "client" else engagement
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, $3, $4, $5)",
        tenant,
        person.user_id,
        role,
        scope,
        scope_id,
    )
    email = cast(str, await seed.value("SELECT email FROM users WHERE id = $1", person.user_id))
    return Portal(tenant, host, person, email, client_id, engagement)


async def _code(p: Portal) -> tuple[uuid.UUID, str]:
    started = await start_sign_in(p.host, p.email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    return started.challenge_id, issued.code


async def _second_step(p: Portal, device_cookie: str | None = None) -> SecondStepRequired:
    challenge, code = await _code(p)
    with pytest.raises(SecondStepRequired) as asked:
        await verify_code(p.host, challenge, code, device_cookie=device_cookie)
    return asked.value


def _now_code(secret: str) -> str:
    return totp_at(secret, time.time())


def _wrong(code: str) -> str:
    return f"{(int(code) + 500_000) % 1_000_000:06d}"


async def _enrol(p: Portal) -> tuple[str, tuple[str, ...]]:
    """Setup on a first sign-in: the secret (as an authenticator holds it) and the backup codes."""
    step = await _second_step(p)
    assert step.state == "mfa_setup_required"
    key = await setup_second_step(p.host, step.mfa_token)
    done = await verify_setup(p.host, step.mfa_token, _now_code(key.manual_key))
    return key.manual_key, done.backup_codes


async def _sessions(seed: Seeder, who: Person) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM auth_sessions WHERE user_id = $1 AND surface = 'portal'",
            who.user_id,
        ),
    )


async def _actions(seed: Seeder, tenant: uuid.UUID) -> list[str]:
    rows = await seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 ORDER BY occurred_at, id", tenant
    )
    return [str(r["action"]) for r in rows]


async def test_ac10_tess_an_owner_cannot_finish_sign_in_without_a_second_factor(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tess = await _portal(seed, "owner")
    challenge, code = await _code(tess)
    response = await client.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": str(challenge), "code": code},
        headers={"host": tess.host},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["state"] == "mfa_setup_required" and set(body) == {"state", "mfa_token"}
    assert "set-cookie" not in response.headers
    assert await _sessions(seed, tess.person) == 0  # no session before the second step
    # The email code was the challenge's one use: replaying it is refused.
    replay = await client.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": str(challenge), "code": code},
        headers={"host": tess.host},
    )
    assert replay.status_code == 410

    token = body["mfa_token"]
    setup = await client.post(
        "/v1/portal/auth/mfa/setup", json={"mfa_token": token}, headers={"host": tess.host}
    )
    assert setup.status_code == 200
    key = cast(dict[str, str], setup.json())
    uri = urlparse(key["otpauth_uri"])
    assert uri.scheme == "otpauth" and parse_qs(uri.query)["secret"] == [key["manual_key"]]
    assert "accrued" not in unquote(key["otpauth_uri"]).casefold()
    # The secret is shown once: the same token can't set up again.
    again = await client.post(
        "/v1/portal/auth/mfa/setup", json={"mfa_token": token}, headers={"host": tess.host}
    )
    assert again.status_code == 410
    # The token is not a second-step token, and a setup token only works on its own host.
    elsewhere = await client.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": _now_code(key["manual_key"])},
        headers={"host": "other.portal-example.test"},
    )
    assert elsewhere.status_code == 410
    wrong = await client.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": _wrong(_now_code(key["manual_key"]))},
        headers={"host": tess.host},
    )
    assert wrong.status_code == 401 and wrong.json() == {
        "detail": "mfa_mismatch",
        "facts": {"tries_left": 2},
    }
    enrolled = await client.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": _now_code(key["manual_key"])},
        headers={"host": tess.host},
    )
    assert enrolled.status_code == 200
    out = enrolled.json()
    codes = cast(list[str], out["backup_codes"])
    assert len(codes) == 8 and len(set(codes)) == 8
    assert out["session"]["state"] == "signed_in" and out["session"]["access_token"]
    assert "__Host-abacus-portal=" in enrolled.headers["set-cookie"]
    assert enrolled.headers["cache-control"] == "no-store"
    # Stored only as SHA-256; the session records its second step.
    stored = {
        str(r["code_sha256"])
        for r in await seed.rows(
            "SELECT code_sha256 FROM mfa_backup_codes WHERE user_id = $1", tess.person.user_id
        )
    }
    assert stored == {hashlib.sha256(c.encode()).hexdigest() for c in codes}
    assert await seed.value(
        "SELECT mfa_at IS NOT NULL FROM auth_sessions WHERE user_id = $1", tess.person.user_id
    )
    # The token was single use.
    reused = await client.post(
        "/v1/portal/auth/mfa/setup/verify",
        json={"mfa_token": token, "totp": _now_code(key["manual_key"])},
        headers={"host": tess.host},
    )
    assert reused.status_code == 410

    # The next sign-in asks for the second step (setup is never offered again).
    step = await _second_step(tess)
    assert step.state == "mfa_required"
    with pytest.raises(MfaExpired):
        await setup_second_step(tess.host, step.mfa_token)
    signed = await client.post(
        "/v1/portal/auth/mfa",
        json={"mfa_token": step.mfa_token, "totp": _now_code(key["manual_key"])},
        headers={"host": tess.host},
    )
    assert signed.status_code == 200 and signed.json()["state"] == "signed_in"
    tess_ctx = await portal_context(signed.json()["access_token"], tess.host)
    assert tess_ctx is not None and tess_ctx.user_id == tess.person.user_id
    actions = await _actions(seed, tess.tenant)
    assert actions.count("portal_mfa.enrolled") == 1
    assert actions.count("portal_mfa.verified") == 1
    assert actions.count("portal_mfa.failed") == 1
    # Nothing Restricted reaches the audit trail or the outbox.
    written = " ".join(
        str(r["row"])
        for r in await seed.rows(
            "SELECT a::text AS row FROM audit_events a WHERE tenant_id = $1 "
            "UNION ALL SELECT o::text FROM outbox o WHERE tenant_id = $1",
            tess.tenant,
        )
    )
    assert key["manual_key"] not in written
    assert not any(c in written for c in codes)


async def test_ac10_claire_a_taxpayer_is_not_asked_for_a_second_step(seed: Seeder) -> None:
    claire = await _portal(seed, "taxpayer", "client")
    assert not await mfa_required(claire.tenant, claire.person.user_id)
    challenge, code = await _code(claire)
    tokens = await verify_code(claire.host, challenge, code)
    assert tokens.landing == "home"


async def test_ac10_a_raising_slow_or_missing_predicate_makes_mfa_required(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    claire = await _portal(seed, "taxpayer", "client")

    async def raises(_tenant: TenantContext, _user: uuid.UUID) -> bool:
        raise RuntimeError("the TRI resolver is down")

    async def slow(_tenant: TenantContext, _user: uuid.UUID) -> bool:
        await asyncio.sleep(5)
        return False

    async def never(_tenant: TenantContext, _user: uuid.UUID) -> bool:
        return False

    predicates: tuple[Callable[[TenantContext, uuid.UUID], Awaitable[bool]], ...] = (raises, slow)
    monkeypatch.setattr(mfa_floor, "PREDICATE_SECONDS", 0.2)
    for predicate in predicates:
        monkeypatch.setitem(mfa_floor._REQUIREMENTS, "tri_scope", predicate)  # pyright: ignore[reportPrivateUsage] -- the slot itself
        assert await mfa_required(claire.tenant, claire.person.user_id)
        step = await _second_step(claire)
        assert step.state == "mfa_setup_required"
    monkeypatch.setitem(mfa_floor._REQUIREMENTS, "tri_scope", never)  # pyright: ignore[reportPrivateUsage] -- the slot itself
    assert not await mfa_required(claire.tenant, claire.person.user_id)
    # A floor predicate that is not registered is a floor that can't be checked: required.
    monkeypatch.delitem(mfa_floor._REQUIREMENTS, "engagement_designation")  # pyright: ignore[reportPrivateUsage] -- the slot itself
    assert await mfa_required(claire.tenant, claire.person.user_id)


@pytest.mark.parametrize(
    ("designation", "required"),
    [
        ("approver_of_record", True),
        ("signing_officer", True),
        ("ske_designee", True),
        ("primary_contact", False),
        ("tcwg_member", False),
    ],
)
async def test_ac10_signing_and_approving_designations_require_mfa(
    seed: Seeder, designation: str, required: bool
) -> None:
    ben = await _portal(seed, "contributor")
    partner = await seed.person(ben.tenant)
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind, user_id) "
        "VALUES ($1, $2, 'Ben Ashby', 'client_person', $3) RETURNING id",
        ben.tenant,
        ben.client_id,
        ben.person.user_id,
    )
    assert not await mfa_required(ben.tenant, ben.person.user_id)
    await seed.run(
        "INSERT INTO engagement_contacts (tenant_id, engagement_id, contact_id, designation, "
        "designated_by) VALUES ($1, $2, $3, $4, $5)",
        ben.tenant,
        ben.engagement,
        contact,
        designation,
        partner.user_id,
    )
    assert await mfa_required(ben.tenant, ben.person.user_id) is required


async def test_ac10_the_firm_may_widen_the_floor_and_never_narrow_it(seed: Seeder) -> None:
    claire = await _portal(seed, "taxpayer", "client")
    tess = await _portal(seed, "owner")
    await seed.run(
        "INSERT INTO portal_security_policies (tenant_id, mfa_for_all_client_users) "
        "VALUES ($1, true)",
        claire.tenant,
    )
    assert await mfa_required(claire.tenant, claire.person.user_id)
    # Tess's firm keeps the floor whatever its policy row says: no setting excludes an owner.
    await seed.run(
        "INSERT INTO portal_security_policies (tenant_id, mfa_for_all_client_users, "
        "trusted_device_days) VALUES ($1, false, 0)",
        tess.tenant,
    )
    assert await mfa_required(tess.tenant, tess.person.user_id)
    # The trusted-device ceiling is 30 days: a firm can only shorten it.
    with pytest.raises(Exception, match="check constraint"):
        await seed.run(
            "UPDATE portal_security_policies SET trusted_device_days = 31 WHERE tenant_id = $1",
            tess.tenant,
        )


async def test_ac11_a_backup_code_verifies_once(seed: Seeder) -> None:
    tess = await _portal(seed, "owner")
    _, codes = await _enrol(tess)
    step = await _second_step(tess)
    done = await second_step(tess.host, step.mfa_token, backup_code=codes[3].upper())
    assert done.tokens.access_token
    again = await _second_step(tess)
    with pytest.raises(MfaMismatch) as missed:
        await second_step(tess.host, again.mfa_token, backup_code=codes[3])
    assert missed.value.tries_left == 2
    assert (await _actions(seed, tess.tenant)).count("portal_backup_code.used") == 1
    used = await seed.value(
        "SELECT count(*) FROM mfa_backup_codes WHERE user_id = $1 AND used_at IS NOT NULL",
        tess.person.user_id,
    )
    assert used == 1


async def test_ac11_three_wrong_second_step_codes_lock_for_15_minutes(seed: Seeder) -> None:
    tess = await _portal(seed, "owner")
    secret, _ = await _enrol(tess)
    step = await _second_step(tess)
    for left in (2, 1):
        with pytest.raises(MfaMismatch) as missed:
            await second_step(tess.host, step.mfa_token, totp=_wrong(_now_code(secret)))
        assert missed.value.tries_left == left
    with pytest.raises(MfaLocked) as locked:
        await second_step(tess.host, step.mfa_token, totp=_wrong(_now_code(secret)))
    minutes = (locked.value.locked_until.timestamp() - time.time()) / 60
    assert 14 < minutes <= 15
    # Locked: the right code is refused, and so is a fresh sign-in.
    with pytest.raises(MfaLocked):
        await second_step(tess.host, step.mfa_token, totp=_now_code(secret))
    challenge, code = await _code(tess)
    with pytest.raises(SignInLocked):
        await verify_code(tess.host, challenge, code)
    assert "portal_mfa.locked" in await _actions(seed, tess.tenant)


async def test_ac11_a_right_email_code_does_not_reset_the_second_step_tries(
    seed: Seeder,
) -> None:
    tess = await _portal(seed, "owner")
    secret, _ = await _enrol(tess)
    for _ in range(2):
        step = await _second_step(tess)
        with pytest.raises(MfaMismatch):
            await second_step(tess.host, step.mfa_token, totp=_wrong(_now_code(secret)))
    step = await _second_step(tess)
    with pytest.raises(MfaLocked):
        await second_step(tess.host, step.mfa_token, totp=_wrong(_now_code(secret)))


async def test_ac11_parallel_second_step_guesses_never_get_more_than_three(seed: Seeder) -> None:
    tess = await _portal(seed, "owner")
    secret, codes = await _enrol(tess)
    step = await _second_step(tess)
    outcomes = await asyncio.gather(
        *(
            second_step(tess.host, step.mfa_token, totp=_wrong(_now_code(secret)))
            for _ in range(8)
        ),
        return_exceptions=True,
    )
    assert sum(isinstance(o, MfaMismatch) for o in outcomes) == 2
    assert sum(isinstance(o, MfaLocked) for o in outcomes) == 6
    with pytest.raises(MfaLocked):
        await second_step(tess.host, step.mfa_token, backup_code=codes[0])


async def test_ac11_the_mfa_token_lives_five_minutes_and_is_used_once(seed: Seeder) -> None:
    tess = await _portal(seed, "owner")
    secret, _ = await _enrol(tess)
    step = await _second_step(tess)
    await seed.run(
        "UPDATE sign_in_challenges SET mfa_expires_at = now() - interval '1 second' "
        "WHERE mfa_token_sha256 = $1",
        hashlib.sha256(step.mfa_token.encode()).hexdigest(),
    )
    with pytest.raises(MfaExpired):
        await second_step(tess.host, step.mfa_token, totp=_now_code(secret))
    step = await _second_step(tess)
    with pytest.raises(MfaExpired):  # a second-step token on another host
        await second_step("other.portal-example.test", step.mfa_token, totp=_now_code(secret))
    await second_step(tess.host, step.mfa_token, totp=_now_code(secret))
    with pytest.raises(MfaExpired):
        await second_step(tess.host, step.mfa_token, totp=_now_code(secret))


async def test_ac11_a_trusted_device_skips_the_second_step_for_the_firms_days(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tess = await _portal(seed, "owner")
    secret, _ = await _enrol(tess)
    step = await _second_step(tess)
    response = await client.post(
        "/v1/portal/auth/mfa",
        json={"mfa_token": step.mfa_token, "totp": _now_code(secret), "trust_device": True},
        headers={"host": tess.host, "user-agent": "Mozilla/5.0 (Macintosh) Safari/605.1.15"},
    )
    assert response.status_code == 200
    cookies = response.headers.get_list("set-cookie")
    device = next(c for c in cookies if c.startswith("__Host-abacus-portal-device="))
    assert "Max-Age=2592000" in device and "HttpOnly" in device and "Secure" in device
    value = device.split(";", 1)[0].split("=", 1)[1]
    days = await seed.value(
        "SELECT extract(epoch FROM expires_at - created_at) / 86400 FROM trusted_devices "
        "WHERE token_sha256 = $1",
        hashlib.sha256(value.encode()).hexdigest(),
    )
    assert round(float(cast(float, days))) == 30
    assert "portal_device.trusted" in await _actions(seed, tess.tenant)

    # Within the 30 days the second step is skipped.
    challenge, code = await _code(tess)
    tokens = await verify_code(tess.host, challenge, code, device_cookie=value)
    assert tokens.access_token
    # Another person's device or an unknown value is no device.
    other = await _portal(seed, "owner")
    await _enrol(other)
    assert (await _second_step(other, device_cookie=value)).state == "mfa_required"
    assert (await _second_step(tess, device_cookie="nonsense")).state == "mfa_required"
    # The firm shortens its days: a device older than that no longer counts.
    await seed.run(
        "UPDATE trusted_devices SET created_at = now() - interval '8 days' "
        "WHERE token_sha256 = $1",
        hashlib.sha256(value.encode()).hexdigest(),
    )
    await seed.run(
        "INSERT INTO portal_security_policies (tenant_id, trusted_device_days) VALUES ($1, 7)",
        tess.tenant,
    )
    assert (await _second_step(tess, device_cookie=value)).state == "mfa_required"
    await seed.run("DELETE FROM portal_security_policies WHERE tenant_id = $1", tess.tenant)
    challenge, code = await _code(tess)
    assert (await verify_code(tess.host, challenge, code, device_cookie=value)).access_token
    # Past its expiry the device is gone.
    await seed.run(
        "UPDATE trusted_devices SET expires_at = now() - interval '1 second' "
        "WHERE token_sha256 = $1",
        hashlib.sha256(value.encode()).hexdigest(),
    )
    assert (await _second_step(tess, device_cookie=value)).state == "mfa_required"


async def test_ac11_a_firm_with_zero_days_never_trusts_a_device(seed: Seeder) -> None:
    tess = await _portal(seed, "owner")
    secret, _ = await _enrol(tess)
    await seed.run(
        "INSERT INTO portal_security_policies (tenant_id, trusted_device_days) VALUES ($1, 0)",
        tess.tenant,
    )
    step = await _second_step(tess)
    done = await second_step(tess.host, step.mfa_token, totp=_now_code(secret), trust_device=True)
    assert done.device_cookie is None
    assert (
        await seed.value(
            "SELECT count(*) FROM trusted_devices WHERE user_id = $1", tess.person.user_id
        )
        == 0
    )


async def test_ac11_access_changed_ends_sessions_and_revokes_trusted_devices(
    seed: Seeder,
) -> None:
    tess = await _portal(seed, "owner")
    secret, _ = await _enrol(tess)
    step = await _second_step(tess)
    done = await second_step(tess.host, step.mfa_token, totp=_now_code(secret), trust_device=True)
    assert done.device_cookie is not None
    assert await portal_context(done.tokens.access_token, tess.host) is not None

    event = OutboxEvent(
        event_id=uuid.uuid4(),
        tenant_id=tess.tenant,
        event_type="access.changed",
        payload={"user_id": str(tess.person.user_id)},
    )
    await revoke_portal_access(event)
    await revoke_portal_access(event)  # delivered twice: nothing more happens
    assert await portal_context(done.tokens.access_token, tess.host) is None
    live = await seed.value(
        "SELECT count(*) FROM auth_sessions WHERE user_id = $1 AND ended_at IS NULL",
        tess.person.user_id,
    )
    assert live == 0
    reasons = {
        str(r["end_reason"])
        for r in await seed.rows(
            "SELECT end_reason FROM auth_sessions WHERE user_id = $1", tess.person.user_id
        )
    }
    assert reasons == {"revoked"}
    assert (await _second_step(tess, device_cookie=done.device_cookie)).state == "mfa_required"
    actions = await _actions(seed, tess.tenant)
    assert actions.count("portal_device.revoked") == 1
    assert actions.count("session.ended") == 2  # setup's session and the second step's


async def test_ac10_a_designation_on_a_contact_named_by_a_grant_requires_mfa_at_once(
    seed: Seeder,
) -> None:
    """The contact is linked only through the person's grant (`contact_id`), as invitations
    link it; designating it ends the sessions that started without the second step."""
    ben = await _portal(seed, "contributor")
    contact = await seed.value(
        "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
        "VALUES ($1, $2, 'Ben Ashby', 'client_person') RETURNING id",
        ben.tenant,
        ben.client_id,
    )
    await seed.run(
        "UPDATE client_access_grants SET contact_id = $1 WHERE user_id = $2",
        contact,
        ben.person.user_id,
    )
    challenge, code = await _code(ben)
    tokens = await verify_code(ben.host, challenge, code)  # not covered yet: no second step
    assert await portal_context(tokens.access_token, ben.host) is not None

    partner = await seed.person(ben.tenant)
    await seed.member(ben.engagement, partner, "engagement_partner")
    assert await designate_contact(
        partner.context(), ben.engagement, cast(uuid.UUID, contact), "signing_officer"
    )
    assert await mfa_required(ben.tenant, ben.person.user_id)
    payloads = await seed.rows(
        "SELECT id, payload FROM outbox WHERE tenant_id = $1 AND event_type = 'access.changed'",
        ben.tenant,
    )
    assert [json.loads(r["payload"])["user_id"] for r in payloads] == [str(ben.person.user_id)]
    await revoke_portal_access(
        OutboxEvent(
            event_id=cast(uuid.UUID, payloads[0]["id"]),
            tenant_id=ben.tenant,
            event_type="access.changed",
            payload=json.loads(payloads[0]["payload"]),
        )
    )
    assert await portal_context(tokens.access_token, ben.host) is None
    assert (await _second_step(ben)).state == "mfa_setup_required"


async def test_ac11_second_step_guesses_are_the_persons_across_firms(seed: Seeder) -> None:
    """One factor, one count: a client of two firms gets three wrong codes in all, not three per
    firm."""
    tess = await _portal(seed, "owner")
    secret, _ = await _enrol(tess)
    other = await seed.firm()
    host = f"ashgrove-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(other, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, other, host, "default")
        await activate_portal_host(tx, other, host)
    partner = await seed.person(other)
    entity = await seed.entity(other)
    engagement = await seed.engagement(other, entity, partner.user_id)
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status, kind) "
        "VALUES ($1, $2, NULL, 'active', 'client')",
        other,
        tess.person.user_id,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'engagement', $3)",
        other,
        tess.person.user_id,
        engagement,
    )
    elsewhere = Portal(other, host, tess.person, tess.email, tess.client_id, engagement)
    for portal in (tess, tess):
        step = await _second_step(portal)
        with pytest.raises(MfaMismatch):
            await second_step(portal.host, step.mfa_token, totp=_wrong(_now_code(secret)))
    step = await _second_step(elsewhere)
    assert step.state == "mfa_required"  # the factor is the person's, not the firm's
    with pytest.raises(MfaLocked):
        await second_step(host, step.mfa_token, totp=_wrong(_now_code(secret)))
    # Locked in the first firm too, even with the right code.
    step = await _second_step(tess)
    with pytest.raises(MfaLocked):
        await second_step(tess.host, step.mfa_token, totp=_now_code(secret))
