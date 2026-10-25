# ac-test-author: ayushkbhatia
"""P-08-T24: independent acceptance tests (ADR-078) for P-08-T17 (portal MFA), T18 (invitations
v2) and T21 (secure links and recovery).

Written from SPEC-320 AC-10 to AC-14 and AC-18 to AC-20, the epic's Stories 3.1 to 3.4, 4.1,
5.1 and 7.1 to 7.3, `docs/contracts/portal-identity.md` §2, §5, §6 and §7, the permission matrix
rows `contact.unlock` and `contact.mfa_reset`, `docs/architecture/human-only-actions.yaml`, and
the decisions that changed them since (DEC-250, DEC-275, DEC-277, DEC-303, DEC-329): the MFA floor
for every client grant role and every designation, allow and deny; fail closed; the firm's
stricter-only extension; backup codes used once; trusted devices of at most 30 days (fewer if the
firm says) that a reset revokes; invitations single use and 14 days, with one 404 for every
failure of the preview; grants attributed to the inviter (INV-5); renewal only to the original
address; unlock and reset denied to the agent (INV-1); the sign-in pause within 10 seconds.

HTTP through `create_app()` on the migrated Postgres. Firm people use fake-identity tokens; the
client uses the portal's own pre-session routes, with the emailed code and the invitation token
taken where their emails take them (`issue_sign_in_code`, `issue_invitation_token`) and TOTP codes
computed from the manual key the setup returns (`totp_at`). Security windows run on real time, so
"later" is staged by moving stored timestamps back.

Followed instead of the plan's wording: a reset ends this firm's trusted devices and sessions but
keeps the person's factor and backup codes (SPEC-320 AC-19 as amended by DEC-329); the unlock is
audited as `contact.unlocked` (DEC-303); the reset as `portal_mfa.reset` (one dot, DEC-250).
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from http.cookies import SimpleCookie
from typing import cast

import asyncpg
import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent, uow
from abacus.modules.communications.api import (
    SUBSCRIPTIONS,
    configure_transport,
    issue_secure_link,
)
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.identity.api import (
    RULES,
    TOTP_STEP_SECONDS,
    agent_context_for_run,
    current_context,
    issue_invitation_token,
    issue_sign_in_code,
    mfa_required,
    register_mfa_requirement,
    totp_at,
)
from abacus.modules.identity.authz.matrix import RULES as MATRIX
from abacus.modules.identity.portal_idp import InMemoryPortalIdp, configure_portal_idp
from abacus.modules.portal.api import activate_portal_host, add_portal_host

from .support import Net, Person, Seeder, Site

Json = dict[str, object]
SESSION_COOKIE = "__Host-abacus-portal"
FLAGS = ("contacts.v2", "portal.sign_in_v2", "portal.home_v2")
# P-08 Story 3.2 / SPEC-320 AC-10 / DEC-63: the floor's grant role and designations.
FLOOR_DESIGNATIONS = ("approver_of_record", "signing_officer", "ske_designee")
OTHER_DESIGNATIONS = ("plan_administrator", "tcwg_member", "primary_contact")
# ADR-146: the twelve client grant roles, each on a scope kind it can hold.
ROLE_SCOPES: dict[str, str] = {
    "owner": "client_entity",
    "contributor": "engagement",
    "plan_administrator": "client_entity",
    "trustee": "client",
    "taxpayer": "client",
    "spouse": "client",
    "delegate": "request_item",
    "third_party": "request_item",
    "k1_recipient": "k1_package",
    "tcwg": "governance_room",
    "prospect": "intake",
    "component_auditor": "component",
}
FLOOR_ROLES = {"owner"}


@pytest.fixture(autouse=True)
def portal_idp() -> Iterator[None]:
    configure_portal_idp(InMemoryPortalIdp())
    yield
    configure_portal_idp(None)


# ================================================================================================
# Seeding and the sign-in steps
# ================================================================================================


@dataclass(frozen=True)
class World:
    net: Net
    tenant: uuid.UUID
    host: str
    grace: Person
    site: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    @property
    def http(self) -> httpx.AsyncClient:
        return self.net.http

    def scope_id(self, kind: str) -> uuid.UUID:
        return {
            "client": self.site.client_id,
            "client_entity": self.site.entity_id,
            "engagement": self.site.engagement_id,
            "request_item": self.site.item_id,
        }.get(kind) or uuid.uuid4()


async def _host(tenant: uuid.UUID) -> str:
    host = f"t24-{uuid.uuid4().hex[:8]}.portal-example.test"
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        await add_portal_host(tx, tenant, host, "default")
        await activate_portal_host(tx, tenant, host)
    return host


@pytest.fixture
async def world(net: Net) -> World:
    seed = net.seed
    tenant = await seed.firm()
    for flag in FLAGS:
        await seed.run(
            "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
            "VALUES ($1, $2, 'true', 'test-seed', 'P-08-T24')",
            tenant,
            flag,
        )
    grace = await seed.person(tenant, "firm_admin")
    site = await seed.site(tenant, grace.user_id, "Copperleaf")
    return World(net, tenant, await _host(tenant), grace, site)


async def _client(
    world: World, role: str | None = "contributor", scope_kind: str = "engagement"
) -> tuple[Person, str]:
    """A client person of the firm; with `role`, an active grant on a scope of that kind."""
    who = await world.seed.person(world.tenant)
    await world.seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        who.user_id,
    )
    if role is not None:
        await _grant(world, who, role, scope_kind)
    email = cast(str, await world.seed.value("SELECT email FROM users WHERE id = $1", who.user_id))
    return who, email


async def _grant(world: World, who: Person, role: str, scope_kind: str) -> None:
    await world.seed.run(
        "INSERT INTO client_access_grants (tenant_id, user_id, role, scope_kind, scope_id, "
        "granted_by) VALUES ($1, $2, $3, $4, $5, $6)",
        world.tenant,
        who.user_id,
        role,
        scope_kind,
        world.scope_id(scope_kind),
        world.grace.user_id,
    )


async def _contact_of(world: World, who: Person, email: str) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, email, contact_kind, "
            "user_id, portal_state) VALUES ($1, $2, 'Client person', $3, 'client_person', $4, "
            "'active') RETURNING id",
            world.tenant,
            world.site.client_id,
            email,
            who.user_id,
        ),
    )


def _cookies(response: httpx.Response) -> dict[str, str]:
    jar = SimpleCookie()
    for header in response.headers.get_list("set-cookie"):
        jar.load(header)
    return {name: morsel.value for name, morsel in jar.items()}


async def _verify(world: World, email: str, *, device: str | None = None) -> httpx.Response:
    http = world.http
    http.cookies.clear()
    start = await http.post(
        "/v1/portal/auth/start", json={"email": email}, headers={"host": world.host}
    )
    assert start.status_code == 202, start.text
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    if device is not None:
        http.cookies.set(DEVICE_COOKIE, device)
    try:
        return await http.post(
            "/v1/portal/auth/verify",
            json={"challenge_id": challenge, "code": issued.code},
            headers={"host": world.host},
        )
    finally:
        http.cookies.clear()


async def _state(world: World, email: str, *, device: str | None = None) -> Json:
    response = await _verify(world, email, device=device)
    assert response.status_code == 200, response.text
    return cast(Json, response.json())


async def _post(world: World, path: str, body: Json) -> httpx.Response:
    world.http.cookies.clear()
    response = await world.http.post(path, json=body, headers={"host": world.host})
    world.http.cookies.clear()
    return response


@dataclass(frozen=True)
class Enrolled:
    secret: str
    backup_codes: list[str]
    access_token: str


async def _enrol(world: World, email: str) -> Enrolled:
    """First sign-in under the floor: DF-17's setup, a first TOTP, the backup codes once."""
    state = await _state(world, email)
    assert state["state"] == "mfa_setup_required", state
    token = cast(str, state["mfa_token"])
    setup = await _post(world, "/v1/portal/auth/mfa/setup", {"mfa_token": token})
    assert setup.status_code == 200, setup.text
    secret = cast(str, setup.json()["manual_key"])
    assert setup.json()["otpauth_uri"].startswith("otpauth://totp/")
    done = await _post(
        world,
        "/v1/portal/auth/mfa/setup/verify",
        {"mfa_token": token, "totp": totp_at(secret, time.time())},
    )
    assert done.status_code == 200, done.text
    session = done.json()["session"]
    assert session["state"] == "signed_in", session
    return Enrolled(secret, list(done.json()["backup_codes"]), cast(str, session["access_token"]))


