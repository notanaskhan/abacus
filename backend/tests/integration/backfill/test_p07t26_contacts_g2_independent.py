# ac-test-author: ayushkbhatia
"""P-07-T26: independent acceptance tests (ADR-078) for P-07-T24 (G2 v2) and P-07-T25 (contacts and
portal access live).

Written from the plan and the contracts, before P-07-T25 was built: SPEC-321 Story 6 (AC-26 to
AC-29); P-07 Story 2.1 (contacts and scoped portal access) and Story 5.2 (G2 v2);
`docs/contracts/contacts-access.md` §2 to §7; the matrix rows `contact.read`, `contact.manage`,
`client_access.grant`, `client_access.revoke` and `contact.unlock`; ADR-146, ADR-164; DEC-39,
DEC-226, DEC-275, DEC-277. The rows: "third party limited to delegated items (INV-4), expiry and
single use, revoke semantics and session closure, unlock rights, invitation email in the firm's
name without amounts, G2 v2 view-versus-assign semantics and the stricter firm setting".

HTTP through `create_app()` against the migrated Postgres with fake-identity tokens for the firm,
and the portal's own pre-session routes for the invitee; seeding as the superuser, a fresh firm
per test. The token is taken where the email takes it (`identity.api.issue_invitation_token`, the
call delivery makes) and the sign-in code where its email does (`issue_sign_in_code`).

Followed instead of the contract's wording: an expired or used link is refused with the same 404
as every other acceptance failure (DEC-275, later than the contract's 409 `invitation_expired` /
`invitation_used`), and nothing is granted. Spec gap: the plan names no key for the firm's
Invitation template; the email case imports a platform default `portal.invitation` (C16
variables `firm_name`, `recipient_first_name`, `app_link`) as test content.

G2 v2 (P-07-T24) is on main and its cases pass. The P-07-T25 cases are strict xfails citing
TASK-1174 until that row lands; its commit removes only the markers.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent, uow
from abacus.modules.communications.api import SUBSCRIPTIONS, configure_transport
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.engagements.api import (
    assign_work_item,
    create_work_item,
    g2_blocks,
    independence_cleared,
)
from abacus.modules.engagements.record import GateUnmet
from abacus.modules.identity.api import (
    RULES,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    issue_invitation_token,
    issue_sign_in_code,
    portal_scopes,
)
from abacus.modules.identity.authz import recording_checks
from abacus.modules.identity.portal_session import portal_context
from abacus.modules.portal.branding import activate_portal_host, add_portal_host

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
T25 = pytest.mark.xfail(
    strict=True,
    reason="P-07-T25 (TASK-1123) builds the contacts and portal-access routes; this suite is "
    "committed first, per ADR-078 (TASK-1174; builds on #393's invitations v2)",
)
INVITATION_DAYS = 14
TEMPLATE_KEY = "portal.invitation"


# ================================================================================================
# Seeding
# ================================================================================================


@dataclass(frozen=True)
class World:
    """Brightwater Hale's shape: Grace (firm admin) and Hannah (manager) on Northwind, three of
    Northwind's requests, and Harborline, the third party two of them are delegated to."""

    net: Net
    tenant: uuid.UUID
    host: str
    firm_name: str
    grace: Person
    hannah: Person
    site: Site
    items: tuple[uuid.UUID, uuid.UUID, uuid.UUID]
    harborline: uuid.UUID
    email: str

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def delegated(self) -> list[str]:
        return [str(self.items[0]), str(self.items[1])]


async def _flag(seed: Seeder, tenant: uuid.UUID, flag: str) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'P-07-T26')",
        tenant,
        flag,
    )


async def _host(tenant: uuid.UUID) -> str:
    host = f"t26-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return host


async def _contact(
    seed: Seeder, site: Site, name: str, *, kind: str = "third_party", org: str | None = None
) -> tuple[uuid.UUID, str]:
    email = f"{name.split()[0].lower()}.{uuid.uuid4().hex[:8]}@example.test"
    contact = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, email, organisation_name, "
            "contact_kind) VALUES ($1, $2, $3, $4, $5, $6) RETURNING id",
            site.tenant_id,
            site.client_id,
            name,
            email,
            org,
            kind,
        ),
    )
    return contact, email


