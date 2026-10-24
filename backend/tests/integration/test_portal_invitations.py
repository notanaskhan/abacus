"""P-08-T18 against Postgres (SPEC-320 AC-12, AC-13; DEC-35, DEC-275): the invitation preview with
one 404 for every failure, `auth/start` for a pending invitee, and acceptance creating the
template's grants in one unit of work, with the terms recorded and the inviter attributed."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.identity import invitations, portal_mfa, portal_session
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.invitations import (
    GrantTemplate,
    InvitationInvalid,
    InvitationNotFound,
    InvitationTerms,
    create_invitation,
    preview_invitation,
)
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp
from abacus.modules.identity.portal_session import (
    issue_sign_in_code,
    portal_context,
    portal_invitee,
    start_sign_in,
    verify_code,
)
from abacus.modules.identity.staff import change_role as change_firm_role
from abacus.modules.identity.staff import revoke as revoke_staff
from abacus.modules.identity.team import remove_member as remove_team_member
from abacus.modules.portal.branding import activate_portal_host, add_portal_host

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

ORG = "Keystone Retirement Services"
PLAN = "Northwind Robotics 401(k) Plan"


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
    monkeypatch.setattr(invitations, "PREVIEW_FLOOR_SECONDS", 0.0)
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
    # A fresh caller address per test: misses are counted per address across the session.
    address = f"198.51.100.{secrets.randbelow(250) + 1}-{uuid.uuid4().hex[:6]}"
    transport = httpx.ASGITransport(app=create_app(), client=(address, 4000))
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class World:
    tenant: uuid.UUID
    host: str
    inviter: Person
    engagement: uuid.UUID
    items: tuple[uuid.UUID, ...]
    contact: uuid.UUID
    invitation: uuid.UUID
    email: str
    token: str


async def _host(tenant: uuid.UUID) -> str:
    host = f"firm-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return host


async def _world(
    seed: Seeder,
    *,
    role: str = "third_party",
    scope_kind: str = "request_item",
    terms_version: int | None = 1,
    email: str | None = None,
) -> World:
    """A firm with a portal host, an engagement with three requests, and a pending v2 invitation
    for a third party at Keystone, from a partner, with its token (only the hash is stored)."""
    tenant = await seed.firm()
    host = await _host(tenant)
    inviter = await seed.person(tenant)
    entity = await seed.entity(tenant, PLAN)
    engagement = await seed.engagement(tenant, entity, inviter.user_id)
    # The inviter is the engagement's partner: `client_contact.invite` is theirs (and is
    # re-checked when the invitation is accepted).
    await seed.member(engagement, inviter, "engagement_partner")
    items = tuple([await seed.item(tenant, engagement, inviter.user_id) for _ in range(3)])
    client_id = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)
    )
    address = email or f"sam.{uuid.uuid4().hex[:8]}@example.test"
    contact = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, email, organisation_name, "
            "contact_kind, portal_state) VALUES ($1, $2, 'Sam Ortiz', $3, $4, 'third_party', "
            "'invited') RETURNING id",
            tenant,
            client_id,
            address,
            ORG,
        ),
    )
    scopes = list(items) if scope_kind == "request_item" else [entity]
    template = {"role": role, "scope_kind": scope_kind, "scope_ids": [str(s) for s in scopes]}
    invitation = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO client_invitations (tenant_id, engagement_id, email, role, invited_by, "
            "expires_at, kind, contact_id, grant_template, terms_version) VALUES ($1, $2, $3, "
            "'client_contributor', $4, now() + interval '14 days', 'delegate', $5, $6::jsonb, "
            "$7) RETURNING id",
            tenant,
            engagement,
            address,
            inviter.user_id,
            contact,
            json.dumps(template),
            terms_version,
        ),
    )
    token = secrets.token_urlsafe(32)
    await seed.run(
        "INSERT INTO invitation_tokens (token_hash, tenant_id, invitation_id) VALUES ($1, $2, $3)",
        _sha(token),
        tenant,
        invitation,
    )
    return World(tenant, host, inviter, engagement, items, contact, invitation, address, token)


async def _invitee_session(world: World) -> str:
    """Start with the invitation token, the emailed code, verify: the invitee's access token."""
    started = await start_sign_in(world.host, world.email, invitation_token=world.token)
    issued = await issue_sign_in_code(started.challenge_id)
    assert issued is not None
    tokens = await verify_code(world.host, started.challenge_id, issued.code)
    return tokens.access_token