def _next_totp(secret: str, steps: int = 1) -> str:
    return totp_at(secret, time.time() + steps * TOTP_STEP_SECONDS)


async def _audited(world: World, action: str) -> list[asyncpg.Record]:
    return await world.seed.rows(
        "SELECT actor_kind, actor_id, on_behalf_of_user_id, target_id FROM audit_events "
        "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
        world.tenant,
        action,
    )


# ================================================================================================
# AC-10: the floor, for every grant role and every designation (allow and deny)
# ================================================================================================


@pytest.mark.parametrize("role", sorted(ROLE_SCOPES))
async def test_ac10_the_floor_asks_a_second_step_of_an_owner_grant_only(
    world: World, role: str
) -> None:
    _, email = await _client(world, role, ROLE_SCOPES[role])
    state = await _state(world, email)
    if role in FLOOR_ROLES:  # deny: no session without the second step
        assert state["state"] == "mfa_setup_required", state
        assert state.get("access_token") is None and state.get("mfa_token")
    else:  # allow: the code alone signs in (Claire Feld before the TRI predicate, Story 3.2)
        assert state["state"] == "signed_in", state
        assert state.get("access_token")


@pytest.mark.parametrize("designation", [*FLOOR_DESIGNATIONS, *OTHER_DESIGNATIONS])
async def test_ac10_the_floor_asks_a_second_step_of_the_three_designations(
    world: World, designation: str
) -> None:
    who, email = await _client(world, "contributor", "engagement")
    contact = await _contact_of(world, who, email)
    await world.seed.run(
        "INSERT INTO engagement_contacts (tenant_id, engagement_id, contact_id, designation, "
        "designated_by) VALUES ($1, $2, $3, $4, $5)",
        world.tenant,
        world.site.engagement_id,
        contact,
        designation,
        world.grace.user_id,
    )
    state = await _state(world, email)
    if designation in FLOOR_DESIGNATIONS:
        assert state["state"] == "mfa_setup_required", state
        assert state.get("access_token") is None
    else:
        assert state["state"] == "signed_in", state