async def _world(net: Net) -> World:
    seed = net.seed
    tenant = await seed.firm()
    firm_name = cast(str, await seed.value("SELECT name FROM firms WHERE tenant_id = $1", tenant))
    for flag in ("contacts.v2", "portal.sign_in_v2"):
        await _flag(seed, tenant, flag)
    host = await _host(tenant)
    grace = await seed.person(tenant, "firm_admin")
    hannah = await seed.person(tenant)
    site = await seed.site(tenant, grace.user_id, "Northwind")
    await seed.member(site, hannah, "manager")
    items = (
        site.item_id,
        await seed.item(site, "Payroll register"),
        await seed.item(site, "Benefit statements"),
    )
    harborline, email = await _contact(seed, site, "Harborline Benefits", org="Harborline")
    return World(net, tenant, host, firm_name, grace, hannah, site, items, harborline, email)


def _harborline_grants(world: World) -> list[Json]:
    """The O3 sheet prefilled with Harborline's two delegated requests (contract §8)."""
    return [
        {
            "role": "third_party",
            "scope_kind": "request_item",
            "scope_id": world.delegated[0],
            "request_item_ids": world.delegated,
        }
    ]


async def _invite(
    world: World,
    contact: uuid.UUID,
    grants: list[Json],
    *,
    who: Person | None = None,
    mfa: bool = True,
    key: str | None = None,
) -> httpx.Response:
    headers = world.net.headers(who or world.grace, mfa=mfa) | {
        "Idempotency-Key": key or uuid.uuid4().hex
    }
    return await world.net.http.post(
        f"/v1/contacts/{contact}/invitations",
        json={"grants": grants, "expires_in_days": INVITATION_DAYS},
        headers=headers,
    )


def _json(response: httpx.Response, status: int = 200) -> Json:
    assert response.status_code == status, response.text
    return cast(Json, response.json())


async def _token(world: World, invitation: str) -> str:
    """The link's token, issued as delivery issues it (only its hash is kept)."""
    issued = await issue_invitation_token(world.tenant, uuid.UUID(invitation))
    assert issued is not None
    return issued.token


async def _portal_session(world: World, email: str, token: str) -> str:
    """POR-01: start with the invitation token, the emailed code, verify: the access token."""
    http = world.net.http
    start = await http.post(
        "/v1/portal/auth/start",
        json={"email": email, "invitation_token": token},
        headers={"host": world.host},
    )
    assert start.status_code == 202, start.text
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = _json(
        await http.post(
            "/v1/portal/auth/verify",
            json={"challenge_id": challenge, "code": issued.code},
            headers={"host": world.host},
        )
    )
    return cast(str, verified["access_token"])


async def _accept(world: World, access: str, token: str) -> httpx.Response:
    return await world.net.http.post(
        "/v1/invitations/accept",
        json={"token": token},
        headers={"host": world.host, "authorization": f"Bearer {access}"},
    )


async def _preview(world: World, token: str) -> httpx.Response:
    return await world.net.http.post(
        "/v1/invitations/preview", json={"token": token}, headers={"host": world.host}
    )


async def _accepted(world: World) -> tuple[Json, str, uuid.UUID]:
    """Harborline invited and accepted: the invitation, the portal access token, the user."""
    invitation = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    token = await _token(world, cast(str, invitation["invitation_id"]))
    access = await _portal_session(world, world.email, token)
    accepted = await _accept(world, access, token)
    assert accepted.status_code == 200, accepted.text
    user = cast(
        uuid.UUID,
        await world.seed.value("SELECT user_id FROM contacts WHERE id = $1", world.harborline),
    )
    assert user is not None
    return invitation, access, user