async def _accept(
    client: httpx.AsyncClient, world: World, access: str, terms: int | None = 1
) -> httpx.Response:
    body: dict[str, object] = {"token": world.token}
    if terms is not None:
        body["terms_version"] = terms
    return await client.post(
        "/v1/invitations/accept",
        json=body,
        headers={"host": world.host, "authorization": f"Bearer {access}"},
    )


# --- AC-12: the preview ------------------------------------------------------------------------


async def test_ac12_the_preview_shows_the_firm_organisation_invitee_access_terms_and_expiry(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed)
    response = await client.post(
        "/v1/invitations/preview", json={"token": world.token}, headers={"host": world.host}
    )
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    body = response.json()
    firm = await seed.value("SELECT name FROM firms WHERE tenant_id = $1", world.tenant)
    assert body["firm_name"] == firm
    assert body["organisation_name"] == ORG and body["invitee_name"] == "Sam Ortiz"
    assert body["invitee_email"] == world.email
    assert body["access"] == {"kind": "delegate", "item_count": 3, "scope_label": PLAN}
    assert body["terms_version"] == 1 and body["terms_url"] is None
    assert body["expires_at"]
    assert "accrued" not in response.text.casefold()


async def test_ac12_every_failure_answers_the_same_404(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    async def preview(token: str, host: str) -> httpx.Response:
        return await client.post(
            "/v1/invitations/preview", json={"token": token}, headers={"host": host}
        )

    world = await _world(seed)
    other = await _world(seed)
    expired = await _world(seed)
    await seed.run(
        "UPDATE client_invitations SET expires_at = now() - interval '1 second' WHERE id = $1",
        expired.invitation,
    )
    revoked = await _world(seed)
    await seed.run(
        "UPDATE client_invitations SET status = 'revoked' WHERE id = $1", revoked.invitation
    )
    staff = await _world(seed)
    staff_email = await seed.value("SELECT email FROM users WHERE id = $1", staff.inviter.user_id)
    await seed.run(
        "UPDATE client_invitations SET email = $2 WHERE id = $1", staff.invitation, staff_email
    )
    answers = [
        await preview(secrets.token_urlsafe(32), world.host),  # unknown
        await preview("short", world.host),  # malformed
        await preview(other.token, world.host),  # another firm's token on this host
        await preview(world.token, "unknown.portal-example.test"),  # a host no firm has
        await preview(expired.token, expired.host),  # past 14 days
        await preview(revoked.token, revoked.host),
        await preview(staff.token, staff.host),  # addressed to a staff member of the firm
    ]
    assert {a.status_code for a in answers} == {404}
    assert {a.text for a in answers} == {answers[0].text}


async def test_ac12_misses_are_counted_per_address_and_then_nothing_is_found(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    address = f"203.0.113.{uuid.uuid4().hex[:6]}"
    for _ in range(10):
        with pytest.raises(InvitationNotFound):
            await preview_invitation(world.host, secrets.token_urlsafe(32), address)
    with pytest.raises(InvitationNotFound):
        await preview_invitation(world.host, world.token, address)  # held for 15 minutes
    found = await preview_invitation(world.host, world.token, f"{address}-other")
    assert found.access.item_count == 3
    # Only digests of the address are kept.
    kept = await seed.rows("SELECT identity_hash FROM invitation_failures")
    assert all(address not in str(r["identity_hash"]) for r in kept)


# --- auth/start for a pending invitee ----------------------------------------------------------


async def _code_events(seed: Seeder, tenant: uuid.UUID) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 "
            "AND event_type = 'portal.sign_in_code_requested'",
            tenant,
        ),
    )


