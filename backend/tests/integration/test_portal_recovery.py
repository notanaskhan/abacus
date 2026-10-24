"""P-08-T21 against Postgres (SPEC-320 AC-14, AC-18 to AC-20; epic Stories 5.1, 7.1 to 7.3):
secure links and their renewal, firm-side unlock and MFA reset, and the per-firm sign-in pause.

Acceptance: an expired reminder link renews to the same address with an identical response for
any token, unlock and reset deny the agent principal, and the pause takes effect within 10
seconds. Links are single use and stored as hashes only; every bad link answers the same 404;
portal sessions stay host-pinned (ADR-168) and the MFA floor (P-08-T17) still holds after a
reset."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel import controls
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.communications import secure_links
from abacus.modules.communications.api import (
    FakeSesTransport,
    configure_transport,
    issue_secure_link,
    resolve_secure_link,
)
from abacus.modules.communications.secure_links import deliver_renewed_link
from abacus.modules.communications.sign_in_codes import deliver_mfa_reset_notice
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.identity import portal_mfa, portal_session
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp, totp_at
from abacus.modules.identity.portal_mfa import (
    MfaExpired,
    MfaLocked,
    MfaMismatch,
    second_step,
    setup_second_step,
    verify_setup,
)
from abacus.modules.identity.portal_session import (
    SecondStepRequired,
    issue_sign_in_code,
    portal_context,
    start_sign_in,
    verify_code,
)
from abacus.modules.organisations import contacts as contacts_service
from abacus.modules.portal.branding import activate_portal_host, add_portal_host
from abacus_tools.harness.mailbox import LocalMailboxReader

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

RENEWED_BODY = "{{firm_name}} sent you a new link: {{app_link}}"
RESET_BODY = "{{firm_name}} reset your two-step verification."


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
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
    monkeypatch.setattr(secure_links, "FLOOR_SECONDS", 0.0)
    configure_portal_idp(InMemoryPortalIdp())
    configure_transport(FakeSesTransport(tmp_path / "mailbox"))
    controls.forget_controls()
    yield
    controls.forget_controls()
    configure_transport(None)
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
    contact_id: uuid.UUID


async def _portal(seed: Seeder, role: str = "owner") -> Portal:
    """A firm with an active portal host and one client person, bound to a contact, holding one
    grant on the client."""
    tenant = await seed.firm()
    host = f"brightwaterhale-{uuid.uuid4().hex[:8]}.portal-example.test"
    ctx = TenantContext(tenant, "human", str(uuid.uuid4()))
    async with uow(ctx) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    partner = await seed.person(tenant)
    entity = await seed.entity(tenant)
    await seed.engagement(tenant, entity, partner.user_id)
    client_id = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    )
    person = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        person.user_id,
    )
    await seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, $3, 'client', $4)",
        tenant,
        person.user_id,
        role,
        client_id,
    )
    email = cast(str, await seed.value("SELECT email FROM users WHERE id = $1", person.user_id))
    contact_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, email, contact_kind, "
            "user_id, portal_state) VALUES ($1, $2, 'Tess Moreno', $3, 'client_person', $4, "
            "'active') RETURNING id",
            tenant,
            client_id,
            email,
            person.user_id,
        ),
    )
    return Portal(tenant, host, person, email, client_id, contact_id)


async def _staff(seed: Seeder, p: Portal, firm_role: str = "security_admin") -> AuthContext:
    who = await seed.person(p.tenant)
    await seed.run(
        "UPDATE memberships SET firm_role = $3 WHERE tenant_id = $1 AND user_id = $2",
        p.tenant,
        who.user_id,
        firm_role,
    )
    return AuthContext(
        TenantContext(p.tenant, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        firm_role,  # pyright: ignore[reportArgumentType] -- a FirmRole code
        datetime.now(UTC) - timedelta(minutes=1),
    )


async def _templates() -> None:
    await import_platform_version(
        "staff-p08t21",
        "portal.link_renewed",
        "en-US",
        "A new link",
        RENEWED_BODY,
        ["firm_name", "app_link"],
    )
    await import_platform_version(
        "staff-p08t21",
        "portal.mfa_reset_notice",
        "en-US",
        "Two-step reset",
        RESET_BODY,
        ["firm_name"],
    )


async def _outbox(seed: Seeder, tenant: uuid.UUID, event_type: str) -> list[OutboxEvent]:
    rows = await seed.rows(
        "SELECT id, payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 ORDER BY id",
        tenant,
        event_type,
    )
    return [
        OutboxEvent(
            event_id=cast(uuid.UUID, r["id"]),
            tenant_id=tenant,
            event_type=event_type,
            payload=json.loads(r["payload"]),
        )
        for r in rows
    ]


async def _actions(seed: Seeder, tenant: uuid.UUID) -> list[str]:
    rows = await seed.rows(
        "SELECT action FROM audit_events WHERE tenant_id = $1 ORDER BY occurred_at, id", tenant
    )
    return [str(r["action"]) for r in rows]


async def _expire(seed: Seeder, link_id: uuid.UUID) -> None:
    await seed.run(
        "UPDATE secure_links SET issued_at = now() - interval '20 days', "
        "expires_at = now() - interval '6 days' WHERE id = $1",
        link_id,
    )


# --- AC-14: links and renewal ------------------------------------------------------------------


async def test_ac14_a_link_is_kept_only_as_its_hash_and_resolves_while_live(seed: Seeder) -> None:
    tess = await _portal(seed)
    issued = await issue_secure_link(
        tess.tenant, contact_id=tess.contact_id, purpose="reminder", recipient_email=tess.email
    )
    stored = await seed.rows(
        "SELECT token_sha256, recipient_email, expires_at - issued_at AS life "
        "FROM secure_links WHERE id = $1",
        issued.link_id,
    )
    assert stored[0]["token_sha256"] == hashlib.sha256(issued.token.encode()).hexdigest()
    assert issued.token not in json.dumps([dict(r) for r in stored], default=str)
    assert stored[0]["life"] == timedelta(days=14)
    found = await resolve_secure_link(tess.tenant, issued.token)
    assert found is not None and found.contact_id == tess.contact_id
    assert await resolve_secure_link(tess.tenant, "not-a-token") is None
    await _expire(seed, issued.link_id)
    assert await resolve_secure_link(tess.tenant, issued.token) is None
    assert "secure_link.issued" in await _actions(seed, tess.tenant)


async def test_ac14_every_bad_link_answers_the_same_404_and_a_good_one_is_single_use(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tess = await _portal(seed, "contributor")
    other = await _portal(seed, "contributor")
    good = await issue_secure_link(
        tess.tenant, contact_id=tess.contact_id, purpose="reminder", recipient_email=tess.email
    )
    expired = await issue_secure_link(
        tess.tenant, contact_id=tess.contact_id, purpose="reminder", recipient_email=tess.email
    )
    await _expire(seed, expired.link_id)
    revoked = await issue_secure_link(
        tess.tenant, contact_id=tess.contact_id, purpose="reminder", recipient_email=tess.email
    )
    await seed.run("UPDATE secure_links SET revoked_at = now() WHERE id = $1", revoked.link_id)
    elsewhere = await issue_secure_link(
        other.tenant, contact_id=other.contact_id, purpose="reminder", recipient_email=other.email
    )

    async def start(token: str, email: str = tess.email) -> httpx.Response:
        return await client.post(
            "/v1/portal/auth/start",
            json={"email": email, "link_token": token},
            headers={"host": tess.host},
        )

    # Another address leaves a live link unused, with the ordinary 202.
    assert (await start(good.token, "someone@example.test")).status_code == 202
    # The address it was sent to uses it; from then on it is like any bad link.
    used = await start(good.token)
    assert used.status_code == 202
    bad = [
        await start(t)
        for t in (good.token, expired.token, revoked.token, elsewhere.token, "x" * 43)
    ]
    assert {r.status_code for r in bad} == {404}
    assert {r.content for r in bad} == {b'{"detail":"link_expired"}'}
    assert await seed.value(
        "SELECT used_at IS NOT NULL FROM secure_links WHERE id = $1", good.link_id
    )


async def test_ac14_an_expired_reminder_renews_to_the_same_address_with_one_answer_for_any_token(
    seed: Seeder, client: httpx.AsyncClient, tmp_path: Path
) -> None:
    await _templates()
    tess = await _portal(seed)
    issued = await issue_secure_link(
        tess.tenant,
        contact_id=tess.contact_id,
        purpose="reminder",
        recipient_email=tess.email,
        host=tess.host,
    )
    await _expire(seed, issued.link_id)
    # The contact's address changes after the email went out: the renewal still goes only to
    # the address the old link was sent to.
    await seed.run(
        "UPDATE contacts SET email = 'changed@example.test' WHERE id = $1", tess.contact_id
    )

    async def renew(token: str, host: str = tess.host) -> httpx.Response:
        return await client.post(
            "/v1/portal/links/renew", json={"link_token": token}, headers={"host": host}
        )

    answers = [
        await renew(issued.token),
        await renew("unknown-token"),
        await renew(issued.token, "other.portal-example.test"),
    ]
    assert {r.status_code for r in answers} == {202}
    assert {r.content for r in answers} == {b'{"accepted":true}'}
    assert {r.headers["cache-control"] for r in answers} == {"no-store"}

    events = await _outbox(seed, tess.tenant, "portal.link_renew_requested")
    assert len(events) == 1
    await deliver_renewed_link(events[0])
    await deliver_renewed_link(events[0])  # delivered twice: one email, one token
    mail = LocalMailboxReader(tmp_path / "mailbox").messages()
    assert [m.to for m in mail] == [tess.email.lower()]
    token = mail[0].body.rsplit("#link=", 1)[1].strip()
    assert mail[0].body.startswith(f"Firm {tess.tenant.hex[:8]} sent you a new link: https://")
    renewed = await resolve_secure_link(tess.tenant, token)
    assert renewed is not None and renewed.purpose == "reminder"
    assert renewed.contact_id == tess.contact_id
    rows = await seed.rows(
        "SELECT token_sha256 FROM secure_links WHERE renewed_from_id = $1", issued.link_id
    )
    assert [r["token_sha256"] for r in rows] == [hashlib.sha256(token.encode()).hexdigest()]
    actions = await _actions(seed, tess.tenant)
    assert actions.count("secure_link.renewed") == 1
    assert actions.count("secure_link.token_issued") == 1


async def test_ac14_renewal_is_limited_to_three_an_hour_and_never_for_a_revoked_link(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tess = await _portal(seed)
    issued = await issue_secure_link(
        tess.tenant,
        contact_id=tess.contact_id,
        purpose="reminder",
        recipient_email=tess.email,
        host=tess.host,
    )
    for _ in range(5):
        answer = await client.post(
            "/v1/portal/links/renew",
            json={"link_token": issued.token},
            headers={"host": tess.host},
        )
        assert answer.status_code == 202
    assert len(await _outbox(seed, tess.tenant, "portal.link_renew_requested")) == 3
    revoked = await issue_secure_link(
        tess.tenant, contact_id=tess.contact_id, purpose="reminder", recipient_email=tess.email
    )
    await seed.run("UPDATE secure_links SET revoked_at = now() WHERE id = $1", revoked.link_id)
    await client.post(
        "/v1/portal/links/renew", json={"link_token": revoked.token}, headers={"host": tess.host}
    )
    assert len(await _outbox(seed, tess.tenant, "portal.link_renew_requested")) == 3


async def test_ac14_an_expired_invitation_renews_at_most_twice_and_a_revoked_one_never(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    tess = await _portal(seed)
    engagement = cast(
        uuid.UUID,
        await seed.value("SELECT id FROM engagements WHERE tenant_id = $1 LIMIT 1", tess.tenant),
    )
    inviter = await seed.person(tess.tenant)

    async def invitation(status: str = "pending") -> tuple[uuid.UUID, str]:
        made = cast(
            uuid.UUID,
            await seed.value(
                "INSERT INTO client_invitations (tenant_id, engagement_id, email, role, "
                "invited_by, expires_at, status) VALUES ($1, $2, $3, 'client_contributor', $4, "
                "now() - interval '1 day', $5) RETURNING id",
                tess.tenant,
                engagement,
                f"{uuid.uuid4().hex[:8]}@example.test",
                inviter.user_id,
                status,
            ),
        )
        token = uuid.uuid4().hex + uuid.uuid4().hex
        await seed.run(
            "INSERT INTO invitation_tokens (token_hash, tenant_id, invitation_id) "
            "VALUES ($1, $2, $3)",
            hashlib.sha256(token.encode()).hexdigest(),
            tess.tenant,
            made,
        )
        return made, token

    async def renew(token: str) -> None:
        answer = await client.post(
            "/v1/portal/links/renew", json={"link_token": token}, headers={"host": tess.host}
        )
        assert answer.status_code == 202

    pending, token = await invitation()
    await renew(token)
    # Renewing voids the old token; the next one comes at delivery. Expire it again to renew.
    for _ in range(3):
        await seed.run(
            "UPDATE client_invitations SET expires_at = now() - interval '1 day' WHERE id = $1",
            pending,
        )
        await seed.run(
            "INSERT INTO invitation_tokens (token_hash, tenant_id, invitation_id) "
            "VALUES ($1, $2, $3) ON CONFLICT (invitation_id) DO UPDATE SET token_hash = "
            "EXCLUDED.token_hash",
            hashlib.sha256(token.encode()).hexdigest(),
            tess.tenant,
            pending,
        )
        await renew(token)
    assert (
        await seed.value("SELECT renewal_count FROM client_invitations WHERE id = $1", pending)
        == 2
    )
    issued = await _outbox(seed, tess.tenant, "client_invitation.issued")
    assert len(issued) == 2
    revoked, revoked_token = await invitation("revoked")
    await renew(revoked_token)
    assert (
        await seed.value("SELECT renewal_count FROM client_invitations WHERE id = $1", revoked)
        == 0
    )
    assert (await _actions(seed, tess.tenant)).count("client_invitation.renewed") == 2


# --- AC-18, AC-19: unlock and MFA reset --------------------------------------------------------


async def _enrol(p: Portal) -> tuple[str, str]:
    """Enrol a factor on a first sign-in; the authenticator's secret and the session token."""
    started = await start_sign_in(p.host, p.email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    with pytest.raises(SecondStepRequired) as asked:
        await verify_code(p.host, started.challenge_id, issued.code)
    key = await setup_second_step(p.host, asked.value.mfa_token)
    done = await verify_setup(p.host, asked.value.mfa_token, totp_at(key.manual_key, time.time()))
    return key.manual_key, done.tokens.access_token


async def _second_step(p: Portal) -> SecondStepRequired:
    started = await start_sign_in(p.host, p.email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    with pytest.raises(SecondStepRequired) as asked:
        await verify_code(p.host, started.challenge_id, issued.code)
    return asked.value


async def test_ac19_the_reset_removes_the_factor_codes_and_devices_and_the_next_sign_in_sets_up(
    seed: Seeder, tmp_path: Path
) -> None:
    await _templates()
    tess = await _portal(seed)
    secret, session = await _enrol(tess)
    step = await _second_step(tess)
    assert step.state == "mfa_required"
    trusted = await second_step(
        tess.host, step.mfa_token, totp=totp_at(secret, time.time()), trust_device=True
    )
    assert trusted.device_cookie is not None
    felix = await _staff(seed, tess)

    done = await contacts_service.mfa_reset(felix, tess.client_id, tess.contact_id)
    assert done.trusted_devices_revoked == 1 and done.mfa_enrolled is False
    assert (
        await seed.value(
            "SELECT count(*) FROM mfa_factors WHERE user_id = $1", tess.person.user_id
        )
        == 0
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM mfa_backup_codes WHERE user_id = $1", tess.person.user_id
        )
        == 0
    )
    assert (
        await seed.value(
            "SELECT revoked_reason FROM trusted_devices WHERE user_id = $1", tess.person.user_id
        )
        == "mfa_reset"
    )
    # Its sessions in the firm ended; the MFA floor still holds: the next sign-in enrols again.
    assert await portal_context(session, tess.host) is None
    assert (await _second_step(tess)).state == "mfa_setup_required"
    actions = await _actions(seed, tess.tenant)
    assert actions.count("portal_mfa.reset") == 1
    rows = await seed.rows(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 AND action = 'portal_mfa.reset'",
        tess.tenant,
    )
    assert rows[0]["actor_id"] == str(felix.user_id)  # INV-5: names the person
    notices = await _outbox(seed, tess.tenant, "portal_mfa.reset_notice_requested")
    await deliver_mfa_reset_notice(notices[0])
    mail = LocalMailboxReader(tmp_path / "mailbox").messages()
    assert [m.to for m in mail] == [tess.email]
    assert mail[0].body == f"Firm {tess.tenant.hex[:8]} reset your two-step verification."


async def test_ac18_ac19_unlock_and_reset_deny_the_agent_and_system_principals(
    seed: Seeder,
) -> None:
    tess = await _portal(seed)
    felix = await _staff(seed, tess)
    for kind in ("agent", "system"):
        ctx = AuthContext(
            TenantContext(tess.tenant, kind, "probe"),
            felix.user_id,
            uuid.uuid4(),
            "security_admin",
            datetime.now(UTC),
        )
        with pytest.raises(Forbidden):
            await contacts_service.mfa_reset(ctx, tess.client_id, tess.contact_id)
        with pytest.raises(Forbidden):
            await contacts_service.portal_unlock(ctx, tess.client_id, tess.contact_id)
    assert "portal_mfa.reset" not in await _actions(seed, tess.tenant)


async def test_ac18_unlock_clears_the_sign_in_and_second_step_locks_naming_the_person(
    seed: Seeder,
) -> None:
    tess = await _portal(seed)
    secret, _ = await _enrol(tess)
    step = await _second_step(tess)
    for _ in range(3):
        with pytest.raises((MfaMismatch, MfaLocked, MfaExpired)):
            await second_step(tess.host, step.mfa_token, totp="000000")
    locked = await seed.value(
        "SELECT mfa_locked_until > now() FROM mfa_factors WHERE user_id = $1", tess.person.user_id
    )
    assert locked is True
    grace = await _staff(seed, tess, "firm_admin")
    await contacts_service.portal_unlock(grace, tess.client_id, tess.contact_id)
    assert (
        await seed.value(
            "SELECT mfa_locked_until FROM mfa_factors WHERE user_id = $1", tess.person.user_id
        )
        is None
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM sign_in_locks "
            "WHERE host_tenant_id = $1 AND locked_until > now()",
            tess.tenant,
        )
        == 0
    )
    fresh = await _second_step(tess)
    done = await second_step(tess.host, fresh.mfa_token, totp=totp_at(secret, time.time()))
    assert done.tokens.access_token
    rows = await seed.rows(
        "SELECT actor_id FROM audit_events WHERE tenant_id = $1 AND action = 'contact.unlocked'",
        tess.tenant,
    )
    assert [r["actor_id"] for r in rows] == [str(grace.user_id)]


