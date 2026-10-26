"""R-01-T13 (TASK-1275; DEC-387, DEC-388): the third-party room and invitations on delegation,
against Postgres through `create_app()`.

Acceptance: "Marcus delegating the bridge letter sends Sam Ortiz one invitation in Brightwater
Hale's name and Sam's room returns exactly the 9 Keystone items." R-01 Stories 6.1 and 6.2.

Northwind's PY2025 PBC list in small: 24 published requests, 9 of them delegated to Keystone
Retirement Services (six recordkeeper reports and three SOC 1 and fee items), the rest the
client's. Marcus Delaney (engagement partner) delegates through CLI-04's contact invitation, the
one invitation a person gets (DEC-388); Sam accepts through the portal's own routes and reads the
room with the portal bearer on the firm's host.

INV-4 in every read: the room holds exactly the delegated requests; every other request, the
binder picker and POR-04 answer 404 to Sam; the upload and comment routes allow the delegated
request only, and Sam reads only its shared comments. ADR P-12: a tax engagement's request is
never delegated without the client's `third_party_disclosure` consent (none exists until C19).
"""

from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.flags import forget_flags
from abacus.kernel.uow import OutboxEvent
from abacus.modules.communications.api import SUBSCRIPTIONS, configure_transport
from abacus.modules.communications.templates import import_platform_version
from abacus.modules.evidence.uploads import authorise_upload
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.portal.notices import on_evidence_uploaded
from abacus.modules.requests.client_responses import list_done
from abacus.modules.requests.client_responses import responses as client_responses
from abacus.modules.requests.comments import post_comment, thread
from abacus.modules.requests.lifecycle import ConsentRequired, delegate_item
from abacus.modules.requests.service import request_items_for

from . import test_p07t26_contacts_g2_independent as t26
from .support import Net, Person, Seeder

pytestmark = pytest.mark.asyncio

# P-07-T26's seeding and calls, shared rather than copied (as P-07-T25's suite does).
_t_world = t26._world  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_flag = t26._flag  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_contact = t26._contact  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_json = t26._json  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_invite = t26._invite  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_token = t26._token  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_portal_session = t26._portal_session  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_accept = t26._accept  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_client_ctx = t26._client_ctx  # pyright: ignore[reportPrivateUsage] -- the shared seeding
_t_outbox = t26._outbox  # pyright: ignore[reportPrivateUsage] -- the shared seeding

Json = dict[str, object]
RECORDKEEPER = "Trust / Recordkeeper Reports"
SOC1 = "Form 5500 & SOC 1"
BRIDGE = "Bridge letter — Oct 1 to Dec 31, 2025"
KEYSTONE_TITLES = (
    (RECORDKEEPER, "Schedule of account balances — every participant, 12/31/2025"),
    (RECORDKEEPER, "Annual participant loan roll-forward — 2025"),
    (RECORDKEEPER, "BrokerWindow self-directed brokerage asset detail — 12/31/2025"),
    (RECORDKEEPER, "Withdrawals and distributions report — 2025"),
    (RECORDKEEPER, "Contribution remittance report — deposit date for each 2025 payroll"),
    (RECORDKEEPER, "Certified trust report — 12/31/2025"),
    (SOC1, "SOC 1 Type 2 report — Oct 1, 2024 to Sep 30, 2025"),
    (SOC1, BRIDGE),
    (SOC1, "ERISA 408(b)(2) fee disclosure"),
)
CLIENT_CATEGORY = "Census & Payroll"
FLAGS = ("portal.third_party_room", "binders.engine", "evidence.withdrawal")
TEMPLATE_KEY = "portal.invitation"


@dataclass(frozen=True)
class Room:
    base: t26.World
    marcus: Person
    binder: uuid.UUID
    delegated: tuple[uuid.UUID, ...]  # the 9 Keystone requests, in KEYSTONE_TITLES order
    client_items: tuple[uuid.UUID, ...]  # the other 15
    sam: uuid.UUID  # Sam Ortiz's contact
    sam_email: str

    @property
    def seed(self) -> Seeder:
        return self.base.seed

    @property
    def bridge(self) -> uuid.UUID:
        return self.delegated[7]


async def _category(world: t26.World, binder: uuid.UUID, name: str, position: int) -> uuid.UUID:
    return cast(
        uuid.UUID,
        await world.seed.value(
            "INSERT INTO request_categories (tenant_id, request_list_id, name, position) "
            "VALUES ($1, $2, $3, $4) RETURNING id",
            world.tenant,
            binder,
            name,
            position,
        ),
    )