async def test_start_with_the_invitation_token_sends_the_invitee_a_code_and_nothing_else(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed)
    shapes = set[frozenset[str]]()
    for email, token in (
        (world.email, secrets.token_urlsafe(32)),  # a wrong token: the ordinary start
        ("someone.else@example.test", world.token),  # the token, another address
    ):
        response = await client.post(
            "/v1/portal/auth/start",
            json={"email": email, "invitation_token": token},
            headers={"host": world.host},
        )
        assert response.status_code == 202
        shapes.add(frozenset(cast(dict[str, object], response.json())))
    assert await _code_events(seed, world.tenant) == 0
    response = await client.post(
        "/v1/portal/auth/start",
        json={"email": world.email.upper(), "invitation_token": world.token},
        headers={"host": world.host},
    )
    assert response.status_code == 202
    shapes.add(frozenset(cast(dict[str, object], response.json())))
    assert shapes == {frozenset({"challenge_id", "code_expires_at", "resend_available_at"})}
    assert await _code_events(seed, world.tenant) == 1
    # The invitee holds a user row, and no membership until they accept.
    user = await seed.value("SELECT id FROM users WHERE lower(email) = lower($1)", world.email)
    assert user is not None
    assert await seed.value("SELECT count(*) FROM memberships WHERE user_id = $1", user) == 0


async def test_the_invitees_session_authorises_nothing_before_acceptance(seed: Seeder) -> None:
    world = await _world(seed)
    access = await _invitee_session(world)
    assert await portal_context(access, world.host) is None  # no membership, no grant
    invitee = await portal_invitee(access, world.host)
    assert invitee is not None and invitee.tenant_id == world.tenant
    assert await portal_invitee(access, "other.portal-example.test") is None


# --- AC-13: acceptance -------------------------------------------------------------------------


async def test_ac13_acceptance_creates_the_template_grants_attributed_to_the_inviter(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed)
    access = await _invitee_session(world)
    response = await _accept(client, world, access)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["tenant_id"] == str(world.tenant)
    assert body["session"]["state"] == "signed_in" and body["session"]["landing"] == "requests"
    invitee = await portal_invitee(access, world.host)
    assert invitee is not None
    user = invitee.user_id
    grants = await seed.rows(
        "SELECT role, scope_kind, scope_id, granted_by, contact_id FROM client_access_grants "
        "WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        user,
    )
    assert sorted(g["scope_id"] for g in grants) == sorted(world.items)
    assert {(g["role"], g["scope_kind"]) for g in grants} == {("third_party", "request_item")}
    assert {g["granted_by"] for g in grants} == {world.inviter.user_id}
    assert {g["contact_id"] for g in grants} == {world.contact}
    events = await seed.rows(
        "SELECT by_user_id FROM client_access_events WHERE tenant_id = $1", world.tenant
    )
    assert {e["by_user_id"] for e in events} == {world.inviter.user_id}
    row = await seed.rows(
        "SELECT status, accepted_by, terms_accepted_at FROM client_invitations WHERE id = $1",
        world.invitation,
    )
    assert row[0]["status"] == "accepted" and row[0]["accepted_by"] == user
    assert row[0]["terms_accepted_at"] is not None
    contact = await seed.rows(
        "SELECT portal_state, user_id FROM contacts WHERE id = $1", world.contact
    )
    assert (contact[0]["portal_state"], contact[0]["user_id"]) == ("active", user)
    assert (
        await seed.value(
            "SELECT count(*) FROM invitation_tokens WHERE invitation_id = $1", world.invitation
        )
        == 0
    )  # single use
    # INV-5: the acceptance and each grant are attributed to the inviting person.
    audit = await seed.rows(
        "SELECT action, actor_kind, on_behalf_of_user_id FROM audit_events WHERE tenant_id = $1 "
        "AND action IN ('client_invitation.accepted', 'client_access.granted')",
        world.tenant,
    )
    assert sorted(a["action"] for a in audit) == ["client_access.granted"] * 3 + [
        "client_invitation.accepted"
    ]
    assert {a["on_behalf_of_user_id"] for a in audit} == {world.inviter.user_id}
    # No `access.changed`: the session the invitee accepted with carries on.
    assert (
        await seed.value(
            "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'access.changed'",
            world.tenant,
        )
        == 0
    )
    ctx = await portal_context(access, world.host)
    assert ctx is not None and ctx.user_id == user


