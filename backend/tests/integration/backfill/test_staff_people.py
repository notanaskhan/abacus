"""SPEC-024 AC-3, AC-4 (TASK-041): a firm administrator invites staff with a firm role, changes
roles and revokes access; the firm is never left without an administrator.

HTTP through `create_app()` against a real Postgres. The invitation email is communications'
job: here its one effect is replayed by asking identity for the token the way delivery does
(`issue_staff_invitation_token`). Expectations come from the spec, not the implementation.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import httpx
import pytest

from abacus.modules.identity.api import issue_staff_invitation_token

from .support import Net, Person, Seeder

FORBIDDEN = {"detail": "forbidden"}
NOT_FOUND = {"detail": "not found"}


class Firm:
    def __init__(self, net: Net, tenant_id: uuid.UUID, admin: Person) -> None:
        self.net = net
        self.tenant_id = tenant_id
        self.admin = admin

    async def invite(self, email: str, role: str | None = "practice_leader") -> uuid.UUID:
        response = await self.net.call(
            "POST",
            "/v1/firm/staff/invitations",
            self.admin,
            body={"email": email, "firm_role": role},
        )
        assert response.status_code == 201, response.text
        return uuid.UUID(cast(str, response.json()["id"]))

    async def token(self, invitation_id: uuid.UUID) -> str:
        issued = await issue_staff_invitation_token(self.tenant_id, invitation_id)
        assert issued is not None
        return issued.token

    async def accept(self, email: str, token: str) -> tuple[httpx.Response, str]:
        subject, headers = self.net.newcomer(email)
        response = await self.net.http.post(
            "/v1/invitations/staff/accept", json={"token": token}, headers=headers
        )
        return response, subject

    async def status(self, invitation_id: uuid.UUID) -> str:
        return str(
            await self.net.seed.value(
                "SELECT status FROM staff_invitations WHERE id = $1", invitation_id
            )
        )

    async def membership(self, user_id: uuid.UUID) -> tuple[str | None, str]:
        row = (
            await self.net.seed.rows(
                "SELECT firm_role, status FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                self.tenant_id,
                user_id,
            )
        )[0]
        return row["firm_role"], str(row["status"])


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    return Firm(net, tenant_id, await seed.person(tenant_id, "firm_admin"))


async def _person_of(seed: Seeder, tenant_id: uuid.UUID, subject: str) -> Person:
    user_id = cast(
        uuid.UUID, await seed.value("SELECT id FROM users WHERE idp_subject = $1", subject)
    )
    return Person(user_id, tenant_id, subject)


# --- AC-3: invite, accept, resend, revoke --------------------------------------------------------


async def test_ac3_a_firm_administrator_invites_a_person_with_a_firm_role(
    firm: Firm, seed: Seeder
) -> None:
    invitation_id = await firm.invite("Pat.Lee@Example.test", "quality_partner")
    row = (
        await seed.rows(
            "SELECT email, firm_role, status, invited_by, expires_at - created_at AS span "
            "FROM staff_invitations WHERE id = $1",
            invitation_id,
        )
    )[0]
    assert (row["email"], row["firm_role"], row["status"]) == (
        "Pat.Lee@Example.test",
        "quality_partner",
        "pending",
    )
    assert row["invited_by"] == firm.admin.user_id
    assert timedelta(days=13, hours=23) < row["span"] <= timedelta(days=14, minutes=1)
    assert "staff_invitation.created" in await seed.actions(firm.tenant_id)
    outbox = await seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND payload::text LIKE $2",
        firm.tenant_id,
        f"%{invitation_id}%",
    )
    assert outbox == 1  # delivery is asked for, by event
    listed = (await firm.net.call("GET", "/v1/firm/staff", firm.admin)).json()
    assert [i["id"] for i in listed["invitations"]] == [str(invitation_id)]
    assert [m["user_id"] for m in listed["members"]] == [str(firm.admin.user_id)]


async def test_ac3_the_link_is_single_use_and_stores_only_a_hash(firm: Firm, seed: Seeder) -> None:
    invitation_id = await firm.invite("pat@example.test")
    token = await firm.token(invitation_id)
    stored = await seed.rows(
        "SELECT token_hash FROM staff_invitation_tokens WHERE invitation_id = $1", invitation_id
    )
    assert [r["token_hash"] for r in stored] == [hashlib.sha256(token.encode()).hexdigest()]
    first, _ = await firm.accept("pat@example.test", token)
    assert first.status_code == 200, first.text
    again, _ = await firm.accept("pat@example.test", token)
    assert again.status_code == 404  # one answer for a used link
    assert await firm.status(invitation_id) == "accepted"


async def test_ac3_the_person_who_accepts_becomes_a_member_with_that_role(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    invitation_id = await firm.invite("pat@example.test", "practice_leader")
    accepted, subject = await firm.accept("pat@example.test", await firm.token(invitation_id))
    assert accepted.status_code == 200, accepted.text
    assert accepted.json() == {"tenant_id": str(firm.tenant_id)}
    pat = await _person_of(seed, firm.tenant_id, subject)
    assert await firm.membership(pat.user_id) == ("practice_leader", "active")
    assert "staff_invitation.accepted" in await seed.actions(firm.tenant_id)
    me = (await net.call("GET", "/v1/me", pat)).json()
    assert [m["tenant_id"] for m in me["memberships"]] == [str(firm.tenant_id)]
    assert me["memberships"][0]["firm_role"] == "practice_leader"
    listed = (await net.call("GET", "/v1/firm/staff", firm.admin)).json()
    assert listed["invitations"] == []
    assert {m["user_id"] for m in listed["members"]} == {
        str(firm.admin.user_id),
        str(pat.user_id),
    }


async def test_ac3_an_invitation_without_a_firm_role_makes_a_member_without_one(
    firm: Firm, seed: Seeder
) -> None:
    invitation_id = await firm.invite("pat@example.test", None)
    accepted, subject = await firm.accept("pat@example.test", await firm.token(invitation_id))
    assert accepted.status_code == 200, accepted.text
    pat = await _person_of(seed, firm.tenant_id, subject)
    assert await firm.membership(pat.user_id) == (None, "active")


async def test_ac3_the_email_must_match_the_invitation_and_the_link_survives_it(
    firm: Firm,
) -> None:
    invitation_id = await firm.invite("pat@example.test")
    token = await firm.token(invitation_id)
    wrong, _ = await firm.accept("someone.else@example.test", token)
    assert wrong.status_code == 404
    assert await firm.status(invitation_id) == "pending"
    right, _ = await firm.accept("PAT@example.test", token)  # case does not matter
    assert right.status_code == 200, right.text


async def test_ac3_an_unknown_token_is_not_found_and_a_malformed_one_is_not_a_token(
    firm: Firm,
) -> None:
    unknown, _ = await firm.accept("pat@example.test", uuid.uuid4().hex + uuid.uuid4().hex)
    assert unknown.status_code == 404
    assert unknown.json() == NOT_FOUND
    malformed, _ = await firm.accept("pat@example.test", "short")
    assert malformed.status_code == 422


async def test_ac3_a_token_with_no_verified_email_is_refused(firm: Firm, net: Net) -> None:
    invitation_id = await firm.invite("pat@example.test")
    token = await firm.token(invitation_id)
    bare = net.idp.token(f"new-{uuid.uuid4().hex}")  # no email claim
    response = await net.http.post(
        "/v1/invitations/staff/accept",
        json={"token": token},
        headers={"Authorization": f"Bearer {bare}"},
    )
    assert response.status_code == 404
    assert await firm.status(invitation_id) == "pending"


async def test_ac3_ten_failed_tries_lock_the_identity_out_even_for_the_right_link(
    firm: Firm,
) -> None:
    invitation_id = await firm.invite("pat@example.test")
    token = await firm.token(invitation_id)
    subject, headers = firm.net.newcomer("pat@example.test")
    for _ in range(10):
        bad = await firm.net.http.post(
            "/v1/invitations/staff/accept",
            json={"token": uuid.uuid4().hex + uuid.uuid4().hex},
            headers=headers,
        )
        assert bad.status_code == 404
    locked = await firm.net.http.post(
        "/v1/invitations/staff/accept", json={"token": token}, headers=headers
    )
    assert locked.status_code == 404
    assert await firm.status(invitation_id) == "pending"
    other, _ = await firm.accept("pat@example.test", token)  # another identity is not locked
    assert other.status_code == 200, other.text
    assert subject


async def test_ac3_an_expired_invitation_cannot_be_accepted_or_delivered(
    firm: Firm, seed: Seeder
) -> None:
    invitation_id = await firm.invite("pat@example.test")
    token = await firm.token(invitation_id)
    await seed.run(
        "UPDATE staff_invitations SET expires_at = $2 WHERE id = $1",
        invitation_id,
        datetime.now(UTC) - timedelta(minutes=1),
    )
    response, _ = await firm.accept("pat@example.test", token)
    assert response.status_code == 404
    assert await issue_staff_invitation_token(firm.tenant_id, invitation_id) is None


async def test_ac3_resend_extends_the_expiry_asks_for_delivery_and_replaces_the_link(
    firm: Firm, seed: Seeder
) -> None:
    invitation_id = await firm.invite("pat@example.test")
    old = await firm.token(invitation_id)
    await seed.run(
        "UPDATE staff_invitations SET expires_at = now() + interval '1 day' WHERE id = $1",
        invitation_id,
    )
    resent = await firm.net.call(
        "POST", f"/v1/firm/staff/invitations/{invitation_id}/resend", firm.admin
    )
    assert resent.status_code == 200, resent.text
    span = await seed.value(
        "SELECT expires_at - clock_timestamp() FROM staff_invitations WHERE id = $1", invitation_id
    )
    assert cast(timedelta, span) > timedelta(days=13)
    assert "staff_invitation.resent" in await seed.actions(firm.tenant_id)
    new = await firm.token(invitation_id)  # delivery issues a fresh link ...
    assert new != old
    stale, _ = await firm.accept("pat@example.test", old)  # ... and the earlier one stops working
    assert stale.status_code == 404
    fresh, _ = await firm.accept("pat@example.test", new)
    assert fresh.status_code == 200, fresh.text


async def test_ac3_revoking_an_invitation_ends_its_link(firm: Firm, seed: Seeder) -> None:
    invitation_id = await firm.invite("pat@example.test")
    token = await firm.token(invitation_id)
    revoked = await firm.net.call(
        "POST", f"/v1/firm/staff/invitations/{invitation_id}/revoke", firm.admin
    )
    assert revoked.status_code == 200, revoked.text
    assert await firm.status(invitation_id) == "revoked"
    assert "staff_invitation.revoked" in await seed.actions(firm.tenant_id)
    response, _ = await firm.accept("pat@example.test", token)
    assert response.status_code == 404
    for action in ("resend", "revoke"):  # it is no longer pending
        again = await firm.net.call(
            "POST", f"/v1/firm/staff/invitations/{invitation_id}/{action}", firm.admin
        )
        assert again.status_code == 404
    assert await issue_staff_invitation_token(firm.tenant_id, invitation_id) is None


async def test_ac3_inviting_the_same_email_again_replaces_the_pending_invitation(
    firm: Firm, seed: Seeder
) -> None:
    first = await firm.invite("pat@example.test", "practice_leader")
    old = await firm.token(first)
    second = await firm.invite("PAT@example.test", "quality_partner")
    assert (await firm.status(first), await firm.status(second)) == ("revoked", "pending")
    stale, _ = await firm.accept("pat@example.test", old)
    assert stale.status_code == 404
    accepted, subject = await firm.accept("pat@example.test", await firm.token(second))
    assert accepted.status_code == 200
    pat = await _person_of(seed, firm.tenant_id, subject)
    assert (await firm.membership(pat.user_id))[0] == "quality_partner"


async def test_ac3_a_revoked_member_who_accepts_again_is_active_with_the_new_role(
    firm: Firm, seed: Seeder
) -> None:
    invitation_id = await firm.invite("pat@example.test", "practice_leader")
    accepted, subject = await firm.accept("pat@example.test", await firm.token(invitation_id))
    assert accepted.status_code == 200
    pat = await _person_of(seed, firm.tenant_id, subject)
    revoked = await firm.net.call("POST", f"/v1/firm/staff/{pat.user_id}/revoke", firm.admin)
    assert revoked.status_code == 200, revoked.text
    again = await firm.invite("pat@example.test", "quality_partner")
    token = await firm.token(again)
    joined = await firm.net.http.post(
        "/v1/invitations/staff/accept",
        json={"token": token},
        headers=firm.net.identity(subject, "pat@example.test"),  # the same sign-in
    )
    assert joined.status_code == 200, joined.text
    assert await firm.membership(pat.user_id) == ("quality_partner", "active")


async def test_ac3_a_client_contact_of_the_firm_cannot_also_be_its_staff(
    firm: Firm, seed: Seeder
) -> None:
    contact = await seed.person(firm.tenant_id)
    await seed.run(
        "UPDATE memberships SET kind = 'client' WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        contact.user_id,
    )
    email = str(await seed.value("SELECT email FROM users WHERE id = $1", contact.user_id))
    invitation_id = await firm.invite(email)
    token = await firm.token(invitation_id)
    response = await firm.net.http.post(
        "/v1/invitations/staff/accept",
        json={"token": token},
        headers=firm.net.identity(contact.subject, email),
    )
    assert response.status_code == 409, response.text
    assert await firm.status(invitation_id) == "pending"
    assert (
        await seed.value(
            "SELECT kind FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            firm.tenant_id,
            contact.user_id,
        )
        == "client"
    )


@pytest.mark.parametrize("email", ["", "no-at-sign", "a@", "x" * 330 + "@example.test"])
async def test_ac3_an_invitation_needs_a_plausible_email(firm: Firm, email: str) -> None:
    response = await firm.net.call(
        "POST",
        "/v1/firm/staff/invitations",
        firm.admin,
        body={"email": email, "firm_role": None},
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize("role", [None, "practice_leader", "quality_partner"])
async def test_ac3_only_a_firm_administrator_with_fresh_mfa_manages_people(
    firm: Firm, seed: Seeder, role: str | None
) -> None:
    invitation_id = await firm.invite("pending@example.test")
    other = await seed.person(firm.tenant_id, role)
    calls = (
        ("GET", "/v1/firm/staff", None),
        ("POST", "/v1/firm/staff/invitations", {"email": "x@example.test", "firm_role": None}),
        ("POST", f"/v1/firm/staff/invitations/{invitation_id}/resend", None),
        ("POST", f"/v1/firm/staff/invitations/{invitation_id}/revoke", None),
        ("PUT", f"/v1/firm/staff/{firm.admin.user_id}/role", {"firm_role": None}),
        ("POST", f"/v1/firm/staff/{firm.admin.user_id}/revoke", None),
    )
    before = await seed.actions(firm.tenant_id)
    for method, path, body in calls:
        response = await firm.net.call(method, path, other, body=body)
        assert response.status_code == 403, (method, path, response.text)
        assert response.json() == FORBIDDEN
    assert await seed.actions(firm.tenant_id) == before
    assert await firm.status(invitation_id) == "pending"
    assert await firm.membership(firm.admin.user_id) == ("firm_admin", "active")


async def test_ac3_a_firm_administrator_without_fresh_mfa_is_refused(firm: Firm) -> None:
    for method, path, body in (
        ("GET", "/v1/firm/staff", None),
        ("POST", "/v1/firm/staff/invitations", {"email": "x@example.test", "firm_role": None}),
    ):
        response = await firm.net.call(method, path, firm.admin, body=body, mfa=False)
        assert response.status_code == 403, response.text


# --- AC-4: change a role, revoke access, never the last administrator ----------------------------


async def _member(firm: Firm, seed: Seeder, role: str | None) -> Person:
    return await seed.person(firm.tenant_id, role)


async def test_ac4_a_changed_role_applies_on_the_members_next_request_and_is_audited(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    pat = await _member(firm, seed, "practice_leader")
    assert (await net.call("GET", "/v1/engagements", pat)).status_code == 200
    before = (await net.call("GET", "/v1/me", pat)).json()["memberships"][0]["firm_role"]
    assert before == "practice_leader"
    changed = await net.call(
        "PUT", f"/v1/firm/staff/{pat.user_id}/role", firm.admin, body={"firm_role": "firm_admin"}
    )
    assert changed.status_code == 200, changed.text
    after = (await net.call("GET", "/v1/me", pat)).json()["memberships"][0]["firm_role"]
    assert after == "firm_admin"  # the same token, the next request
    assert (
        await net.call("GET", "/v1/firm/staff", pat)
    ).status_code == 200  # now an administrator
    assert "membership.role_changed" in await seed.actions(firm.tenant_id)
    await net.call(
        "PUT", f"/v1/firm/staff/{pat.user_id}/role", firm.admin, body={"firm_role": None}
    )
    assert (await net.call("GET", "/v1/firm/staff", pat)).status_code == 403


async def test_ac4_revoked_access_refuses_the_members_next_request_and_is_audited(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    pat = await _member(firm, seed, "practice_leader")
    assert (await net.call("GET", "/v1/engagements", pat)).status_code == 200
    revoked = await net.call("POST", f"/v1/firm/staff/{pat.user_id}/revoke", firm.admin)
    assert revoked.status_code == 200, revoked.text
    refused = await net.call("GET", "/v1/engagements", pat)  # the same token
    assert refused.status_code == 403
    assert refused.json() == FORBIDDEN
    assert await firm.membership(pat.user_id) == ("practice_leader", "revoked")
    assert "membership.revoked" in await seed.actions(firm.tenant_id)
    listed = (await net.call("GET", "/v1/firm/staff", firm.admin)).json()
    [shown] = [m for m in listed["members"] if m["user_id"] == str(pat.user_id)]
    assert shown["status"] == "revoked"


async def test_ac4_the_last_firm_administrator_cannot_be_demoted_or_removed(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    before = await seed.actions(firm.tenant_id)
    for role in (None, "practice_leader", "quality_partner"):
        demoted = await net.call(
            "PUT",
            f"/v1/firm/staff/{firm.admin.user_id}/role",
            firm.admin,
            body={"firm_role": role},
        )
        assert demoted.status_code == 409, demoted.text
        assert demoted.json() == {"detail": "last_admin"}
    removed = await net.call("POST", f"/v1/firm/staff/{firm.admin.user_id}/revoke", firm.admin)
    assert removed.status_code == 409, removed.text
    assert await firm.membership(firm.admin.user_id) == ("firm_admin", "active")
    assert await seed.actions(firm.tenant_id) == before  # nothing was audited as changed


async def test_ac4_with_two_administrators_one_can_step_down_but_not_the_other(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    second = await _member(firm, seed, "firm_admin")
    stepped = await net.call(
        "PUT", f"/v1/firm/staff/{firm.admin.user_id}/role", second, body={"firm_role": None}
    )
    assert stepped.status_code == 200, stepped.text
    last = await net.call(
        "PUT", f"/v1/firm/staff/{second.user_id}/role", second, body={"firm_role": None}
    )
    assert last.status_code == 409, last.text
    assert await firm.membership(second.user_id) == ("firm_admin", "active")


async def test_ac4_a_revoked_administrator_does_not_count_as_one(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    gone = await _member(firm, seed, "firm_admin")
    await seed.revoke(gone)
    refused = await net.call("POST", f"/v1/firm/staff/{firm.admin.user_id}/revoke", firm.admin)
    assert refused.status_code == 409, refused.text


async def test_ac4_an_unknown_member_is_not_found_and_nothing_is_audited(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    before = await seed.actions(firm.tenant_id)
    ghost = uuid.uuid4()
    for method, path, body in (
        ("PUT", f"/v1/firm/staff/{ghost}/role", {"firm_role": None}),
        ("POST", f"/v1/firm/staff/{ghost}/revoke", None),
    ):
        response = await net.call(method, path, firm.admin, body=body)
        assert response.status_code == 404, response.text
    assert await seed.actions(firm.tenant_id) == before


async def test_ac4_a_role_outside_the_three_firm_roles_is_refused(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    pat = await _member(firm, seed, "practice_leader")
    response = await net.call(
        "PUT", f"/v1/firm/staff/{pat.user_id}/role", firm.admin, body={"firm_role": "owner"}
    )
    assert response.status_code == 422, response.text
    assert await firm.membership(pat.user_id) == ("practice_leader", "active")


# --- Q-03-T006 additions (ac-test-author: ayushkbhatia) -----------------------------------------
# SPEC-024 AC-3 "resend and revoke behave as client invitations do", and the ADR P-10 role
# catalogue (DEC-21): `security_admin` joins the three SPEC-024 firm roles.


async def test_ac3_resend_ends_the_old_link_at_once(firm: Firm) -> None:
    """A resent invitation's earlier link stops working when it is resent, not later when the new
    email happens to be delivered (as a client invitation's does, SPEC-015 AC-10)."""
    invitation_id = await firm.invite("pat@example.test")
    old = await firm.token(invitation_id)
    resent = await firm.net.call(
        "POST", f"/v1/firm/staff/invitations/{invitation_id}/resend", firm.admin
    )
    assert resent.status_code == 200, resent.text
    stale, _ = await firm.accept("pat@example.test", old)  # before any new link is issued
    assert stale.status_code == 404
    assert stale.json() == NOT_FOUND
    assert await firm.status(invitation_id) == "pending"
    fresh, _ = await firm.accept("pat@example.test", await firm.token(invitation_id))
    assert fresh.status_code == 200, fresh.text


async def test_ac3_a_security_admin_does_not_manage_people(firm: Firm, seed: Seeder) -> None:
    """P-10: `security_admin` is a firm role, but people stay `firm.manage_users` (firm admin)."""
    security = await seed.person(firm.tenant_id, "security_admin")
    invitation_id = await firm.invite("pending@example.test")
    before = await seed.actions(firm.tenant_id)
    for method, path, body in (
        ("GET", "/v1/firm/staff", None),
        ("POST", "/v1/firm/staff/invitations", {"email": "x@example.test", "firm_role": None}),
        ("POST", f"/v1/firm/staff/invitations/{invitation_id}/revoke", None),
        ("PUT", f"/v1/firm/staff/{firm.admin.user_id}/role", {"firm_role": None}),
        ("POST", f"/v1/firm/staff/{firm.admin.user_id}/revoke", None),
    ):
        response = await firm.net.call(method, path, security, body=body)
        assert response.status_code == 403, (method, path, response.text)
        assert response.json() == FORBIDDEN
    assert await seed.actions(firm.tenant_id) == before
    assert await firm.status(invitation_id) == "pending"


async def test_ac4_a_firm_with_a_security_admin_still_lists_its_people(
    firm: Firm, seed: Seeder
) -> None:
    """P-10: a member holding the catalogue's `security_admin` is listed with that role."""
    security = await seed.person(firm.tenant_id, "security_admin")
    listed = await firm.net.call("GET", "/v1/firm/staff", firm.admin)
    assert listed.status_code == 200, listed.text
    roles = {m["user_id"]: m["firm_role"] for m in listed.json()["members"]}
    assert roles[str(security.user_id)] == "security_admin"


async def test_ac3_an_administrator_invites_a_security_admin(firm: Firm, seed: Seeder) -> None:
    """P-10: an invitation may carry any firm role of the catalogue, `security_admin` included."""
    invitation_id = await firm.invite("sec@example.test", "security_admin")
    accepted, subject = await firm.accept("sec@example.test", await firm.token(invitation_id))
    assert accepted.status_code == 200, accepted.text
    who = await _person_of(seed, firm.tenant_id, subject)
    assert await firm.membership(who.user_id) == ("security_admin", "active")


async def test_ac4_an_administrator_changes_a_member_to_security_admin(
    firm: Firm, seed: Seeder, net: Net
) -> None:
    pat = await _member(firm, seed, "practice_leader")
    changed = await net.call(
        "PUT",
        f"/v1/firm/staff/{pat.user_id}/role",
        firm.admin,
        body={"firm_role": "security_admin"},
    )
    assert changed.status_code == 200, changed.text
    assert await firm.membership(pat.user_id) == ("security_admin", "active")