async def _request(
    world: t26.World, item: uuid.UUID, title: str, category: uuid.UUID, owner: Person
) -> None:
    await world.seed.run(
        "UPDATE request_items SET title = $2, description = $2, category_id = $3, "
        "client_visible = true, firm_owner_user_id = $4 WHERE id = $1",
        item,
        title,
        category,
        owner.user_id,
    )
    await world.seed.run(
        "UPDATE request_items SET status = 'requested', requested_at = now() WHERE id = $1", item
    )


async def _room_world(net: Net) -> Room:
    world = await _t_world(net)
    for flag in FLAGS:
        await _t_flag(world.seed, world.tenant, flag)
    marcus = await world.seed.person(world.tenant)
    await world.seed.member(world.site, marcus, "engagement_partner")
    await world.seed.run(
        "UPDATE users SET display_name = 'Marcus Delaney' WHERE id = $1", marcus.user_id
    )
    binder = cast(
        uuid.UUID,
        await world.seed.value(
            "SELECT request_list_id FROM request_items WHERE id = $1", world.site.item_id
        ),
    )
    await world.seed.run(
        "UPDATE request_lists SET name = 'PY2025 Audit requests', status = 'published', "
        "published_at = now(), published_by = $2 WHERE id = $1",
        binder,
        world.grace.user_id,
    )
    cats = {
        name: await _category(world, binder, name, pos)
        for pos, name in enumerate((CLIENT_CATEGORY, RECORDKEEPER, SOC1))
    }
    items = list(world.items)
    while len(items) < 24:
        items.append(await world.seed.item(world.site, f"Request {len(items) + 1}"))
    delegated = tuple(items[:9])
    for item, (category, title) in zip(delegated, KEYSTONE_TITLES, strict=True):
        await _request(world, item, title, cats[category], marcus)
    for n, item in enumerate(items[9:]):
        await _request(world, item, f"Census request {n + 1}", cats[CLIENT_CATEGORY], marcus)
    sam, email = await _t_contact(
        world.seed, world.site, "Sam Ortiz", org="Keystone Retirement Services"
    )
    return Room(world, marcus, binder, delegated, tuple(items[9:]), sam, email)


def _keystone_grants(room: Room) -> list[Json]:
    return [
        {
            "role": "third_party",
            "scope_kind": "request_item",
            "scope_id": str(room.delegated[0]),
            "request_item_ids": [str(i) for i in room.delegated],
        }
    ]


async def _invite(room: Room) -> Json:
    return _t_json(
        await _t_invite(room.base, room.sam, _keystone_grants(room), who=room.marcus),
        201,
    )


async def _signed_in(room: Room) -> tuple[str, uuid.UUID]:
    """Sam invited by Marcus and accepted: the portal bearer and Sam's user."""
    invitation = await _invite(room)
    token = await _t_token(room.base, cast(str, invitation["invitation_id"]))
    access = await _t_portal_session(room.base, room.sam_email, token)
    accepted = await _t_accept(room.base, access, token)
    assert accepted.status_code == 200, accepted.text
    user = cast(
        uuid.UUID, await room.seed.value("SELECT user_id FROM contacts WHERE id = $1", room.sam)
    )
    return access, user


def _portal(room: Room, access: str) -> dict[str, str]:
    return {"host": room.base.host, "authorization": f"Bearer {access}"}


async def _get(room: Room, access: str, path: str) -> httpx.Response:
    return await room.base.net.http.get(path, headers=_portal(room, access))


def _staff(who: Person) -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


def _sam(room: Room, user: uuid.UUID) -> AuthContext:
    return _t_client_ctx(room.base, user)


def _row_ids(body: Json) -> list[str]:
    return [
        cast(str, r["id"])
        for b in cast(list[Json], body["bands"])
        for r in cast(list[Json], b["rows"])
    ]