def _client_ctx(world: World, user: uuid.UUID) -> AuthContext:
    return AuthContext(
        TenantContext(world.tenant, "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        None,
        client=True,
    )


async def _grants_of(world: World, contact: uuid.UUID) -> list[tuple[str, str, uuid.UUID, str]]:
    rows = await world.seed.rows(
        "SELECT role, scope_kind, scope_id, status FROM client_access_grants "
        "WHERE tenant_id = $1 AND contact_id = $2 ORDER BY scope_id",
        world.tenant,
        contact,
    )
    return [(r["role"], r["scope_kind"], r["scope_id"], r["status"]) for r in rows]


async def _audited(world: World, action: str) -> list[str]:
    rows = await world.seed.rows(
        "SELECT actor_kind FROM audit_events WHERE tenant_id = $1 AND action = $2",
        world.tenant,
        action,
    )
    return [str(r["actor_kind"]) for r in rows]


async def _outbox(world: World, event_type: str) -> list[Json]:
    rows = await world.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 ORDER BY id",
        world.tenant,
        event_type,
    )
    return [
        cast(Json, json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"])
        for r in rows
    ]


@pytest.fixture
async def world(net: Net) -> World:
    return await _world(net)


# ================================================================================================
# INV-4: a third party is limited to its delegated requests
# ================================================================================================


@T25
async def test_inv4_harborlines_invitation_grants_exactly_its_two_delegated_requests(
    world: World,
) -> None:
    sent = datetime.now(UTC)
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    assert body["contact_id"] == str(world.harborline)
    assert body["portal_status"] == "invited"
    assert body["mfa_policy"] in ("required_by_firm", "optional")
    expires = datetime.fromisoformat(cast(str, body["expires_at"]))
    assert abs(expires - sent - timedelta(days=INVITATION_DAYS)) < timedelta(minutes=5)
    # The token goes only in the email (AC-28): no key or value names it.
    assert not {k for k in body if "token" in k or "link" in k}
    grants = cast(list[Json], body["grants"])
    covered = {str(i) for g in grants for i in cast(list[str], g["request_item_ids"])} | {
        str(g["scope_id"]) for g in grants
    }
    assert covered == set(world.delegated)
    assert {(g["role"], g["status"]) for g in grants} == {("third_party", "pending")}
    stored = await _grants_of(world, world.harborline)
    assert sorted(s[2] for s in stored) == sorted(world.items[:2])
    assert {(s[0], s[1], s[3]) for s in stored} == {("third_party", "request_item", "pending")}
    invited = await _outbox(world, "contact.invited")
    assert len(invited) == 1 and invited[0]["contact_id"] == str(world.harborline)
    assert await _audited(world, "contact.invited") == ["human"]


@T25
async def test_inv4_after_accepting_harborline_reaches_those_two_requests_and_nothing_else(
    world: World,
) -> None:
    _, _, user = await _accepted(world)
    stored = await _grants_of(world, world.harborline)
    assert {(s[2], s[3]) for s in stored} == {
        (world.items[0], "active"),
        (world.items[1], "active"),
    }
    scopes = await portal_scopes(_client_ctx(world, user))
    assert scopes.shell == "limited"
    assert {(s.role, s.scope_kind, s.scope_id) for s in scopes.scopes} == {
        ("third_party", "request_item", world.items[0]),
        ("third_party", "request_item", world.items[1]),
    }
    other = await world.seed.rows(
        "SELECT 1 FROM client_access_grants WHERE tenant_id = $1 AND user_id = $2 "
        "AND scope_id NOT IN ($3, $4)",
        world.tenant,
        user,
        world.items[0],
        world.items[1],
    )
    assert other == []


@T25
async def test_ac28_a_grant_outside_the_contacts_client_is_422_scope_outside_client(
    world: World,
) -> None:
    elsewhere = await world.seed.site(world.tenant, world.grace.user_id, "Calloway")
    grants: list[Json] = [
        {
            "role": "third_party",
            "scope_kind": "request_item",
            "scope_id": str(elsewhere.item_id),
            "request_item_ids": [str(elsewhere.item_id)],
        }
    ]
    response = await _invite(world, world.harborline, grants)
    assert response.status_code == 422, response.text
    assert response.json()["detail"] == "scope_outside_client"
    assert await _grants_of(world, world.harborline) == []


# ================================================================================================
# 14 days, single use, resend
# ================================================================================================


@T25
async def test_ac28_an_expired_link_is_refused_and_grants_nothing(world: World) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    token = await _token(world, cast(str, body["invitation_id"]))
    access = await _portal_session(world, world.email, token)
    await world.seed.run(
        "UPDATE client_invitations SET expires_at = now() - interval '1 minute' WHERE id = $1",
        uuid.UUID(cast(str, body["invitation_id"])),
    )
    refused = await _accept(world, access, token)
    assert refused.status_code == 404  # DEC-275: the one answer for every failure
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"pending"}


