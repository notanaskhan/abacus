# ac-test-author: ayushkbhatia
"""SPEC-015 AC-1 to AC-10 (TASK-030; back-filled by Q-03-T007): client invitations and client
users, against the migrated C5 grant model (ADR P-09, F-03-T26, DEC-129).

HTTP through `create_app()` against a real Postgres. Expectations come from SPEC-015, read
through C5: a client's role on an engagement is now a `client_access_grants` row (`owner` for a
client admin, `contributor` for a client contributor) at `engagement` scope, and
`engagement_members` holds staff only (TASK-373). Delivery is replayed by handing the outbox event
to communications' public subscriber, the way the relay does, with a recording transport.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import cast

import httpx
import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.communications.api import SUBSCRIPTIONS, configure_transport
from abacus.modules.identity.api import ClientInvitationIssued

from .support import Net, Person, Seeder, Site

NOT_FOUND = {"detail": "not found"}
REFUSED = (403, 404)  # the spec says "refused" without a code: either is a refusal


@dataclass
class Mail:
    to: str
    subject: str
    body: str
    sender_name: str | None


@dataclass
class Mailbox:
    """A transport that keeps what it is asked to send (the protocol communications declares)."""

    sent: list[Mail] = field(default_factory=list[Mail])

    def send(
        self,
        *,
        to: str,
        subject: str,
        body: str,
        sender_name: str | None = None,
        reply_to: str | None = None,
        tenant_id: uuid.UUID | None = None,
        message_id: uuid.UUID | None = None,
    ) -> None:
        del reply_to, tenant_id, message_id
        self.sent.append(Mail(to, subject, body, sender_name))


@pytest.fixture
def mailbox() -> Iterator[Mailbox]:
    box = Mailbox()
    configure_transport(box)
    yield box
    configure_transport(None)


class Desk:
    """One firm with two clients, each with an open engagement; a partner and a manager staff
    both."""

    def __init__(
        self,
        net: Net,
        mailbox: Mailbox,
        tenant_id: uuid.UUID,
        partner: Person,
        manager: Person,
        a: Site,
        b: Site,
    ) -> None:
        self.net = net
        self.seed = net.seed
        self.mailbox = mailbox
        self.tenant_id = tenant_id
        self.partner = partner
        self.manager = manager
        self.a = a
        self.b = b

    @staticmethod
    def base(site: Site) -> str:
        return f"/v1/engagements/{site.engagement_id}"

    async def invite(
        self, who: Person, email: str, role: str = "client_admin", site: Site | None = None
    ) -> httpx.Response:
        return await self.net.call(
            "POST",
            f"{self.base(site or self.a)}/client-invitations",
            who,
            body={"email": email, "role": role},
        )

    async def invited(
        self, email: str, role: str = "client_admin", site: Site | None = None
    ) -> uuid.UUID:
        response = await self.invite(self.partner, email, role, site)
        assert response.status_code == 201, response.text
        return uuid.UUID(cast(str, response.json()["invitation_id"]))

    async def events(self, invitation_id: uuid.UUID) -> list[OutboxEvent]:
        rows = await self.seed.rows(
            "SELECT id, tenant_id, event_type, payload FROM outbox WHERE tenant_id = $1 "
            "AND payload->>'invitation_id' = $2 ORDER BY seq",
            self.tenant_id,
            str(invitation_id),
        )
        return [
            OutboxEvent(
                r["id"], r["tenant_id"], str(r["event_type"]), json.loads(str(r["payload"]))
            )
            for r in rows
        ]

    async def deliver(self, invitation_id: uuid.UUID) -> str:
        """Hand the invitation's latest event to communications, as the relay does; the token
        is read from the link in the email that went out."""
        event = (await self.events(invitation_id))[-1]
        before = len(self.mailbox.sent)
        await SUBSCRIPTIONS[ClientInvitationIssued.event_type](event)
        assert len(self.mailbox.sent) == before + 1, "no email went out"
        found = re.search(r"#token=([A-Za-z0-9_\-]+)", self.mailbox.sent[-1].body)
        assert found is not None, "the email carries no link"
        return found.group(1)

    async def accept(
        self, email: str, token: str, *, subject: str | None = None
    ) -> tuple[httpx.Response, str]:
        subject = subject or f"new-{uuid.uuid4().hex}"
        response = await self.net.http.post(
            "/v1/invitations/accept",
            json={"token": token},
            headers=self.net.identity(subject, email),
        )
        return response, subject

    async def client(
        self, email: str, role: str = "client_admin", site: Site | None = None
    ) -> Person:
        """An accepted client user of `site` (default A)."""
        invitation_id = await self.invited(email, role, site)
        response, subject = await self.accept(email, await self.deliver(invitation_id))
        assert response.status_code == 200, response.text
        user_id = cast(
            uuid.UUID,
            await self.seed.value("SELECT id FROM users WHERE idp_subject = $1", subject),
        )
        return Person(user_id, self.tenant_id, subject)

    async def status(self, invitation_id: uuid.UUID) -> str:
        return str(
            await self.seed.value(
                "SELECT status FROM client_invitations WHERE id = $1", invitation_id
            )
        )

    async def grants(self, user_id: uuid.UUID) -> set[tuple[str, str, uuid.UUID, str]]:
        rows = await self.seed.rows(
            "SELECT role, scope_kind, scope_id, status FROM client_access_grants "
            "WHERE user_id = $1",
            user_id,
        )
        return {(r["role"], r["scope_kind"], r["scope_id"], r["status"]) for r in rows}

    async def actions(self) -> list[str]:
        return await self.seed.actions(self.tenant_id)


@pytest.fixture
async def desk(net: Net, seed: Seeder, mailbox: Mailbox) -> Desk:
    tenant_id = await seed.firm()
    partner = await seed.person(tenant_id)
    manager = await seed.person(tenant_id)
    a = await seed.site(tenant_id, partner.user_id, "Ashford")
    b = await seed.site(tenant_id, partner.user_id, "Birchwood")
    for site in (a, b):
        await seed.member(site, partner, "engagement_partner")
        await seed.member(site, manager, "manager")
    return Desk(net, mailbox, tenant_id, partner, manager, a, b)


# --- AC-1: the firm invites ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("inviter", "role"), [("partner", "client_admin"), ("manager", "client_contributor")]
)
async def test_ac1_a_partner_or_manager_invites_and_a_pending_invitation_is_stored(
    desk: Desk, inviter: str, role: str
) -> None:
    who = desk.partner if inviter == "partner" else desk.manager
    response = await desk.invite(who, "CFO@Ashford.example", role)
    assert response.status_code == 201, response.text
    invitation_id = uuid.UUID(cast(str, response.json()["invitation_id"]))
    row = (
        await desk.seed.rows(
            "SELECT email, role, status, invited_by, engagement_id, "
            "expires_at - created_at AS span FROM client_invitations WHERE id = $1",
            invitation_id,
        )
    )[0]
    assert (row["email"], row["role"], row["status"]) == ("CFO@Ashford.example", role, "pending")
    assert (row["invited_by"], row["engagement_id"]) == (who.user_id, desk.a.engagement_id)
    # SPEC-320 supersedes SPEC-015 Q3's 7 days (DEC-35, P-08-T18): 14 days, single use.
    assert timedelta(days=13, hours=23) < row["span"] <= timedelta(days=14, minutes=1)
    assert "client_invitation.created" in await desk.actions()
    assert len(await desk.events(invitation_id)) == 1  # delivery is asked for by event


async def test_ac1_the_response_never_carries_the_link_or_a_token(desk: Desk) -> None:
    response = await desk.invite(desk.partner, "cfo@ashford.example")
    assert response.status_code == 201, response.text
    text = response.text.lower()
    assert "token" not in text and "#" not in text and "http" not in text
    invitation_id = uuid.UUID(cast(str, response.json()["invitation_id"]))
    token = await desk.deliver(invitation_id)
    assert token not in response.text


async def test_ac1_the_response_carries_the_invitations_id_email_and_status(desk: Desk) -> None:
    response = await desk.invite(desk.partner, "cfo@ashford.example")
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "cfo@ashford.example"
    assert body["status"] == "pending"


async def test_ac1_the_email_is_delivered_with_the_link_and_only_a_hash_is_stored(
    desk: Desk,
) -> None:
    invitation_id = await desk.invited("cfo@ashford.example")
    token = await desk.deliver(invitation_id)
    mail = desk.mailbox.sent[-1]
    assert mail.to == "cfo@ashford.example"
    stored = await desk.seed.rows(
        "SELECT token_hash FROM invitation_tokens WHERE invitation_id = $1", invitation_id
    )
    assert [r["token_hash"] for r in stored] == [hashlib.sha256(token.encode()).hexdigest()]
    # The token is at rest nowhere else: not in the invitation, the outbox or the audit trail.
    for sql in (
        "SELECT count(*) FROM client_invitations c WHERE tenant_id = $1 AND c::text LIKE $2",
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND payload::text LIKE $2",
        "SELECT count(*) FROM audit_events a WHERE tenant_id = $1 AND a::text LIKE $2",
    ):
        assert await desk.seed.value(sql, desk.tenant_id, f"%{token}%") == 0


async def test_ac1_a_senior_cannot_invite(desk: Desk, seed: Seeder) -> None:
    senior = await seed.person(desk.tenant_id)
    await seed.member(desk.a, senior, "senior")
    response = await desk.invite(senior, "cfo@ashford.example")
    assert response.status_code in REFUSED
    assert (
        await seed.value(
            "SELECT count(*) FROM client_invitations WHERE engagement_id = $1",
            desk.a.engagement_id,
        )
        == 0
    )


# --- AC-2: a client admin invites contributors to their own engagement only ----------------------


async def test_ac2_a_client_admin_invites_a_contributor_to_their_engagement(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    response = await desk.invite(admin, "clerk@ashford.example", "client_contributor")
    assert response.status_code == 201, response.text
    invitation_id = uuid.UUID(cast(str, response.json()["invitation_id"]))
    assert await desk.status(invitation_id) == "pending"
    token = await desk.deliver(invitation_id)
    accepted, _ = await desk.accept("clerk@ashford.example", token)
    assert accepted.status_code == 200, accepted.text


async def test_ac2_a_client_admin_cannot_invite_another_admin(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    response = await desk.invite(admin, "boss@ashford.example", "client_admin")
    assert response.status_code in REFUSED
    assert (
        await desk.seed.value(
            "SELECT count(*) FROM client_invitations WHERE lower(email) = 'boss@ashford.example'"
        )
        == 0
    )


async def test_ac2_a_client_admin_cannot_invite_to_another_clients_engagement(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    response = await desk.invite(admin, "clerk@ashford.example", "client_contributor", desk.b)
    assert response.status_code in REFUSED
    assert (
        await desk.seed.value(
            "SELECT count(*) FROM client_invitations WHERE engagement_id = $1",
            desk.b.engagement_id,
        )
        == 0
    )


async def test_ac2_a_client_contributor_cannot_invite(desk: Desk) -> None:
    clerk = await desk.client("clerk@ashford.example", "client_contributor")
    response = await desk.invite(clerk, "other@ashford.example", "client_contributor")
    assert response.status_code in REFUSED


# --- AC-3: archived engagements and the daily limit ----------------------------------------------


async def test_ac3_an_archived_engagement_refuses_invitations(desk: Desk) -> None:
    await desk.seed.run(
        "UPDATE engagements SET status = 'archived' WHERE id = $1", desk.a.engagement_id
    )
    response = await desk.invite(desk.partner, "cfo@ashford.example")
    assert response.status_code != 201, response.text
    assert (
        await desk.seed.value(
            "SELECT count(*) FROM client_invitations WHERE engagement_id = $1",
            desk.a.engagement_id,
        )
        == 0
    )


async def test_ac3_an_archived_engagement_answers_409(desk: Desk) -> None:
    await desk.seed.run(
        "UPDATE engagements SET status = 'archived' WHERE id = $1", desk.a.engagement_id
    )
    response = await desk.invite(desk.partner, "cfo@ashford.example")
    assert response.status_code == 409, response.text
    assert response.json() == {"detail": "engagement_archived"}


async def test_ac3_the_fifty_first_invitation_of_the_day_is_refused_with_409(desk: Desk) -> None:
    for n in range(49):  # Q4: at most 50 per engagement per day
        await desk.seed.run(
            "INSERT INTO client_invitations (tenant_id, engagement_id, email, role, invited_by, "
            "expires_at) VALUES ($1, $2, $3, 'client_contributor', $4, now() + interval '7 days')",
            desk.tenant_id,
            desk.a.engagement_id,
            f"person{n}@ashford.example",
            desk.partner.user_id,
        )
    fiftieth = await desk.invite(desk.partner, "fiftieth@ashford.example")
    assert fiftieth.status_code == 201, fiftieth.text
    over = await desk.invite(desk.partner, "over@ashford.example")
    assert over.status_code == 409, over.text
    other = await desk.invite(desk.partner, "cfo@birchwood.example", site=desk.b)
    assert other.status_code == 201, other.text  # the limit is per engagement


# --- AC-4: accepting, once, in one unit of work --------------------------------------------------


async def test_ac4_accepting_makes_a_client_user_with_an_engagement_grant(desk: Desk) -> None:
    invitation_id = await desk.invited("cfo@ashford.example", "client_admin")
    response, subject = await desk.accept("cfo@ashford.example", await desk.deliver(invitation_id))
    assert response.status_code == 200, response.text
    assert response.json() == {
        "tenant_id": str(desk.tenant_id),
        "engagement_id": str(desk.a.engagement_id),
    }
    user_id = cast(
        uuid.UUID, await desk.seed.value("SELECT id FROM users WHERE idp_subject = $1", subject)
    )
    membership = await desk.seed.rows(
        "SELECT kind, firm_role, status FROM memberships WHERE tenant_id = $1 AND user_id = $2",
        desk.tenant_id,
        user_id,
    )
    assert [(m["kind"], m["firm_role"], m["status"]) for m in membership] == [
        ("client", None, "active")
    ]
    # C5 (F-03-T26, DEC-129): a client admin's engagement role is an `owner` grant on it.
    assert await desk.grants(user_id) == {("owner", "engagement", desk.a.engagement_id, "active")}
    assert await desk.status(invitation_id) == "accepted"
    accepted_by = await desk.seed.value(
        "SELECT accepted_by FROM client_invitations WHERE id = $1", invitation_id
    )
    assert accepted_by == user_id
    assert "client_invitation.accepted" in await desk.actions()


async def test_ac4_a_contributor_invitation_yields_a_contributor_grant(desk: Desk) -> None:
    clerk = await desk.client("clerk@ashford.example", "client_contributor")
    assert await desk.grants(clerk.user_id) == {
        ("contributor", "engagement", desk.a.engagement_id, "active")
    }


async def test_ac4_client_roles_are_grants_and_never_staff_team_rows(desk: Desk) -> None:
    # C5 spec drift: SPEC-015 §4 put client roles on `engagement_members`; since TASK-373 that
    # table holds staff only and the client's role is the grant.
    admin = await desk.client("admin@ashford.example")
    assert (
        await desk.seed.value(
            "SELECT count(*) FROM engagement_members WHERE user_id = $1", admin.user_id
        )
        == 0
    )
    team = await desk.net.call("GET", f"{desk.base(desk.a)}/team", desk.partner)
    assert str(admin.user_id) not in {m["user_id"] for m in team.json()}


async def test_ac4_an_invitation_for_one_client_never_yields_a_grant_on_another(
    desk: Desk,
) -> None:
    admin = await desk.client("admin@ashford.example")
    grants = await desk.grants(admin.user_id)
    assert {scope_id for _, _, scope_id, _ in grants} == {desk.a.engagement_id}
    assert desk.b.engagement_id not in {scope_id for _, _, scope_id, _ in grants}
    assert desk.b.client_id not in {scope_id for _, _, scope_id, _ in grants}
    mine = await desk.net.call("GET", desk.base(desk.a), admin)
    assert mine.status_code == 200, mine.text
    theirs = await desk.net.call("GET", desk.base(desk.b), admin)
    assert theirs.status_code == 404
    assert desk.b.marker not in theirs.text


async def test_ac4_an_existing_client_user_of_the_firm_reuses_their_membership(
    desk: Desk,
) -> None:
    admin = await desk.client("admin@ashford.example")
    second = await desk.invited("admin@ashford.example", "client_contributor", desk.b)
    response, _ = await desk.accept(
        "admin@ashford.example", await desk.deliver(second), subject=admin.subject
    )
    assert response.status_code == 200, response.text
    assert (
        await desk.seed.value(
            "SELECT count(*) FROM memberships WHERE tenant_id = $1 AND user_id = $2",
            desk.tenant_id,
            admin.user_id,
        )
        == 1
    )
    assert await desk.grants(admin.user_id) == {
        ("owner", "engagement", desk.a.engagement_id, "active"),
        ("contributor", "engagement", desk.b.engagement_id, "active"),
    }


async def test_ac4_a_link_works_once(desk: Desk) -> None:
    invitation_id = await desk.invited("cfo@ashford.example")
    token = await desk.deliver(invitation_id)
    first, subject = await desk.accept("cfo@ashford.example", token)
    assert first.status_code == 200, first.text
    again, _ = await desk.accept("cfo@ashford.example", token, subject=subject)
    assert again.status_code == 404
    assert again.json() == NOT_FOUND


# --- AC-5: one 404 for every failure, and a rate limit -------------------------------------------


async def test_ac5_every_invalid_acceptance_gets_the_same_404(desk: Desk) -> None:
    answers: list[tuple[int, object]] = []

    async def refused(email: str, token: str) -> None:
        response, _ = await desk.accept(email, token)
        answers.append((response.status_code, response.json()))

    # a wrong token
    await refused("cfo@ashford.example", uuid.uuid4().hex + uuid.uuid4().hex)
    # an expired invitation
    expired = await desk.invited("late@ashford.example")
    expired_token = await desk.deliver(expired)
    await desk.seed.run(
        "UPDATE client_invitations SET expires_at = $2 WHERE id = $1",
        expired,
        datetime.now(UTC) - timedelta(minutes=1),
    )
    await refused("late@ashford.example", expired_token)
    # a revoked invitation
    revoked = await desk.invited("gone@ashford.example")
    revoked_token = await desk.deliver(revoked)
    response = await desk.net.call(
        "POST", f"{desk.base(desk.a)}/client-invitations/{revoked}/revoke", desk.partner
    )
    assert response.status_code == 200, response.text
    await refused("gone@ashford.example", revoked_token)
    # a used token
    used = await desk.invited("used@ashford.example")
    used_token = await desk.deliver(used)
    ok, _ = await desk.accept("used@ashford.example", used_token)
    assert ok.status_code == 200, ok.text
    await refused("used@ashford.example", used_token)
    # another signed-in email
    other = await desk.invited("right@ashford.example")
    other_token = await desk.deliver(other)
    await refused("wrong@ashford.example", other_token)

    assert answers == [(404, NOT_FOUND)] * 5
    assert await desk.status(other) == "pending"  # a mismatch does not spend the link


async def test_ac5_ten_failed_tries_in_an_hour_lock_the_identity_out(desk: Desk) -> None:
    invitation_id = await desk.invited("cfo@ashford.example")
    token = await desk.deliver(invitation_id)
    subject = f"new-{uuid.uuid4().hex}"
    for _ in range(10):
        bad, _ = await desk.accept(
            "cfo@ashford.example", uuid.uuid4().hex + uuid.uuid4().hex, subject=subject
        )
        assert bad.status_code == 404
    locked, _ = await desk.accept("cfo@ashford.example", token, subject=subject)
    assert locked.status_code == 404
    assert locked.json() == NOT_FOUND
    assert await desk.status(invitation_id) == "pending"
    elsewhere, _ = await desk.accept("cfo@ashford.example", token)  # another identity
    assert elsewhere.status_code == 200, elsewhere.text


# --- AC-6: staff are never clients of their own firm ---------------------------------------------


async def test_ac6_a_staff_member_of_the_firm_cannot_accept_a_client_invitation(
    desk: Desk,
) -> None:
    staff_email = f"{desk.manager.subject}@example.test"  # the seed's address for the manager
    invitation_id = await desk.invited(staff_email)
    response, _ = await desk.accept(
        staff_email, await desk.deliver(invitation_id), subject=desk.manager.subject
    )
    assert response.status_code == 404
    assert await desk.status(invitation_id) == "pending"
    assert await desk.grants(desk.manager.user_id) == set()
    kinds = await desk.seed.rows(
        "SELECT kind FROM memberships WHERE tenant_id = $1 AND user_id = $2",
        desk.tenant_id,
        desk.manager.user_id,
    )
    assert [k["kind"] for k in kinds] == ["staff"]


# --- AC-7: a client is governed by the client rows, on their engagements only --------------------


async def test_ac7_a_client_reads_their_engagement_and_lists_only_it(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    listed = await desk.net.call("GET", "/v1/engagements", admin)
    assert listed.status_code == 200, listed.text
    assert [e["id"] for e in listed.json()] == [str(desk.a.engagement_id)]
    assert desk.b.marker not in listed.text


@pytest.mark.parametrize("path", ["/v1/firm/staff", "/v1/firm/settings"])
async def test_ac7_firm_level_routes_refuse_a_client(desk: Desk, path: str) -> None:
    admin = await desk.client("admin@ashford.example")
    response = await desk.net.call("GET", path, admin)
    assert response.status_code in REFUSED


async def test_ac7_staff_actions_on_their_own_engagement_are_refused(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    stranger = await desk.seed.person(desk.tenant_id)
    added = await desk.net.call(
        "POST",
        f"{desk.base(desk.a)}/team",
        admin,
        body={"user_id": str(stranger.user_id), "role": "staff"},
    )
    assert added.status_code in REFUSED
    candidates = await desk.net.call("GET", f"{desk.base(desk.a)}/team/candidates", admin)
    assert candidates.status_code in REFUSED


async def test_ac7_a_client_of_a_firm_cannot_reach_another_firms_engagement(
    desk: Desk, seed: Seeder
) -> None:
    admin = await desk.client("admin@ashford.example")
    elsewhere_firm = await seed.firm()
    owner = await seed.person(elsewhere_firm)
    elsewhere = await seed.site(elsewhere_firm, owner.user_id, "Elsewhere")
    response = await desk.net.call("GET", desk.base(elsewhere), admin, tenant=elsewhere_firm)
    assert response.status_code in (*REFUSED, 401)
    assert elsewhere.marker not in response.text


# --- AC-8: removal ends access on the next request -----------------------------------------------


async def test_ac8_a_client_removed_from_the_engagement_is_refused_next_request(
    desk: Desk,
) -> None:
    admin = await desk.client("admin@ashford.example")
    before = await desk.net.call("GET", desk.base(desk.a), admin)
    assert before.status_code == 200, before.text
    removed = await desk.net.call(
        "DELETE", f"{desk.base(desk.a)}/client-contacts/{admin.user_id}", desk.partner
    )
    assert removed.status_code == 200, removed.text
    after = await desk.net.call("GET", desk.base(desk.a), admin)
    assert after.status_code in REFUSED
    assert {status for *_, status in await desk.grants(admin.user_id)} == {"revoked"}


async def test_ac8_a_client_whose_membership_is_revoked_is_refused_next_request(
    desk: Desk,
) -> None:
    admin = await desk.client("admin@ashford.example")
    await desk.seed.revoke(admin)
    after = await desk.net.call("GET", desk.base(desk.a), admin)
    assert after.status_code in (*REFUSED, 401)
    assert desk.a.marker not in after.text


# --- AC-9: listing, revoking and removing --------------------------------------------------------


async def test_ac9_partners_managers_and_client_admins_see_members_and_pending_invitations(
    desk: Desk,
) -> None:
    admin = await desk.client("admin@ashford.example")
    pending = await desk.invited("clerk@ashford.example", "client_contributor")
    for who in (desk.partner, desk.manager, admin):
        response = await desk.net.call("GET", f"{desk.base(desk.a)}/client-contacts", who)
        assert response.status_code == 200, response.text
        listed = {(c["kind"], c["id"]) for c in response.json()}
        assert listed == {("member", str(admin.user_id)), ("invitation", str(pending))}


async def test_ac9_a_contributor_cannot_list_contacts(desk: Desk) -> None:
    clerk = await desk.client("clerk@ashford.example", "client_contributor")
    response = await desk.net.call("GET", f"{desk.base(desk.a)}/client-contacts", clerk)
    assert response.status_code in REFUSED


async def test_ac9_contacts_are_those_of_that_engagement_only(desk: Desk) -> None:
    await desk.client("admin@ashford.example")
    await desk.invited("cfo@birchwood.example", site=desk.b)
    response = await desk.net.call("GET", f"{desk.base(desk.b)}/client-contacts", desk.partner)
    assert response.status_code == 200, response.text
    assert [c["kind"] for c in response.json()] == ["invitation"]


async def test_ac9_revoking_a_pending_invitation_is_audited_and_drops_it(desk: Desk) -> None:
    invitation_id = await desk.invited("cfo@ashford.example")
    response = await desk.net.call(
        "POST", f"{desk.base(desk.a)}/client-invitations/{invitation_id}/revoke", desk.manager
    )
    assert response.status_code == 200, response.text
    assert await desk.status(invitation_id) == "revoked"
    assert "client_invitation.revoked" in await desk.actions()
    listed = await desk.net.call("GET", f"{desk.base(desk.a)}/client-contacts", desk.partner)
    assert listed.json() == []


async def test_ac9_removing_a_client_member_is_audited(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    response = await desk.net.call(
        "DELETE", f"{desk.base(desk.a)}/client-contacts/{admin.user_id}", desk.manager
    )
    assert response.status_code == 200, response.text
    assert "client_member.removed" in await desk.actions()
    listed = await desk.net.call("GET", f"{desk.base(desk.a)}/client-contacts", desk.partner)
    assert listed.json() == []


async def test_ac9_a_client_admin_removes_contributors_but_not_admins(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    other_admin = await desk.client("owner@ashford.example")
    clerk = await desk.client("clerk@ashford.example", "client_contributor")
    refused = await desk.net.call(
        "DELETE", f"{desk.base(desk.a)}/client-contacts/{other_admin.user_id}", admin
    )
    assert refused.status_code in REFUSED
    assert ("owner", "engagement", desk.a.engagement_id, "active") in await desk.grants(
        other_admin.user_id
    )
    removed = await desk.net.call(
        "DELETE", f"{desk.base(desk.a)}/client-contacts/{clerk.user_id}", admin
    )
    assert removed.status_code == 200, removed.text


async def test_ac9_a_client_admin_cannot_revoke_an_admin_invitation(desk: Desk) -> None:
    admin = await desk.client("admin@ashford.example")
    invitation_id = await desk.invited("owner@ashford.example", "client_admin")
    response = await desk.net.call(
        "POST", f"{desk.base(desk.a)}/client-invitations/{invitation_id}/revoke", admin
    )
    assert response.status_code in REFUSED
    assert await desk.status(invitation_id) == "pending"


# --- AC-10: resend -------------------------------------------------------------------------------


async def test_ac10_resend_issues_a_new_link_kills_the_old_and_sends_again(desk: Desk) -> None:
    invitation_id = await desk.invited("cfo@ashford.example")
    old = await desk.deliver(invitation_id)
    response = await desk.net.call(
        "POST", f"{desk.base(desk.a)}/client-invitations/{invitation_id}/resend", desk.partner
    )
    assert response.status_code == 200, response.text
    assert "client_invitation.resent" in await desk.actions()
    assert len(await desk.events(invitation_id)) == 2  # a second email is asked for
    stale, _ = await desk.accept("cfo@ashford.example", old)
    assert stale.status_code == 404  # the old link stopped working at the resend
    new = await desk.deliver(invitation_id)
    assert new != old
    assert len(desk.mailbox.sent) == 2
    accepted, _ = await desk.accept("cfo@ashford.example", new)
    assert accepted.status_code == 200, accepted.text