async def _upload(room: Room, item: uuid.UUID, name: str, by: uuid.UUID) -> uuid.UUID:
    """A client upload stored on the request as the upload pipeline stores one (detached key
    left out: the room reads names, dates and decisions only)."""
    eid = room.base.site.engagement_id
    evidence = await room.seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, $3, 'human', $4) RETURNING id",
        room.base.tenant,
        eid,
        name,
        str(by),
    )
    fingerprint = hashlib.sha256(uuid.uuid4().bytes).hexdigest()
    version = cast(
        uuid.UUID,
        await room.seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, $4, $5, 'v1', 2048, 'application/pdf', "
            "'client_upload', 'uploaded') RETURNING id",
            room.base.tenant,
            eid,
            evidence,
            fingerprint,
            f"tenants/{room.base.tenant}/sha256/{fingerprint}",
        ),
    )
    await room.seed.run(
        "INSERT INTO fulfilments (tenant_id, engagement_id, request_item_id, "
        "evidence_version_id, created_by_kind, created_by_id) "
        "VALUES ($1, $2, $3, $4, 'human', $5)",
        room.base.tenant,
        eid,
        item,
        version,
        str(by),
    )
    await room.seed.run("UPDATE request_items SET status = 'uploaded' WHERE id = $1", item)
    return version


@pytest.fixture
async def room(net: Net) -> Room:
    return await _room_world(net)


# ================================================================================================
# The acceptance line
# ================================================================================================


async def test_ac_marcus_delegating_sends_sam_one_invitation_and_the_room_holds_exactly_9(
    room: Room,
) -> None:
    await import_platform_version(
        "r01t13",
        TEMPLATE_KEY,
        "en-US",
        "{{firm_name}} invites you to share documents",
        "Hello {{recipient_first_name}},\n\n{{firm_name}} has asked you for some documents."
        "\n\nOpen your invitation: {{app_link}}\n",
        ["firm_name", "recipient_first_name", "app_link"],
    )
    sent: list[Json] = []

    class Box:
        def send(self, **message: object) -> None:
            sent.append(dict(message))

    configure_transport(Box())
    try:
        await _invite(room)
        for event_type in ("client_invitation.issued", "contact.invited"):
            handler = SUBSCRIPTIONS.get(event_type)
            for payload in await _t_outbox(room.base, event_type):
                if handler is not None:
                    await handler(OutboxEvent(uuid.uuid4(), room.base.tenant, event_type, payload))
    finally:
        configure_transport(None)
    # One invitation, one email, in the firm's name (DEC-388; OQ-9).
    invitations = await room.seed.rows(
        "SELECT id FROM client_invitations WHERE tenant_id = $1 AND contact_id = $2",
        room.base.tenant,
        room.sam,
    )
    assert len(invitations) == 1
    assert len(sent) == 1
    mail = sent[0]
    text = f"{mail['subject']}\n{mail['body']}"
    assert mail["sender_name"] == room.base.firm_name and room.base.firm_name in text
    assert "Accrued" not in text and "abacus" not in text.lower()
    assert len(re.findall(r"https?://", text)) == 1
    # The delegations are recorded in the invitation's unit of work.
    delegations = await room.seed.rows(
        "SELECT request_item_id FROM request_delegations WHERE tenant_id = $1 AND contact_id = $2 "
        "AND revoked_at IS NULL",
        room.base.tenant,
        room.sam,
    )
    assert sorted(r["request_item_id"] for r in delegations) == sorted(room.delegated)

    token = await _t_token(room.base, str(invitations[0]["id"]))
    access = await _t_portal_session(room.base, room.sam_email, token)
    assert (await _t_accept(room.base, access, token)).status_code == 200
    response = await _get(room, access, "/v1/portal/room")
    assert response.status_code == 200, response.text
    body = cast(Json, response.json())
    assert sorted(_row_ids(body)) == sorted(str(i) for i in room.delegated)
    assert (body["total"], body["uploaded_count"], body["complete"]) == (9, 0, False)
    assert body["organisation_name"] == "Keystone Retirement Services"
    assert body["firm_name"] == room.base.firm_name
    bands = cast(list[Json], body["bands"])
    assert [(b["label"], b["total"]) for b in bands] == [(RECORDKEEPER, 6), (SOC1, 3)]
    rows = {cast(str, r["id"]): r for b in bands for r in cast(list[Json], b["rows"])}
    bridge = rows[str(room.bridge)]
    assert (bridge["title"], bridge["state"], bridge["disc"]) == (BRIDGE, "due", "ring")
    assert bridge["allowed_actions"] == ["upload", "comment"]
    # Nothing of the other 15 requests, nor of the client, is in the answer.
    for other in room.client_items:
        assert str(other) not in response.text
    assert "Census request" not in response.text