@T25
async def test_ac28_a_used_link_is_refused_the_second_time(world: World) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    token = await _token(world, cast(str, body["invitation_id"]))
    access = await _portal_session(world, world.email, token)
    assert (await _accept(world, access, token)).status_code == 200
    again = await _accept(world, access, token)
    assert again.status_code == 404
    assert (await _preview(world, token)).status_code == 404


@T25
async def test_resend_issues_a_new_link_and_the_old_one_stops_working(world: World) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    invitation = cast(str, body["invitation_id"])
    old = await _token(world, invitation)
    assert (await _preview(world, old)).status_code == 200
    await world.seed.run(
        "UPDATE client_invitations SET expires_at = now() - interval '1 day' WHERE id = $1",
        uuid.UUID(invitation),
    )
    resent = _json(
        await world.net.call("POST", f"/v1/invitations/{invitation}/resend", world.grace)
    )
    assert resent["portal_status"] == "invited"
    expires = datetime.fromisoformat(cast(str, resent["expires_at"]))
    assert abs(expires - datetime.now(UTC) - timedelta(days=INVITATION_DAYS)) < timedelta(
        minutes=5
    )
    assert not {k for k in resent if "token" in k or "link" in k}
    assert (await _preview(world, old)).status_code == 404
    new = await _token(world, invitation)
    assert (await _preview(world, new)).status_code == 200
    assert await _audited(world, "invitation.resent") == ["human"]


@T25
async def test_resend_is_a_persons_with_the_grant_right_and_not_staffs(world: World) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    senior = await world.seed.person(world.tenant)
    await world.seed.member(world.site, senior, "senior")
    refused = await world.net.call(
        "POST", f"/v1/invitations/{body['invitation_id']}/resend", senior
    )
    assert refused.status_code in (403, 404)
    assert await _audited(world, "invitation.resent") == []


# ================================================================================================
# Revoke: grants revoked, sessions closed, requests kept
# ================================================================================================


@T25
async def test_revoke_ends_the_session_revokes_the_grants_and_keeps_the_requests(
    world: World,
) -> None:
    invitation, access, user = await _accepted(world)
    assert await portal_context(access, world.host) is not None
    revoked = _json(
        await world.net.call(
            "POST", f"/v1/invitations/{invitation['invitation_id']}/revoke", world.grace
        )
    )
    assert revoked["contact_id"] == str(world.harborline)
    assert set(cast(list[str], revoked["kept_request_item_ids"])) == set(world.delegated)
    assert len(cast(list[str], revoked["revoked_grant_ids"])) == 2
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"revoked"}
    # The requests stay with Northwind: not deleted, not moved, not reassigned.
    kept = await world.seed.rows(
        "SELECT engagement_id, deleted_at FROM request_items WHERE id = ANY($1::uuid[])",
        list(world.items[:2]),
    )
    assert [(k["engagement_id"], k["deleted_at"]) for k in kept] == [
        (world.site.engagement_id, None)
    ] * 2
    # The session reaches nothing any more, and `access.changed` tells every other holder.
    assert await portal_context(access, world.host) is None
    changed = await _outbox(world, "access.changed")
    assert any(e.get("user_id") == str(user) for e in changed)
    assert await _audited(world, "invitation.revoked") == ["human"]


@T25
async def test_revoke_before_acceptance_kills_the_link_and_the_pending_grants(
    world: World,
) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    token = await _token(world, cast(str, body["invitation_id"]))
    revoked = _json(
        await world.net.call(
            "POST", f"/v1/invitations/{body['invitation_id']}/revoke", world.grace
        )
    )
    assert set(cast(list[str], revoked["kept_request_item_ids"])) == set(world.delegated)
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"revoked"}
    assert (await _preview(world, token)).status_code == 404


@T25
async def test_revoke_needs_fresh_mfa(world: World) -> None:
    body = _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    refused = await world.net.call(
        "POST", f"/v1/invitations/{body['invitation_id']}/revoke", world.grace, mfa=False
    )
    assert refused.status_code == 403
    assert {s[3] for s in await _grants_of(world, world.harborline)} == {"pending"}