async def test_ac10_an_owner_passes_with_the_second_step_and_is_refused_a_wrong_one(
    world: World,
) -> None:
    _, email = await _client(world, "owner", "client_entity")
    enrolled = await _enrol(world, email)  # allow: setup and a first code give a session
    assert enrolled.access_token
    state = await _state(world, email)
    assert state["state"] == "mfa_required" and state.get("access_token") is None
    token = cast(str, state["mfa_token"])
    wrong = await _post(world, "/v1/portal/auth/mfa", {"mfa_token": token, "totp": "000000"})
    assert wrong.status_code == 401, wrong.text
    assert wrong.json()["detail"] == "mfa_mismatch"
    assert SESSION_COOKIE not in _cookies(wrong) and "access_token" not in wrong.text
    right = await _post(
        world, "/v1/portal/auth/mfa", {"mfa_token": token, "totp": _next_totp(enrolled.secret)}
    )
    assert right.status_code == 200, right.text
    assert right.json()["state"] == "signed_in" and right.json()["access_token"]


async def test_ac11_three_wrong_second_step_codes_lock_for_15_minutes(world: World) -> None:
    _, email = await _client(world, "owner", "client_entity")
    enrolled = await _enrol(world, email)
    token = cast(str, (await _state(world, email))["mfa_token"])
    answers = [
        await _post(world, "/v1/portal/auth/mfa", {"mfa_token": token, "totp": "000000"})
        for _ in range(3)
    ]
    assert [a.status_code for a in answers[:2]] == [401, 401]
    assert [a.json()["facts"]["tries_left"] for a in answers[:2]] == [2, 1]
    locked = answers[2]
    assert locked.status_code == 423 and locked.json()["detail"] == "mfa_locked"
    until = datetime.fromisoformat(locked.json()["facts"]["locked_until"].replace("Z", "+00:00"))
    assert timedelta(minutes=14) < until - datetime.now(UTC) <= timedelta(minutes=15, seconds=5)
    # The right code during the lock is refused too.
    again = await _post(
        world, "/v1/portal/auth/mfa", {"mfa_token": token, "totp": _next_totp(enrolled.secret)}
    )
    assert again.status_code in (410, 423) and "access_token" not in again.text


# --- fail closed --------------------------------------------------------------------------------

_RAISING: set[uuid.UUID] = set()
_STALLING: set[uuid.UUID] = set()


async def _p08t24_probe(tenant: TenantContext, user_id: uuid.UUID) -> bool:
    """A predicate another epic might register (T-01's TRI, N-02's signer) that breaks: it raises
    for the people in `_RAISING` and never answers for those in `_STALLING`; for everyone else it
    says "not required", so it changes nothing for any other test."""
    if user_id in _RAISING:
        raise RuntimeError("predicate broke")
    if user_id in _STALLING:
        await asyncio.sleep(3600)
    return False


register_mfa_requirement("p08t24_probe", _p08t24_probe)


async def test_ac10_a_predicate_that_raises_requires_the_second_step(world: World) -> None:
    who, email = await _client(world, "contributor", "engagement")
    assert await mfa_required(world.tenant, who.user_id) is False
    _RAISING.add(who.user_id)
    try:
        assert await mfa_required(world.tenant, who.user_id) is True
        state = await _state(world, email)
        assert state["state"] == "mfa_setup_required" and state.get("access_token") is None
    finally:
        _RAISING.discard(who.user_id)


async def test_ac10_a_predicate_that_times_out_requires_the_second_step(world: World) -> None:
    """SPEC-320 AC-10 and §12: a predicate that does not answer counts as required. The budget is
    the sign-in's (p95 400 ms, §16); the test allows 10 seconds before calling it a hang."""
    who, _ = await _client(world, "contributor", "engagement")
    _STALLING.add(who.user_id)
    try:
        required = await asyncio.wait_for(mfa_required(world.tenant, who.user_id), timeout=10)
    finally:
        _STALLING.discard(who.user_id)
    assert required is True