async def test_ac13_a_reused_token_wrong_terms_or_expired_invitation_gets_the_same_404(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed)
    access = await _invitee_session(world)
    wrong_terms = await _accept(client, world, access, terms=2)
    no_terms = await _accept(client, world, access, terms=None)
    assert (wrong_terms.status_code, no_terms.status_code) == (404, 404)
    assert (
        await seed.value("SELECT status FROM client_invitations WHERE id = $1", world.invitation)
        == "pending"
    )
    assert (await _accept(client, world, access)).status_code == 200
    reused = await _accept(client, world, access)
    assert reused.status_code == 404 and reused.text == wrong_terms.text

    late = await _world(seed)
    late_access = await _invitee_session(late)
    await seed.run(
        "UPDATE client_invitations SET expires_at = now() - interval '1 second' WHERE id = $1",
        late.invitation,
    )
    expired = await _accept(client, late, late_access)
    assert expired.status_code == 404 and expired.text == wrong_terms.text
    # A session from another firm's host is no session here (ADR-168 §3).
    other = await _world(seed)
    other_access = await _invitee_session(other)
    fresh = await _world(seed, email=other.email)
    assert (await _accept(client, fresh, other_access)).status_code == 401


async def test_ac13_one_unit_of_work_a_bad_scope_writes_nothing(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed)
    access = await _invitee_session(world)
    # The last scope is no longer the engagement's (another engagement's request).
    stray = await _world(seed)
    await seed.run(
        "UPDATE client_invitations SET grant_template = "
        "jsonb_set(grant_template, '{scope_ids,2}', to_jsonb($2::text)) WHERE id = $1",
        world.invitation,
        str(stray.items[0]),
    )
    response = await _accept(client, world, access)
    assert response.status_code == 404
    assert (
        await seed.value(
            "SELECT count(*) FROM client_access_grants WHERE tenant_id = $1", world.tenant
        )
        == 0
    )
    assert (
        await seed.value("SELECT status FROM client_invitations WHERE id = $1", world.invitation)
        == "pending"
    )
    assert (
        await seed.value("SELECT portal_state FROM contacts WHERE id = $1", world.contact)
        == "invited"
    )


async def test_acceptance_ends_the_invitees_other_sessions_in_the_firm(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed)
    earlier = await _invitee_session(world)
    access = await _invitee_session(world)
    assert (await _accept(client, world, access)).status_code == 200
    assert await portal_invitee(earlier, world.host) is None
    assert await portal_context(access, world.host) is not None


async def test_an_owner_template_asks_for_the_second_step_after_acceptance(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed, role="owner", scope_kind="client_entity", terms_version=None)
    access = await _invitee_session(world)
    response = await _accept(client, world, access, terms=None)
    assert response.status_code == 200, response.text
    session = response.json()["session"]
    assert session["state"] == "mfa_setup_required" and session["mfa_token"]
    assert "access_token" not in session or session["access_token"] is None
    assert await portal_invitee(access, world.host) is None  # no session without the step
    setup = await client.post(
        "/v1/portal/auth/mfa/setup",
        json={"mfa_token": session["mfa_token"]},
        headers={"host": world.host},
    )
    assert setup.status_code == 200 and setup.json()["otpauth_uri"].startswith("otpauth://")