# ================================================================================================
# Change scope
# ================================================================================================


@T25
async def test_change_scope_replaces_the_grant_set_and_refuses_a_stale_version(
    world: World,
) -> None:
    await _accepted(world)
    drawer = _json(await world.net.call("GET", f"/v1/contacts/{world.harborline}", world.grace))
    version = cast(int, drawer["version"])
    target = [str(world.items[0]), str(world.items[2])]
    changed = _json(
        await world.net.call(
            "PUT",
            f"/v1/contacts/{world.harborline}/access",
            world.grace,
            body={
                "seen_version": version,
                "grants": [
                    {
                        "role": "third_party",
                        "scope_kind": "request_item",
                        "scope_id": target[0],
                        "request_item_ids": target,
                    }
                ],
            },
        )
    )
    live = {
        (g["scope_id"], g["status"])
        for g in cast(list[Json], changed["grants"])
        if g["status"] != "revoked"
    }
    assert live == {(target[0], "active"), (target[1], "active")}
    stored = {(s[2], s[3]) for s in await _grants_of(world, world.harborline)}
    assert (world.items[1], "revoked") in stored
    assert (world.items[2], "active") in stored
    assert await _audited(world, "contact.access_changed") == ["human"]
    stale = await world.net.call(
        "PUT",
        f"/v1/contacts/{world.harborline}/access",
        world.grace,
        body={"seen_version": version, "grants": []},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"] == "stale_version"


# ================================================================================================
# Unlock
# ================================================================================================


async def _lock(world: World, email: str) -> None:
    """P-08's lockout: three wrong codes on one challenge."""
    http = world.net.http
    start = await http.post(
        "/v1/portal/auth/start", json={"email": email}, headers={"host": world.host}
    )
    challenge = start.json()["challenge_id"]
    last = None
    for _ in range(3):
        last = await http.post(
            "/v1/portal/auth/verify",
            json={"challenge_id": challenge, "code": "000000"},
            headers={"host": world.host},
        )
    assert last is not None
    assert last.status_code == 423, last.text


@T25
async def test_unlock_clears_the_portal_lock_and_is_audited(world: World) -> None:
    await _accepted(world)
    await _lock(world, world.email)
    listed = _json(
        await world.net.call("GET", f"/v1/clients/{world.site.client_id}/contacts", world.grace)
    )
    assert cast(Json, listed["summary"])["locked"] == 1
    unlocked = _json(
        await world.net.call("POST", f"/v1/contacts/{world.harborline}/unlock", world.grace)
    )
    assert unlocked["contact_id"] == str(world.harborline)
    assert unlocked["portal_status"] != "locked"
    assert await _audited(world, "contact.unlocked") == ["human"]
    # The person can sign in again at once.
    start = await world.net.http.post(
        "/v1/portal/auth/start", json={"email": world.email}, headers={"host": world.host}
    )
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = await world.net.http.post(
        "/v1/portal/auth/verify",
        json={"challenge_id": challenge, "code": issued.code},
        headers={"host": world.host},
    )
    assert verified.status_code == 200, verified.text


@T25
async def test_unlock_is_refused_to_a_senior_and_allowed_to_it_security(world: World) -> None:
    await _accepted(world)
    await _lock(world, world.email)
    senior = await world.seed.person(world.tenant)
    await world.seed.member(world.site, senior, "senior")
    refused = await world.net.call("POST", f"/v1/contacts/{world.harborline}/unlock", senior)
    assert refused.status_code in (403, 404)
    assert await _audited(world, "contact.unlocked") == []
    security = await world.seed.person(world.tenant, "security_admin")
    allowed = await world.net.call("POST", f"/v1/contacts/{world.harborline}/unlock", security)
    assert allowed.status_code == 200, allowed.text


async def test_unlock_rights_are_the_firms_client_side_leads_never_agent_or_system() -> None:
    granted = {r for r, d in RULES["contact.unlock"].decisions.items() if d == "allow"}
    assert granted == {
        "firm_admin",
        "security_admin",
        "engagement_partner",
        "manager",
        "client_service",
    }
    for action in ("contact.unlock", "client_access.grant", "client_access.revoke"):
        decisions = RULES[action].decisions
        assert decisions.get("agent", "deny") == "deny", action
        assert decisions.get("system", "deny") == "deny", action
        assert not {"client_admin", "client_contributor"} & {
            r for r, d in decisions.items() if d == "allow"
        }, action
    assert RULES["client_access.grant"].mfa_recent and RULES["client_access.revoke"].mfa_recent


# ================================================================================================
# The invitation email: the firm's name, one call to action, no amounts
# ================================================================================================


class _Outbox:
    def __init__(self) -> None:
        self.sent: list[Json] = []

    def send(self, **message: object) -> None:
        self.sent.append(dict(message))


@T25
async def test_the_invitation_email_is_in_the_firms_name_with_one_link_and_no_amounts(
    world: World,
) -> None:
    await import_platform_version(
        "p07t26",
        TEMPLATE_KEY,
        "en-US",
        "{{firm_name}} invites you to share documents",
        "Hello {{recipient_first_name}},\n\n{{firm_name}} has invited you to its client portal."
        "\n\nOpen your invitation: {{app_link}}\n",
        ["firm_name", "recipient_first_name", "app_link"],
    )
    box = _Outbox()
    configure_transport(box)
    try:
        _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
        for event_type in ("client_invitation.issued", "contact.invited"):
            handler = SUBSCRIPTIONS.get(event_type)
            if handler is None:
                continue
            for payload in await _outbox(world, event_type):
                await handler(OutboxEvent(uuid.uuid4(), world.tenant, event_type, payload))
    finally:
        configure_transport(None)
    assert len(box.sent) == 1
    mail = box.sent[0]
    text = f"{mail['subject']}\n{mail['body']}"
    assert mail["sender_name"] == world.firm_name
    assert world.firm_name in text
    assert "Accrued" not in text and "abacus" not in text.lower()
    assert not re.search(r"[$€£]\s?\d|\d[\d,]*\.\d{2}\b", text)  # no amounts
    assert len(re.findall(r"https?://", text)) == 1  # one call to action


# ================================================================================================
# G1 for full-client grants, walls, the agent
# ================================================================================================


@T25
async def test_a_full_client_grant_before_any_accepted_engagement_is_409_gate_unmet_g1(
    net: Net,
) -> None:
    world = await _world(net)
    prospect = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO clients (tenant_id, name) VALUES ($1, $2) RETURNING id",
            world.tenant,
            f"Thornbury {uuid.uuid4().hex[:6]}",
        ),
    )
    entity = await world.seed.value(
        "INSERT INTO client_entities (tenant_id, client_id, name) VALUES ($1, $2, 'Thornbury') "
        "RETURNING id",
        world.tenant,
        prospect,
    )
    await world.seed.run(
        "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
        "fiscal_period_start, fiscal_period_end, created_by, status) "
        "VALUES ($1, $2, $3, 'Thornbury PY2025', '2025-01-01', '2025-12-31', $4, 'prospect')",
        world.tenant,
        prospect,
        entity,
        world.grace.user_id,
    )
    owner = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, email, contact_kind) "
            "VALUES ($1, $2, 'Thornbury owner', $3, 'client_person') RETURNING id",
            world.tenant,
            prospect,
            f"owner.{uuid.uuid4().hex[:8]}@example.test",
        ),
    )
    refused = await _invite(
        world,
        owner,
        [{"role": "owner", "scope_kind": "client", "scope_id": str(prospect)}],
    )
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "gate_unmet"
    assert refused.json()["facts"]["gate"] == "G1"
    assert await _grants_of(world, owner) == []