# --- the firm's stricter-only extension ---------------------------------------------------------


async def _policy(world: World, *, all_users: bool, days: int = 30) -> None:
    await world.seed.run(
        "INSERT INTO portal_security_policies (tenant_id, mfa_for_all_client_users, "
        "trusted_device_days, updated_by) VALUES ($1, $2, $3, $4) "
        "ON CONFLICT (tenant_id) DO UPDATE SET mfa_for_all_client_users = $2, "
        "trusted_device_days = $3, version = portal_security_policies.version + 1",
        world.tenant,
        all_users,
        days,
        world.grace.user_id,
    )


async def test_ac10_the_firm_may_widen_the_floor_to_every_client_user(world: World) -> None:
    taxpayer, email = await _client(world, "taxpayer", "client")
    assert (await _state(world, email))["state"] == "signed_in"
    await _policy(world, all_users=True)
    assert await mfa_required(world.tenant, taxpayer.user_id) is True
    state = await _state(world, email)
    assert state["state"] == "mfa_setup_required" and state.get("access_token") is None


async def test_ac10_no_setting_narrows_the_floor(world: World) -> None:
    owner, email = await _client(world, "owner", "client_entity")
    await _policy(world, all_users=False, days=0)
    assert await mfa_required(world.tenant, owner.user_id) is True
    assert (await _state(world, email))["state"] == "mfa_setup_required"
    # A trusted device can never last longer than 30 days, whatever the firm stores.
    with pytest.raises(Exception, match="check"):
        await _policy(world, all_users=False, days=31)


# ================================================================================================
# AC-11: setup, backup codes, trusted devices
# ================================================================================================


async def test_ac11_setup_returns_eight_backup_codes_once(world: World) -> None:
    _, email = await _client(world, "owner", "client_entity")
    state = await _state(world, email)
    token = cast(str, state["mfa_token"])
    setup = await _post(world, "/v1/portal/auth/mfa/setup", {"mfa_token": token})
    assert setup.status_code == 200
    assert set(setup.json()) == {"otpauth_uri", "manual_key"}
    # Setup asked twice on one token: 410 (contract §6).
    twice = await _post(world, "/v1/portal/auth/mfa/setup", {"mfa_token": token})
    assert twice.status_code == 410 and twice.json()["detail"] == "mfa_expired"
    done = await _post(
        world,
        "/v1/portal/auth/mfa/setup/verify",
        {"mfa_token": token, "totp": totp_at(setup.json()["manual_key"], time.time())},
    )
    codes = cast(list[str], done.json()["backup_codes"])
    assert len(codes) == 8 and len(set(codes)) == 8
    # Shown once: the verify can't be replayed to see them again.
    replay = await _post(
        world,
        "/v1/portal/auth/mfa/setup/verify",
        {"mfa_token": token, "totp": _next_totp(setup.json()["manual_key"])},
    )
    assert replay.status_code == 410 and "backup_codes" not in replay.text


async def test_ac11_a_backup_code_verifies_once(world: World) -> None:
    owner, email = await _client(world, "owner", "client_entity")
    enrolled = await _enrol(world, email)
    code = enrolled.backup_codes[0]
    first = cast(str, (await _state(world, email))["mfa_token"])
    used = await _post(world, "/v1/portal/auth/mfa", {"mfa_token": first, "backup_code": code})
    assert used.status_code == 200, used.text
    assert used.json()["state"] == "signed_in"
    second = cast(str, (await _state(world, email))["mfa_token"])
    reused = await _post(world, "/v1/portal/auth/mfa", {"mfa_token": second, "backup_code": code})
    assert reused.status_code == 401 and reused.json()["detail"] == "mfa_mismatch"
    another = await _post(
        world,
        "/v1/portal/auth/mfa",
        {"mfa_token": second, "backup_code": enrolled.backup_codes[1]},
    )
    assert another.status_code == 200, another.text
    assert [r["actor_id"] for r in await _audited(world, "portal_backup_code.used")] == [
        str(owner.user_id)
    ] * 2


async def _trusted(world: World, email: str, enrolled: Enrolled) -> str:
    token = cast(str, (await _state(world, email))["mfa_token"])
    trusted = await _post(
        world,
        "/v1/portal/auth/mfa",
        {"mfa_token": token, "totp": _next_totp(enrolled.secret), "trust_device": True},
    )
    assert trusted.status_code == 200, trusted.text
    device = _cookies(trusted).get(DEVICE_COOKIE)
    assert device, trusted.headers.get_list("set-cookie")
    return device