async def test_ac13_one_unit_of_work_a_failure_after_the_grants_rolls_them_back(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    world = await _world(seed)
    access = await _invitee_session(world)
    someone = await seed.person(world.tenant)
    await seed.run(
        "UPDATE contacts SET user_id = $2 WHERE id = $1", world.contact, someone.user_id
    )  # the contact is already someone else's: activation, after the grants, fails
    response = await _accept(client, world, access)
    assert response.status_code == 404
    assert (
        await seed.value(
            "SELECT count(*) FROM client_access_grants WHERE tenant_id = $1", world.tenant
        )
        == 0
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM memberships WHERE tenant_id = $1 AND kind = 'client'",
            world.tenant,
        )
        == 0
    )
    assert (
        await seed.value("SELECT status FROM client_invitations WHERE id = $1", world.invitation)
        == "pending"
    )


async def test_create_invitation_v2_stores_a_template_within_the_engagement_only(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    stray = await _world(seed)
    ctx = AuthContext(
        tenant=TenantContext(world.tenant, "human", str(world.inviter.user_id)),
        user_id=world.inviter.user_id,
        membership_id=uuid.uuid4(),
        firm_role="firm_admin",
        mfa_at=None,
    )
    template = GrantTemplate("third_party", "request_item", world.items[:2])
    async with uow(ctx.tenant) as tx:
        created = await create_invitation(
            tx,
            ctx,
            world.engagement,
            "next.person@example.test",
            "client_contributor",
            kind="delegate",
            contact_id=world.contact,
            template=template,
            terms=InvitationTerms(2, "https://firm.example/terms"),
        )
    [row] = await seed.rows(
        "SELECT kind, grant_template::text AS t, terms_version, terms_url, "
        "expires_at - created_at AS span FROM client_invitations WHERE id = $1",
        created,
    )
    assert (row["kind"], row["terms_version"], row["terms_url"]) == (
        "delegate",
        2,
        "https://firm.example/terms",
    )
    assert json.loads(row["t"])["scope_ids"] == [str(i) for i in world.items[:2]]
    assert row["span"].days == 13 or row["span"].days == 14  # DEC-35: 14 days
    foreign = GrantTemplate("third_party", "request_item", (stray.items[0],))
    with pytest.raises(InvitationInvalid):
        async with uow(ctx.tenant) as tx:
            await create_invitation(
                tx,
                ctx,
                world.engagement,
                "x@example.test",
                "client_contributor",
                template=foreign,
            )


# --- Security review fixes (DEC-277) ------------------------------------------------------------


async def _refusals(seed: Seeder, world: World) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 "
            "AND action = 'client_invitation.accept_refused' AND target_id = $2",
            world.tenant,
            str(world.invitation),
        ),
    )


async def _granted(seed: Seeder, world: World) -> int:
    return cast(
        int,
        await seed.value(
            "SELECT count(*) FROM client_access_grants WHERE tenant_id = $1", world.tenant
        ),
    )


@pytest.mark.parametrize("change", ["offboarded", "walled", "removed", "archived"])
async def test_inv5_acceptance_rechecks_the_inviters_authority(
    seed: Seeder, client: httpx.AsyncClient, change: str
) -> None:
    """An inviter who no longer may invite (offboarded, walled from the client, off the
    engagement, or the engagement archived) grants nothing: the same 404, and a refusal on the
    record. The state is changed directly, past the services that also revoke eagerly."""
    world = await _world(seed)
    access = await _invitee_session(world)
    if change == "offboarded":
        await seed.revoke(world.inviter)
    elif change == "walled":
        await seed.run(
            "INSERT INTO ethical_walls (tenant_id, user_id, client_id, created_by) "
            "SELECT tenant_id, $2, client_id, $2 FROM engagements WHERE id = $1",
            world.engagement,
            world.inviter.user_id,
        )
    elif change == "removed":
        await seed.unmember(world.engagement, world.inviter)
    else:
        await seed.run(
            "UPDATE engagements SET status = 'archived' WHERE id = $1", world.engagement
        )
    response = await _accept(client, world, access)
    assert response.status_code == 404 and response.json() == {"detail": "not found"}
    assert await _granted(seed, world) == 0
    assert (
        await seed.value("SELECT status FROM client_invitations WHERE id = $1", world.invitation)
        == "pending"
    )
    assert await _refusals(seed, world) == 1