@pytest.mark.xfail(
    strict=True,
    reason="OQ-11's intake grants need an intake scope resolver, which arrives with CLI-06 "
    "(P-07-T42); held as TASK-1174 (#393 built invitations v2 without one)",
)
async def test_an_intake_grant_is_the_exception_to_g1(world: World) -> None:
    response = await _invite(
        world,
        world.harborline,
        [{"role": "prospect", "scope_kind": "intake", "scope_id": str(world.site.client_id)}],
    )
    assert response.status_code == 201, response.text


@T25
async def test_a_walled_client_answers_404_on_the_contacts_routes(world: World) -> None:
    await world.net.wall(world.grace, world.hannah, world.site)
    listed = await world.net.call(
        "GET", f"/v1/clients/{world.site.client_id}/contacts", world.hannah
    )
    assert listed.status_code == 404
    drawer = await world.net.call("GET", f"/v1/contacts/{world.harborline}", world.hannah)
    assert drawer.status_code == 404
    invited = await _invite(world, world.harborline, _harborline_grants(world), who=world.hannah)
    assert invited.status_code == 404
    assert await _grants_of(world, world.harborline) == []


@T25
async def test_ac27_the_list_counts_portal_states_and_foots_the_delegated_requests(
    world: World,
) -> None:
    await _contact(world.seed, world.site, "Sam Ortiz")  # not invited
    _json(await _invite(world, world.harborline, _harborline_grants(world)), 201)
    page = _json(
        await world.net.call("GET", f"/v1/clients/{world.site.client_id}/contacts", world.grace)
    )
    rows = cast(list[Json], page["items"])
    assert page["total"] == len(rows) == 2
    summary = cast(dict[str, int], page["summary"])
    assert summary["invited"] == 1 and summary["not_invited"] == 1
    assert sum(summary.values()) == len(rows)
    delegated = cast(Json, page["delegated"])
    per_row = [cast(int, r["delegated_request_count"]) for r in rows]
    assert delegated["parts"] == [n for n in per_row if n]
    assert delegated["total"] == sum(per_row) == 2
    harborline = next(r for r in rows if r["id"] == str(world.harborline))
    assert harborline["portal_status"] == "invited" and harborline["party_kind"] == "person"