async def test_ac_a_later_delegation_through_p06_adds_the_request_and_no_second_invitation(
    room: Room,
) -> None:
    access, _ = await _signed_in(room)
    tenth = room.client_items[0]
    delegated = await room.base.net.call(
        "POST",
        f"/v1/engagements/{room.base.site.engagement_id}/request-items/{tenth}/delegate",
        room.marcus,
        body={"contact_id": str(room.sam)},
    )
    assert delegated.status_code == 201, delegated.text
    count = await room.seed.value(
        "SELECT count(*) FROM client_invitations WHERE tenant_id = $1 AND contact_id = $2",
        room.base.tenant,
        room.sam,
    )
    assert count == 1  # OQ-9: one invitation per person
    body = cast(Json, (await _get(room, access, "/v1/portal/room")).json())
    assert body["total"] == 10 and str(tenth) in _row_ids(body)


# ================================================================================================
# INV-4: Sam reaches the delegated requests and nothing else
# ================================================================================================


async def test_inv4_every_other_portal_read_answers_404_to_sam(room: Room) -> None:
    access, _ = await _signed_in(room)
    assert (await _get(room, access, "/v1/portal/binders")).status_code == 404
    assert (await _get(room, access, f"/v1/portal/binders/{room.binder}")).status_code == 404
    for item in (room.bridge, room.client_items[0]):
        found = await _get(room, access, f"/v1/portal/request-items/{item}")
        assert found.status_code == 404


async def test_inv4_upload_and_comments_reach_the_delegated_request_only(room: Room) -> None:
    _, user = await _signed_in(room)
    sam = _sam(room, user)
    eid = room.base.site.engagement_id
    await authorise_upload(sam, eid, room.bridge)
    for other in (room.client_items[0], room.client_items[5]):
        with pytest.raises(Forbidden):
            await authorise_upload(sam, eid, other)
        with pytest.raises(Forbidden):
            await thread(sam, eid, other, None)
    # The firm's internal note on the bridge letter never reaches Sam; shared ones do.
    marcus = _staff(room.marcus)
    await post_comment(marcus, eid, room.bridge, None, text="Check the period first.")
    posted = await post_comment(sam, eid, room.bridge, None, text="I'll upload it by Sep 22.")
    assert posted.visibility == "shared"
    seen = await thread(sam, eid, room.bridge, None)
    assert [c.text for c in seen] == ["I'll upload it by Sep 22."]


async def test_inv4_no_list_of_the_engagement_answers_to_sam(room: Room) -> None:
    """`delegated_only` reaches no list: the engagement's request list, the client's responses
    and who marked the list done are refused to a third party (they would name the client)."""
    _, user = await _signed_in(room)
    sam = _sam(room, user)
    eid = room.base.site.engagement_id
    for read in (request_items_for, client_responses, list_done):
        with pytest.raises(Forbidden):
            await read(sam, eid)


async def test_inv4_a_revoked_delegation_leaves_the_room(room: Room) -> None:
    access, _ = await _signed_in(room)
    await room.seed.run(
        "UPDATE request_delegations SET revoked_at = now() WHERE request_item_id = $1",
        room.bridge,
    )
    body = cast(Json, (await _get(room, access, "/v1/portal/room")).json())
    assert body["total"] == 8 and str(room.bridge) not in _row_ids(body)


async def test_inv4_a_full_client_person_and_the_flag_off_have_no_room(room: Room) -> None:
    dana = await room.seed.client_contact(room.base.site)
    headers = room.base.net.headers(dana)
    response = await room.base.net.http.get("/v1/portal/room", headers=headers)
    assert response.status_code == 404
    access, _ = await _signed_in(room)
    await room.seed.run(
        "UPDATE feature_flag_states SET value = 'false' WHERE tenant_id = $1 AND flag = $2",
        room.base.tenant,
        "portal.third_party_room",
    )
    forget_flags()
    assert (await _get(room, access, "/v1/portal/room")).status_code == 404


# ================================================================================================
# The rows: in review, uploaded, complete; suggest; the owner told
# ================================================================================================


async def test_story62_sams_upload_reads_in_review_and_counts_5_of_9(room: Room) -> None:
    access, user = await _signed_in(room)
    for item in room.delegated[:4]:
        await _upload(room, item, "Keystone_report.pdf", room.marcus.user_id)
    await _upload(room, room.bridge, "Keystone_Bridge_Letter_Q4_2025.pdf", user)
    body = cast(Json, (await _get(room, access, "/v1/portal/room")).json())
    assert (body["uploaded_count"], body["total"]) == (5, 9)
    rows = {
        cast(str, r["id"]): r
        for b in cast(list[Json], body["bands"])
        for r in cast(list[Json], b["rows"])
    }
    bridge = rows[str(room.bridge)]
    assert (bridge["state"], bridge["disc"]) == ("in_review", "done")
    [file] = cast(list[Json], bridge["files"])
    assert cast(Json, file["receipt"])["kind"] == "uploaded"
    assert cast(Json, file["receipt"]).get("by_first_name") is None
    first = rows[str(room.delegated[0])]
    assert (first["state"], first["disc"]) == ("uploaded", "done")