async def test_ac11_a_trusted_device_skips_the_second_step_for_at_most_30_days(
    world: World,
) -> None:
    owner, email = await _client(world, "owner", "client_entity")
    enrolled = await _enrol(world, email)
    device = await _trusted(world, email, enrolled)
    skipped = await _state(world, email, device=device)
    assert skipped["state"] == "signed_in" and skipped["access_token"]
    [row] = await world.seed.rows(
        "SELECT created_at, expires_at FROM trusted_devices WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        owner.user_id,
    )
    assert row["expires_at"] - row["created_at"] <= timedelta(days=30)
    assert row["expires_at"] - row["created_at"] > timedelta(days=29)
    # Past its expiry the device no longer stands in for the second step.
    await world.seed.run(
        "UPDATE trusted_devices SET created_at = created_at - interval '31 days', "
        "expires_at = expires_at - interval '31 days' WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        owner.user_id,
    )
    expired = await _state(world, email, device=device)
    assert expired["state"] == "mfa_required" and expired.get("access_token") is None


async def test_ac11_the_firm_may_set_fewer_trusted_days(world: World) -> None:
    owner, email = await _client(world, "owner", "client_entity")
    await _policy(world, all_users=False, days=7)
    enrolled = await _enrol(world, email)
    await _trusted(world, email, enrolled)
    [row] = await world.seed.rows(
        "SELECT created_at, expires_at FROM trusted_devices WHERE tenant_id = $1 AND user_id = $2",
        world.tenant,
        owner.user_id,
    )
    assert row["expires_at"] - row["created_at"] <= timedelta(days=7)


async def test_ac11_a_device_cookie_of_another_person_or_none_never_skips(world: World) -> None:
    _, email = await _client(world, "owner", "client_entity")
    _, other_email = await _client(world, "owner", "client_entity")
    enrolled = await _enrol(world, email)
    device = await _trusted(world, email, enrolled)
    await _enrol(world, other_email)
    state = await _state(world, other_email, device=device)
    assert state["state"] == "mfa_required"
    assert (await _state(world, other_email, device="not-a-device"))["state"] == "mfa_required"


# ================================================================================================
# AC-12, AC-13: invitations v2
# ================================================================================================


async def _invitation(world: World) -> tuple[uuid.UUID, str, uuid.UUID]:
    """Grace invites a third-party contact to two of the engagement's requests: the invitation,
    the address and the contact (contacts-access §2, the O3 sheet)."""
    second = await world.seed.item(world.site, "Benefit statements")
    email = f"sam.{uuid.uuid4().hex[:8]}@example.test"
    contact = cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO contacts (tenant_id, client_id, display_name, email, organisation_name, "
            "contact_kind) VALUES ($1, $2, 'Sam Ortiz', $3, 'Keystone', 'third_party') "
            "RETURNING id",
            world.tenant,
            world.site.client_id,
            email,
        ),
    )
    items = [str(world.site.item_id), str(second)]
    response = await world.http.post(
        f"/v1/contacts/{contact}/invitations",
        json={
            "grants": [
                {
                    "role": "third_party",
                    "scope_kind": "request_item",
                    "scope_id": items[0],
                    "request_item_ids": items,
                }
            ],
            "expires_in_days": 14,
        },
        headers=world.net.headers(world.grace) | {"Idempotency-Key": uuid.uuid4().hex},
    )
    assert response.status_code == 201, response.text
    return uuid.UUID(response.json()["invitation_id"]), email, contact


async def _token(world: World, invitation: uuid.UUID) -> str:
    issued = await issue_invitation_token(world.tenant, invitation)
    assert issued is not None
    return issued.token


async def _preview(world: World, token: str, host: str | None = None) -> httpx.Response:
    world.http.cookies.clear()
    return await world.http.post(
        "/v1/invitations/preview", json={"token": token}, headers={"host": host or world.host}
    )


async def _invitee_session(world: World, email: str, token: str) -> str:
    http = world.http
    http.cookies.clear()
    start = await http.post(
        "/v1/portal/auth/start",
        json={"email": email, "invitation_token": token},
        headers={"host": world.host},
    )
    challenge = cast(str, start.json()["challenge_id"])
    issued = await issue_sign_in_code(uuid.UUID(challenge))
    assert issued is not None
    verified = await _post(
        world, "/v1/portal/auth/verify", {"challenge_id": challenge, "code": issued.code}
    )
    assert verified.status_code == 200, verified.text
    return cast(str, verified.json()["access_token"])


async def _accept(world: World, access: str, token: str) -> httpx.Response:
    world.http.cookies.clear()
    terms = await world.seed.value(
        "SELECT terms_version FROM client_invitations i JOIN invitation_tokens t "
        "ON t.invitation_id = i.id WHERE t.token_hash = encode(sha256(convert_to($1, 'UTF8')), "
        "'hex')",
        token,
    )
    body: Json = {"token": token} if terms is None else {"token": token, "terms_version": terms}
    return await world.http.post(
        "/v1/invitations/accept",
        json=body,
        headers={"host": world.host, "authorization": f"Bearer {access}"},
    )