# ================================================================================================
# G2 v2 (P-07-T24): view versus assign, attest only, the stricter firm setting
# ================================================================================================


@dataclass(frozen=True)
class Team:
    world: World
    engagement: uuid.UUID
    partner: Person
    ana: Person
    work_item: uuid.UUID

    def ctx(self, who: Person, *, firm_role: Literal["firm_admin"] | None = None) -> AuthContext:
        return AuthContext(
            TenantContext(who.tenant_id, "human", str(who.user_id)),
            who.user_id,
            uuid.uuid4(),
            firm_role,
            datetime.now(UTC),
        )

    @property
    def on(self) -> Resource:
        return Resource.engagement(self.world.tenant, self.engagement, archived=False)


async def _team(world: World, *, attest: bool) -> Team:
    """Northwind PY2025 (attest: an active EBP audit) or a CAS close, with its partner (cleared)
    and Ana Cruz on staff, asked to confirm and not yet confirmed."""
    seed = world.seed
    site = await seed.site(world.tenant, world.grace.user_id, "G2")
    if attest:
        await seed.attest(world.tenant, site.engagement_id)
    else:
        await seed.run(
            "UPDATE engagements SET type = 'cas_monthly_close' WHERE id = $1", site.engagement_id
        )
    partner = await seed.person(world.tenant)
    await seed.member(site, partner, "engagement_partner")
    ana = await seed.person(world.tenant)
    await seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        world.tenant,
        site.engagement_id,
        ana.user_id,
    )
    await seed.run(
        "INSERT INTO independence_confirmations (tenant_id, engagement_id, user_id, status) "
        "VALUES ($1, $2, $3, 'requested') ON CONFLICT DO NOTHING",
        world.tenant,
        site.engagement_id,
        ana.user_id,
    )
    found = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 LIMIT 1", site.engagement_id
    )
    team = Team(world, site.engagement_id, partner, ana, uuid.uuid4())
    if found is None:
        found = await create_work_item(
            team.ctx(partner), site.engagement_id, "advisory_project", name="G2 project"
        )
    return Team(world, site.engagement_id, partner, ana, cast(uuid.UUID, found))


async def _confirm(team: Team) -> None:
    await team.world.seed.run(
        "UPDATE independence_confirmations SET status = 'confirmed', answered_at = now() "
        "WHERE engagement_id = $1 AND user_id = $2",
        team.engagement,
        team.ana.user_id,
    )


async def _layer(ctx: AuthContext, action: str, resource: Resource) -> str | None:
    with recording_checks():
        try:
            await authorise(ctx, action, resource)
        except Forbidden as refused:
            return refused.layer
    return None