async def test_story62_every_request_received_completes_the_room(room: Room) -> None:
    access, _ = await _signed_in(room)
    for item in room.delegated:
        await _upload(room, item, "Keystone_report.pdf", room.marcus.user_id)
        await room.seed.run("UPDATE request_items SET status = 'received' WHERE id = $1", item)
    body = cast(Json, (await _get(room, access, "/v1/portal/room")).json())
    assert (body["uploaded_count"], body["total"], body["complete"]) == (9, 9, True)


async def test_story62_suggest_preselects_among_the_delegated_requests_only(room: Room) -> None:
    access, _ = await _signed_in(room)
    response = await room.base.net.http.post(
        "/v1/portal/room/suggest",
        json={"file_names": ["Keystone_Bridge_Letter_Oct-Dec.pdf", "Census request 3.xlsx"]},
        headers=_portal(room, access),
    )
    assert response.status_code == 200, response.text
    suggestions = cast(list[Json], response.json()["suggestions"])
    assert suggestions[0]["request_item_id"] == str(room.bridge)
    assert suggestions[1].get("request_item_id") is None  # a client's request is never offered


async def test_inv5_sams_upload_tells_the_request_owner(room: Room) -> None:
    _, user = await _signed_in(room)
    version = await _upload(room, room.bridge, "Keystone_Bridge_Letter.pdf", user)
    payload: Json = {
        "engagement_id": str(room.base.site.engagement_id),
        "request_item_id": str(room.bridge),
        "evidence_version_id": str(version),
        "uploaded_by": str(user),
    }
    await on_evidence_uploaded(
        OutboxEvent(uuid.uuid4(), room.base.tenant, "evidence.uploaded", payload)
    )
    told = await _t_outbox(room.base, "third_party.uploaded")
    assert len(told) == 1 and told[0]["owner_user_id"] == str(room.marcus.user_id)
    # A firm upload to a request nobody delegated makes no notice.
    other = await _upload(room, room.client_items[0], "Census.pdf", room.marcus.user_id)
    await on_evidence_uploaded(
        OutboxEvent(
            uuid.uuid4(),
            room.base.tenant,
            "evidence.uploaded",
            payload
            | {
                "request_item_id": str(room.client_items[0]),
                "evidence_version_id": str(other),
                "uploaded_by": str(room.marcus.user_id),
            },
        )
    )
    assert len(await _t_outbox(room.base, "third_party.uploaded")) == 1


# ================================================================================================
# ADR P-12: §7216 fails closed
# ================================================================================================


async def _tax_return(room: Room) -> None:
    site = room.base.site
    await room.seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, created_by) VALUES ($1, $2, $3, $4, 'tax_return', '2025 Form 5500-EZ', $5)",
        site.tenant_id,
        site.engagement_id,
        site.client_id,
        site.entity_id,
        room.marcus.user_id,
    )


async def test_adr_p12_a_tax_engagement_is_never_delegated_without_the_consent(
    room: Room,
) -> None:
    await _tax_return(room)
    refused = await _t_invite(room.base, room.sam, _keystone_grants(room), who=room.marcus)
    assert refused.status_code == 409, refused.text
    assert refused.json()["detail"] == "consent_required"
    assert (
        await room.seed.rows(
            "SELECT 1 FROM client_invitations WHERE tenant_id = $1 AND contact_id = $2",
            room.base.tenant,
            room.sam,
        )
        == []
    )
    assert (
        await room.seed.rows("SELECT 1 FROM request_delegations WHERE contact_id = $1", room.sam)
        == []
    )
    with pytest.raises(ConsentRequired):
        await delegate_item(
            _staff(room.marcus), room.base.site.engagement_id, room.bridge, room.sam
        )


async def test_adr_p12_the_room_leaves_out_a_tax_engagement_delegated_before_its_return(
    room: Room,
) -> None:
    access, _ = await _signed_in(room)
    await _tax_return(room)
    assert (await _get(room, access, "/v1/portal/room")).status_code == 404