async def test_ac12_preview_answers_the_same_404_for_every_failure(world: World, net: Net) -> None:
    live, _, _ = await _invitation(world)
    good = await _token(world, live)
    ok = await _preview(world, good)
    assert ok.status_code == 200, ok.text
    assert ok.json()["access"]["item_count"] == 2
    # expired (over 14 days)
    expired_id, _, _ = await _invitation(world)
    expired = await _token(world, expired_id)
    await world.seed.run(
        "UPDATE client_invitations SET created_at = created_at - interval '15 days', "
        "expires_at = expires_at - interval '15 days' WHERE id = $1",
        expired_id,
    )
    # used
    used_id, used_email, _ = await _invitation(world)
    used = await _token(world, used_id)
    accepted = await _accept(world, await _invitee_session(world, used_email, used), used)
    assert accepted.status_code == 200, accepted.text
    # revoked
    revoked_id, _, _ = await _invitation(world)
    revoked = await _token(world, revoked_id)
    revoke = await world.http.post(
        f"/v1/invitations/{revoked_id}/revoke", headers=net.headers(world.grace)
    )
    assert revoke.status_code == 200, revoke.text
    # a staff member's own invitation link (SPEC-024): never a portal invitation
    staff_token = "staff-" + uuid.uuid4().hex
    # another firm's live invitation, previewed on this firm's host
    other = World(net, await world.seed.firm(), world.host, world.grace, world.site)
    failures = {
        "expired": expired,
        "used": used,
        "revoked": revoked,
        "malformed": "not a token",
        "unknown": uuid.uuid4().hex + uuid.uuid4().hex,
        "staff": staff_token,
    }
    answers = {kind: await _preview(world, token) for kind, token in failures.items()}
    answers["another host"] = await _preview(world, good, host=f"x{other.tenant.hex[:6]}.test")
    bodies = {kind: (r.status_code, r.text) for kind, r in answers.items()}
    assert set(bodies.values()) == {(404, '{"detail":"not found"}')}, bodies


async def test_ac12_an_invitation_lasts_14_days_and_is_used_once(world: World) -> None:
    invitation, email, _ = await _invitation(world)
    row = await world.seed.rows(
        "SELECT created_at, expires_at FROM client_invitations WHERE id = $1", invitation
    )
    lasts = row[0]["expires_at"] - row[0]["created_at"]
    assert abs(lasts - timedelta(days=14)) < timedelta(seconds=1), lasts
    token = await _token(world, invitation)
    access = await _invitee_session(world, email, token)
    assert (await _accept(world, access, token)).status_code == 200
    again = await _accept(world, access, token)
    assert again.status_code == 404
    assert (await _preview(world, token)).status_code == 404


async def test_ac13_accept_grants_the_template_attributed_to_the_inviter(world: World) -> None:
    invitation, email, contact = await _invitation(world)
    token = await _token(world, invitation)
    access = await _invitee_session(world, email, token)
    accepted = await _accept(world, access, token)
    assert accepted.status_code == 200, accepted.text
    grants = await world.seed.rows(
        "SELECT user_id, role, scope_kind, status, granted_by FROM client_access_grants "
        "WHERE tenant_id = $1 AND contact_id = $2",
        world.tenant,
        contact,
    )
    assert len(grants) == 2
    assert {(g["role"], g["scope_kind"], g["status"]) for g in grants} == {
        ("third_party", "request_item", "active")
    }
    assert {g["granted_by"] for g in grants} == {world.grace.user_id}  # INV-5
    invitee = grants[0]["user_id"]
    grace = str(world.grace.user_id)
    for action, count in (("client_invitation.accepted", 1), ("client_access.granted", 2)):
        rows = await _audited(world, action)
        assert len(rows) == count, action
        for r in rows:  # the inviter, never the invitee and never an anonymous system
            attributed = {r["actor_id"], str(r["on_behalf_of_user_id"])}
            assert grace in attributed, (action, dict(r))
            assert r["actor_kind"] in ("human", "system"), action
            assert (
                r["actor_id"] != str(invitee) or r["on_behalf_of_user_id"] == world.grace.user_id
            )


# ================================================================================================
# AC-14: renewal goes only to the original address
# ================================================================================================


class _Mailbox:
    def __init__(self) -> None:
        self.sent: list[Json] = []

    def send(self, **message: object) -> None:
        self.sent.append(dict(message))


async def _renewal_template() -> None:
    await import_platform_version(
        "p08t24",
        "portal.link_renewed",
        "en-US",
        "Your new link from {{firm_name}}",
        "Hello,\n\n{{firm_name}} sent you a new link: {{app_link}}\n",
        ["firm_name", "app_link"],
    )