async def test_ac18_a_contact_of_another_client_or_a_walled_one_answers_404(seed: Seeder) -> None:
    tess = await _portal(seed)
    felix = await _staff(seed, tess)
    with pytest.raises(NotFound):
        await contacts_service.mfa_reset(felix, uuid.uuid4(), tess.contact_id)
    with pytest.raises(NotFound):
        await contacts_service.portal_unlock(felix, uuid.uuid4(), tess.contact_id)


# --- AC-20: the pause ---------------------------------------------------------------------------


async def test_ac20_the_pause_lands_within_10_seconds_and_sessions_carry_on(
    seed: Seeder, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    claire = await _portal(seed, "contributor")
    started = await start_sign_in(claire.host, claire.email)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    tokens = await verify_code(claire.host, started.challenge_id, issued.code)
    now = [1000.0]
    monkeypatch.setattr(controls, "_clock", lambda: now[0])

    async def start() -> httpx.Response:
        return await client.post(
            "/v1/portal/auth/start", json={"email": claire.email}, headers={"host": claire.host}
        )

    assert (await start()).status_code == 202  # caches "not paused" at t=1000
    await seed.value(
        "SELECT set_platform_control('portal_sign_in', 'firm', $1, NULL, true, 'drill', "
        "'ana', NULL)",
        claire.tenant,
    )
    now[0] += controls.CACHE_SECONDS
    paused = await start()
    assert paused.status_code == 503 and paused.json() == {"detail": "sign_in_paused"}
    verify = await client.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": str(started.challenge_id), "code": "123456"},
        headers={"host": claire.host},
    )
    assert verify.status_code == 503
    # Nothing is renewed while paused (the answer is the same 202).
    link = await issue_secure_link(
        claire.tenant,
        contact_id=claire.contact_id,
        purpose="reminder",
        recipient_email=claire.email,
    )
    renewed = await client.post(
        "/v1/portal/links/renew", json={"link_token": link.token}, headers={"host": claire.host}
    )
    assert renewed.status_code == 202
    assert await _outbox(seed, claire.tenant, "portal.link_renew_requested") == []
    # Existing sessions are unaffected; another firm's sign-in is not paused.
    assert await portal_context(tokens.access_token, claire.host) is not None
    other = await _portal(seed, "contributor")
    elsewhere = await client.post(
        "/v1/portal/auth/start", json={"email": other.email}, headers={"host": other.host}
    )
    assert elsewhere.status_code == 202
    actions = await _actions(seed, claire.tenant)
    assert "platform_control.changed" in actions
    await seed.value(
        "SELECT set_platform_control('portal_sign_in', 'firm', $1, NULL, false, 'drill over', "
        "'ana', NULL)",
        claire.tenant,
    )
    now[0] += controls.CACHE_SECONDS
    assert (await start()).status_code == 202