async def _assignments(team: Team) -> int:
    return int(
        str(
            await team.world.seed.value(
                "SELECT count(*) FROM work_item_assignments WHERE work_item_id = $1 "
                "AND user_id = $2",
                team.work_item,
                team.ana.user_id,
            )
        )
    )


async def test_ac5_2_ana_opens_the_attest_engagement_but_is_not_assigned_until_she_confirms(
    world: World,
) -> None:
    team = await _team(world, attest=True)
    ana = team.ctx(team.ana)
    opened = await world.net.call("GET", f"/v1/engagements/{team.engagement}", team.ana)
    assert opened.status_code == 200, opened.text  # DEC-39: G2 no longer hides the engagement
    assert await _layer(ana, "evidence.read", team.on) is None
    assert not await independence_cleared(ana.tenant, team.engagement, team.ana.user_id)
    assert await g2_blocks(ana.tenant, team.engagement, team.ana.user_id)
    assert await _layer(ana, "sign_off.prepare", team.on) == "independence"
    with pytest.raises(GateUnmet) as refused:
        await assign_work_item(
            team.ctx(team.partner), team.work_item, team.ana.user_id, "preparer"
        )
    assert refused.value.facts == {"gate": "G2", "user_id": str(team.ana.user_id)}
    assert await _assignments(team) == 0
    await _confirm(team)
    assert not await g2_blocks(ana.tenant, team.engagement, team.ana.user_id)
    await assign_work_item(team.ctx(team.partner), team.work_item, team.ana.user_id, "preparer")
    assert await _assignments(team) == 1
    assert await _layer(team.ctx(team.ana), "sign_off.prepare", team.on) is None


async def test_ac5_2_a_non_attest_engagement_is_never_gated_even_with_g2_blocks_view(
    world: World,
) -> None:
    team = await _team(world, attest=False)
    await world.seed.blocks_view(world.tenant, world.grace.user_id)
    ana = team.ctx(team.ana)
    assert not await g2_blocks(ana.tenant, team.engagement, team.ana.user_id)
    assert await _layer(ana, "evidence.read", team.on) is None
    assert await _layer(ana, "sign_off.prepare", team.on) is None
    await assign_work_item(team.ctx(team.partner), team.work_item, team.ana.user_id, "preparer")
    assert await _assignments(team) == 1


async def test_ac5_2_g2_blocks_view_takes_content_reads_away_from_pending_members_only(
    world: World,
) -> None:
    team = await _team(world, attest=True)
    await world.seed.blocks_view(world.tenant, world.grace.user_id)
    assert await _layer(team.ctx(team.ana), "evidence.read", team.on) == "independence"
    # Stricter only: the cleared partner and the firm admin read as before.
    assert await _layer(team.ctx(team.partner), "evidence.read", team.on) is None
    await _confirm(team)
    assert await _layer(team.ctx(team.ana), "evidence.read", team.on) is None


async def test_dec39_a_client_facing_grant_needs_the_acting_member_cleared_on_an_attest_client(
    world: World,
) -> None:
    team = await _team(world, attest=True)
    manager = await world.seed.person(world.tenant)
    await world.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'manager')",
        world.tenant,
        team.engagement,
        manager.user_id,
    )
    assert await _layer(team.ctx(manager), "client_access.grant", team.on) == "independence"
    # A firm role isn't bound by G2 (ADR-164): Grace grants as before.
    assert (
        await _layer(team.ctx(world.grace, firm_role="firm_admin"), "client_access.grant", team.on)
        is None
    )


@T25
async def test_dec39_an_uncleared_manager_cannot_invite_a_contact_on_an_attest_engagement(
    world: World,
) -> None:
    await world.seed.attest(world.tenant, world.site.engagement_id)
    await world.seed.run(
        "UPDATE independence_confirmations SET status = 'requested', answered_at = NULL "
        "WHERE engagement_id = $1 AND user_id = $2",
        world.site.engagement_id,
        world.hannah.user_id,
    )
    refused = await _invite(world, world.harborline, _harborline_grants(world), who=world.hannah)
    assert refused.status_code == 403, refused.text
    assert await _grants_of(world, world.harborline) == []
    allowed = await _invite(world, world.harborline, _harborline_grants(world))
    assert allowed.status_code == 201, allowed.text