async def _deliver(world: World, event_type: str) -> None:
    handler = SUBSCRIPTIONS.get(event_type)
    assert handler is not None, event_type
    rows = await world.seed.rows(
        "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 ORDER BY id",
        world.tenant,
        event_type,
    )
    for row in rows:
        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)
        await handler(OutboxEvent(uuid.uuid4(), world.tenant, event_type, payload))


async def _renew(world: World, token: str) -> httpx.Response:
    return await _post(world, "/v1/portal/links/renew", {"link_token": token})


async def test_ac14_renew_answers_202_for_any_token_and_sends_only_to_the_original_address(
    world: World,
) -> None:
    await _renewal_template()
    who, email = await _client(world, "taxpayer", "client")
    contact = await _contact_of(world, who, email)
    link = await issue_secure_link(
        world.tenant,
        contact_id=contact,
        purpose="reminder",
        recipient_email=email,
        issued_by=world.grace.user_id,
        host=world.host,
    )
    # Story 5.1: a reminder link issued more than 14 days ago.
    await world.seed.run(
        "UPDATE secure_links SET issued_at = issued_at - interval '15 days', "
        "expires_at = expires_at - interval '15 days', "
        "chain_started_at = chain_started_at - interval '15 days' WHERE id = $1",
        link.link_id,
    )
    real = await _renew(world, link.token)
    unknown = await _renew(world, uuid.uuid4().hex * 2)
    malformed = await _renew(world, "x")
    answers = {(r.status_code, r.text) for r in (real, unknown, malformed)}
    assert answers == {(202, '{"accepted":true}')}, answers
    # The person's address on file changes; the old link's renewal still never reaches it.
    moved = f"moved.{uuid.uuid4().hex[:8]}@example.test"
    await world.seed.run("UPDATE users SET email = $2 WHERE id = $1", who.user_id, moved)
    await _renew(world, link.token)
    box = _Mailbox()
    configure_transport(box)
    try:
        await _deliver(world, "portal.link_renew_requested")
    finally:
        configure_transport(None)
    recipients = {str(m["to"]).lower() for m in box.sent}
    assert recipients == {email.lower()}, recipients
    assert len(await _audited(world, "secure_link.renewed")) >= 1


# ================================================================================================
# AC-18, AC-19: unlock and reset, people only (INV-1, INV-3, INV-5)
# ================================================================================================


async def _locked(world: World) -> tuple[Person, str, uuid.UUID]:
    who, email = await _client(world, "contributor", "engagement")
    contact = await _contact_of(world, who, email)
    http = world.http
    start = await http.post(
        "/v1/portal/auth/start", json={"email": email}, headers={"host": world.host}
    )
    challenge = start.json()["challenge_id"]
    last = None
    for _ in range(3):
        last = await _post(
            world, "/v1/portal/auth/verify", {"challenge_id": challenge, "code": "000000"}
        )
    assert last is not None and last.status_code == 423, last
    return who, email, contact


def _unlock_path(world: World, contact: uuid.UUID) -> str:
    return f"/v1/clients/{world.site.client_id}/contacts/{contact}/portal-unlock"


def _reset_path(world: World, contact: uuid.UUID) -> str:
    return f"/v1/clients/{world.site.client_id}/contacts/{contact}/mfa-reset"


def test_ac18_ac19_the_matrix_gives_unlock_and_reset_to_named_people_only() -> None:
    unlock = MATRIX["contact.unlock"].decisions
    reset = MATRIX["contact.mfa_reset"].decisions
    for decisions in (unlock, reset):
        assert decisions.get("agent", "deny") == "deny"
        assert decisions.get("system", "deny") == "deny"
        assert not {"client_admin", "client_contributor"} & {
            r for r, d in decisions.items() if d == "allow"
        }
    assert {r for r, d in reset.items() if d == "allow"} == {"security_admin"}
    assert RULES["contact.mfa_reset"].mfa_recent


async def test_ac18_unlock_clears_the_lock_names_the_person_and_a_walled_person_gets_404(
    world: World, net: Net
) -> None:
    _, email, contact = await _locked(world)
    walled = await world.seed.person(world.tenant, "firm_admin")
    await net.wall(world.grace, walled, world.site)
    hidden = await net.call("POST", _unlock_path(world, contact), walled)
    assert hidden.status_code == 404, hidden.text
    unlocked = await net.call("POST", _unlock_path(world, contact), world.grace)
    assert unlocked.status_code == 200, unlocked.text
    assert unlocked.json()["portal_status"] == "active"
    assert unlocked.json()["locked_until"] is None
    rows = await _audited(world, "contact.unlocked")
    assert [(r["actor_kind"], r["actor_id"]) for r in rows] == [
        ("human", str(world.grace.user_id))
    ]
    assert (await _state(world, email))["state"] == "signed_in"