async def _admin(seed: Seeder, tenant: uuid.UUID) -> AuthContext:
    admin = await seed.person(tenant)
    await seed.run(
        "UPDATE memberships SET firm_role = 'firm_admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        admin.user_id,
    )
    membership = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            tenant,
            admin.user_id,
        ),
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(admin.user_id)),
        user_id=admin.user_id,
        membership_id=membership,
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("change", ["revoked", "role_changed"])
async def test_inv5_offboarding_or_a_role_change_revokes_the_persons_pending_invitations(
    seed: Seeder, client: httpx.AsyncClient, change: str
) -> None:
    world = await _world(seed)
    admin = await _admin(seed, world.tenant)
    if change == "revoked":
        await revoke_staff(admin, world.inviter.user_id)
    else:
        await change_firm_role(admin, world.inviter.user_id, "security_admin")
    [row] = await seed.rows(
        "SELECT status FROM client_invitations WHERE id = $1", world.invitation
    )
    assert row["status"] == "revoked"
    assert (
        await seed.value(
            "SELECT count(*) FROM invitation_tokens WHERE invitation_id = $1", world.invitation
        )
        == 0
    )
    preview = await client.post(
        "/v1/invitations/preview", json={"token": world.token}, headers={"host": world.host}
    )
    assert preview.status_code == 404


async def test_inv5_leaving_the_engagement_revokes_the_persons_invitations_there(
    seed: Seeder,
) -> None:
    world = await _world(seed)
    # A second partner removes the inviter (and keeps the engagement's last-partner rule).
    other = await seed.person(world.tenant)
    await seed.member(world.engagement, other, "engagement_partner")
    partner = AuthContext(
        tenant=TenantContext(world.tenant, "human", str(other.user_id)),
        user_id=other.user_id,
        membership_id=cast(
            uuid.UUID,
            await seed.value(
                "SELECT id FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                world.tenant,
                other.user_id,
            ),
        ),
        firm_role=None,
        mfa_at=datetime.now(UTC),
    )
    async with uow(partner.tenant) as tx:
        await remove_team_member(tx, partner, world.engagement, world.inviter.user_id)
    assert (
        await seed.value("SELECT status FROM client_invitations WHERE id = $1", world.invitation)
        == "revoked"
    )


async def test_the_floor_is_met_inside_the_acceptance_and_enforced_on_every_request(
    seed: Seeder, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An owner template: the session that accepted ends in the acceptance's own transaction,
    even if nothing after the commit runs; and a session without the second step reaches
    nothing once the person's access needs it."""
    world = await _world(seed, role="owner", scope_kind="client_entity", terms_version=None)
    access = await _invitee_session(world)

    async def crash(*_: object) -> None:
        raise RuntimeError("the process stops after the commit")

    monkeypatch.setattr(invitations, "_after_commit", crash)
    with pytest.raises(RuntimeError):
        await invitations.accept_portal_invitation(
            (await portal_invitee(access, world.host)) or pytest.fail("no invitee"),
            world.token,
            None,
        )
    assert await _granted(seed, world) == 1  # committed
    assert await portal_invitee(access, world.host) is None  # and the session ended with it
    assert await portal_context(access, world.host) is None


async def test_a_session_without_the_second_step_reaches_nothing_once_the_floor_applies(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    """Defence in depth: the floor is applied per request, not only when a session starts."""
    world = await _world(seed, role="contributor", scope_kind="client_entity", terms_version=None)
    access = await _invitee_session(world)
    assert (await _accept(client, world, access, terms=None)).status_code == 200
    ctx = await portal_context(access, world.host)
    assert ctx is not None
    entity = await seed.value(
        "SELECT client_entity_id FROM engagements WHERE id = $1", world.engagement
    )
    await seed.run(  # an owner grant arrives with no access.changed relay yet
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id) "
        "VALUES ($1, $2, 'owner', 'client_entity', $3)",
        world.tenant,
        ctx.user_id,
        entity,
    )
    assert await portal_context(access, world.host) is None


def _address_headers(world: World, viewer: str) -> dict[str, str]:
    return {"host": world.host, "cloudfront-viewer-address": f"{viewer}:443"}


async def test_preview_misses_lock_only_the_viewer_that_made_them(
    seed: Seeder, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Behind CloudFront every viewer shares an edge address: the throttle is keyed on the
    viewer address CloudFront forwards, so ten misses by one viewer never block another's
    valid token."""
    monkeypatch.setattr(invitations, "trust_viewer_address", lambda: True)
    world = await _world(seed)
    for _ in range(10):
        miss = await client.post(
            "/v1/invitations/preview",
            json={"token": secrets.token_urlsafe(32)},
            headers=_address_headers(world, "192.0.2.10"),
        )
        assert miss.status_code == 404
    held = await client.post(
        "/v1/invitations/preview",
        json={"token": world.token},
        headers=_address_headers(world, "192.0.2.10"),
    )
    assert held.status_code == 404
    other = await client.post(
        "/v1/invitations/preview",
        json={"token": world.token},
        headers=_address_headers(world, "192.0.2.11"),
    )
    assert other.status_code == 200


async def test_without_a_trusted_viewer_address_misses_never_block_a_valid_token(
    seed: Seeder, client: httpx.AsyncClient
) -> None:
    """The fallback bucket is the peer and the token's digest prefix: another token's misses
    from the same edge don't hold this one; a forged viewer header is not believed."""
    world = await _world(seed)
    prefix = hashlib.sha256(world.token.encode()).hexdigest()[:4]
    misses = 0
    while misses < 12:
        guess = secrets.token_urlsafe(32)
        if hashlib.sha256(guess.encode()).hexdigest()[:4] == prefix:
            continue
        await client.post(
            "/v1/invitations/preview",
            json={"token": guess},
            headers=_address_headers(world, f"192.0.2.{misses}"),  # forged: not believed
        )
        misses += 1
    found = await client.post(
        "/v1/invitations/preview", json={"token": world.token}, headers={"host": world.host}
    )
    assert found.status_code == 200


async def test_create_invitation_refuses_a_contact_of_another_client(seed: Seeder) -> None:
    world = await _world(seed)
    stray = await _world(seed)  # another firm's contact
    elsewhere = await seed.entity(world.tenant, "Another client's plan")
    other_client = await seed.value(
        "SELECT client_id FROM client_entities WHERE id = $1", elsewhere
    )
    local = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, contact_kind) "
            "VALUES ($1, $2, 'Someone else', 'third_party') RETURNING id",
            world.tenant,
            other_client,
        ),
    )
    ctx = AuthContext(
        tenant=TenantContext(world.tenant, "human", str(world.inviter.user_id)),
        user_id=world.inviter.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=None,
    )
    for contact in (local, stray.contact):
        with pytest.raises(InvitationInvalid):
            async with uow(ctx.tenant) as tx:
                await create_invitation(
                    tx,
                    ctx,
                    world.engagement,
                    "x.y@example.test",
                    "client_contributor",
                    kind="delegate",
                    contact_id=contact,
                )