async def _as_agent(world: World) -> httpx.AsyncClient:
    agent = await agent_context_for_run(
        tenant_id=world.tenant,
        run_id=uuid.uuid4(),
        agent_id="evidence.screener",
        engagement_id=world.site.engagement_id,
        task_scope=frozenset(RULES),
        initiator_user_id=world.grace.user_id,
    )
    app = create_app()
    app.dependency_overrides[current_context] = lambda: agent
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_inv1_the_agent_is_refused_unlock_and_reset_and_nothing_changes(
    world: World,
) -> None:
    await world.seed.member(world.site, world.grace, "engagement_partner")
    _, email, contact = await _locked(world)
    before = await world.seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1", world.tenant
    )
    async with await _as_agent(world) as agent:
        unlock = await agent.post(_unlock_path(world, contact))
        reset = await agent.post(
            _reset_path(world, contact), headers={"Idempotency-Key": uuid.uuid4().hex}
        )
    assert unlock.status_code == 403, unlock.text
    assert reset.status_code == 403, reset.text
    assert (
        await world.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND action IN "
            "('contact.unlocked', 'portal_mfa.reset')",
            world.tenant,
        )
        == 0
    )
    assert (
        await world.seed.value(
            "SELECT count(*) FROM audit_events WHERE tenant_id = $1", world.tenant
        )
        == before
    )
    still = await _verify(world, email)
    assert still.status_code == 423  # still locked


async def test_ac19_reset_is_security_admins_with_fresh_mfa_and_revokes_this_firms_devices(
    world: World, net: Net
) -> None:
    owner, email = await _client(world, "owner", "client_entity")
    contact = await _contact_of(world, owner, email)
    enrolled = await _enrol(world, email)
    device = await _trusted(world, email, enrolled)
    assert (await _state(world, email, device=device))["state"] == "signed_in"
    felix = await world.seed.person(world.tenant, "security_admin")

    async def reset(who: Person, *, mfa: bool = True) -> httpx.Response:
        return await world.http.post(
            _reset_path(world, contact),
            headers=net.headers(who, mfa=mfa) | {"Idempotency-Key": uuid.uuid4().hex},
        )

    assert (await reset(world.grace)).status_code in (403, 404)  # firm admin: not theirs
    assert (await reset(felix, mfa=False)).status_code in (401, 403)  # no fresh MFA
    done = await reset(felix)
    assert done.status_code == 200, done.text
    assert done.json()["trusted_devices_revoked"] >= 1
    rows = await _audited(world, "portal_mfa.reset")
    assert [(r["actor_kind"], r["actor_id"]) for r in rows] == [("human", str(felix.user_id))]
    # The device no longer stands in for the second step; the factor itself stays (DEC-329).
    asked = await _state(world, email, device=device)
    assert asked["state"] == "mfa_required" and asked.get("access_token") is None
    assert (
        await world.seed.value(
            "SELECT count(*) FROM mfa_factors WHERE user_id = $1", owner.user_id
        )
        == 1
    )


# ================================================================================================
# AC-20: the per-firm sign-in pause, within 10 seconds
# ================================================================================================


async def _set_pause(world: World, active: bool) -> None:
    await world.seed.run(
        "SELECT set_platform_control('portal_sign_in', 'firm', $1, NULL, $2, 'P-08-T24 drill', "
        "'p08t24', NULL)",
        world.tenant,
        active,
    )


@pytest.mark.serial
async def test_ac20_the_pause_takes_effect_within_10_seconds_and_keeps_sessions(
    world: World,
) -> None:
    _, email = await _client(world, "contributor", "engagement")
    signed = await _state(world, email)
    access = cast(str, signed["access_token"])
    http = world.http
    pending = await http.post(
        "/v1/portal/auth/start", json={"email": email}, headers={"host": world.host}
    )
    challenge = pending.json()["challenge_id"]
    await _set_pause(world, True)
    paused_at = time.monotonic()
    try:
        answer = None
        while time.monotonic() - paused_at < 12:
            answer = await http.post(
                "/v1/portal/auth/start", json={"email": email}, headers={"host": world.host}
            )
            if answer.status_code == 503:
                break
            await asyncio.sleep(0.5)
        took = time.monotonic() - paused_at
        assert answer is not None and answer.status_code == 503, answer
        assert answer.json() == {"detail": "sign_in_paused"}
        assert took <= 10.5, took
        verify = await _post(
            world, "/v1/portal/auth/verify", {"challenge_id": challenge, "code": "123456"}
        )
        assert verify.status_code == 503 and verify.json() == {"detail": "sign_in_paused"}
        # An existing session is unaffected.
        http.cookies.clear()
        me = await http.get(
            f"/v1/portal/home?scope_id={world.site.engagement_id}",
            headers={"host": world.host, "authorization": f"Bearer {access}"},
        )
        assert me.status_code == 200, me.text
    finally:
        await _set_pause(world, False)


DEVICE_COOKIE = "__Host-abacus-portal-device"  # P-08 Story 3.1: a `__Host-` cookie
