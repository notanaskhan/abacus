# ac-test-author: notanaskhan (G-01-T09; ADR-078's independent suite is G-01-T15)
"""G-01-T09 walls v2 over HTTP against Postgres (G-01 AC8.1 to AC8.7; SPEC-002 amended; DEC-43,
DEC-73, INV-3, INV-5): Grace Holloway (firm admin) walls Lena Park from Ashford with a reason and
Margaret Okonkwo as the named approver; the wall applies at once; the preview names blockers and
the assignments it would end; Neil Ashcroft, Ashford's relationship partner, can't be walled
from it; only Margaret approves, once, with fresh MFA; the wall's log reads from the audit
trail; the `wall.created` consumer ends Lena's assignments on Ashford as the system on behalf of
Grace; Margaret is notified and Grace told of the approval.

Expectations come from G-01 section 3.8, not from the implementation."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import cast

import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent
from abacus.modules.engagements.conditions import functions_on
from abacus.modules.identity.api import end_assignments_for_wall
from abacus.modules.notifications.api import SUBSCRIPTIONS as NOTIFY
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Seeder
from .walls_support import FORBIDDEN, NOT_FOUND, Json, Net, Site

FLAG = "firm_settings.v2"


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@dataclass(frozen=True)
class Firm:
    net: Net
    tenant_id: uuid.UUID
    grace: Person
    margaret: Person
    daniel: Person
    neil: Person
    lena: Person
    ashford: Site
    granite: Site

    @property
    def seed(self) -> Seeder:
        return self.net.seed

    async def call(
        self, method: str, path: str, who: Person, body: Json | None = None, **kw: object
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body, **kw)  # type: ignore[arg-type]  # mfa options

    async def wall_lena(self, approver: Person | None = None) -> httpx.Response:
        return await self.call(
            "POST",
            "/v1/walls",
            self.grace,
            {
                "user_id": str(self.lena.user_id),
                "client_id": str(self.ashford.client_id),
                "reason_code": "personal_relationship",
                "reason_text": "Family member employed at Ashford",
                "approver_user_id": str((approver or self.margaret).user_id),
            },
        )

    async def outbox(self, event_type: str) -> list[OutboxEvent]:
        rows = await self.seed.rows(
            "SELECT id, tenant_id, event_type, payload FROM outbox "
            "WHERE tenant_id = $1 AND event_type = $2 ORDER BY occurred_at, id",
            self.tenant_id,
            event_type,
        )
        import json

        return [
            OutboxEvent(
                r["id"],
                r["tenant_id"],
                r["event_type"],
                cast(dict[str, object], json.loads(r["payload"]))
                if isinstance(r["payload"], str)
                else cast(dict[str, object], r["payload"]),
            )
            for r in rows
        ]

    async def audit(self, action: str) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT actor_kind, actor_id, on_behalf_of_user_id, target_type, "
            "target_id::text AS target_id, after_ref::text AS after_ref FROM audit_events "
            "WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant_id,
            action,
        )
        return [dict(r) for r in rows]


async def _level(net: Net, tenant: uuid.UUID, who: Person, level: str) -> None:
    await net.seed.run(
        "UPDATE memberships SET level = $3 WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        who.user_id,
        level,
    )


@pytest.fixture
async def firm(net: Net, seed: Seeder) -> Firm:
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'G-01-T09')",
        tenant,
        FLAG,
    )
    grace = await net.person(tenant, "firm_admin")
    margaret = await net.person(tenant)
    daniel = await net.person(tenant)
    neil = await net.person(tenant)
    for partner in (margaret, daniel, neil):
        await _level(net, tenant, partner, "partner")
    lena = await net.person(tenant)
    await _level(net, tenant, lena, "seasonal")
    ashford = await net.site(tenant, grace.user_id)
    granite = await net.site(tenant, grace.user_id)
    await seed.run(
        "UPDATE clients SET relationship_partner_id = $2 WHERE id = $1",
        ashford.client_id,
        neil.user_id,
    )
    return Firm(net, tenant, grace, margaret, daniel, neil, lena, ashford, granite)


def _body(response: httpx.Response) -> Json:
    return cast(Json, response.json())


# --- AC8.1: create, active at once ---------------------------------------------------------------


async def test_ac8_1_grace_walls_lena_from_ashford_with_a_reason_and_a_named_partner(
    firm: Firm,
) -> None:
    await firm.seed.member(firm.ashford.engagement_id, firm.lena, "staff")
    before = await firm.call("GET", f"/v1/engagements/{firm.ashford.engagement_id}", firm.lena)
    assert before.status_code == 200
    response = await firm.wall_lena()
    assert response.status_code == 201, response.text
    wall = _body(response)
    assert wall["status"] == "active"
    assert wall["approval_status"] == "awaiting"
    assert wall["reason_code"] == "personal_relationship"
    assert wall["reason_text"] == "Family member employed at Ashford"
    assert wall["approver_user_id"] == str(firm.margaret.user_id)
    assert wall["approved_at"] is None
    after = await firm.call("GET", f"/v1/engagements/{firm.ashford.engagement_id}", firm.lena)
    never = await firm.call("GET", f"/v1/engagements/{uuid.uuid4()}", firm.lena)
    assert (after.status_code, after.json()) == (404, NOT_FOUND)
    assert (after.status_code, after.text) == (never.status_code, never.text)
    [event] = await firm.audit("wall.created")
    assert str(firm.margaret.user_id) in str(event["after_ref"])
    # The wall tells Lena's sessions and caches her access changed.
    changed = [e.payload.get("user_id") for e in await firm.outbox("access.changed")]
    assert str(firm.lena.user_id) in changed


async def test_ac8_1_a_partner_may_wall_too_and_staff_may_not(firm: Firm) -> None:
    body: Json = {"user_id": str(firm.lena.user_id), "client_id": str(firm.granite.client_id)}
    assert (await firm.call("POST", "/v1/walls", firm.daniel, body)).status_code == 201
    other = await firm.net.person(firm.tenant_id)
    refused = await firm.call(
        "POST",
        "/v1/walls",
        other,
        {"user_id": str(firm.lena.user_id), "client_id": str(firm.ashford.client_id)},
    )
    assert (refused.status_code, refused.json()) == (403, FORBIDDEN)


async def test_ac8_1_the_preview_counts_the_assignments_the_wall_ends(firm: Firm) -> None:
    await firm.seed.member(firm.ashford.engagement_id, firm.lena, "staff")
    await _assign(firm, firm.ashford, firm.lena, "preparer")
    path = f"/v1/walls/preview?user_id={firm.lena.user_id}&client_id={firm.ashford.client_id}"
    response = await firm.call("GET", path, firm.grace)
    assert response.status_code == 200, response.text
    assert _body(response) == {"blockers": [], "assignments_ended": 2}


async def test_ac8_1_an_unknown_client_or_person_previews_as_not_found(firm: Firm) -> None:
    for user, client in (
        (firm.lena.user_id, uuid.uuid4()),
        (uuid.uuid4(), firm.ashford.client_id),
    ):
        path = f"/v1/walls/preview?user_id={user}&client_id={client}"
        response = await firm.call("GET", path, firm.grace)
        assert (response.status_code, response.json()) == (404, NOT_FOUND)


async def test_ac8_1_a_walled_creator_learns_nothing_of_the_client(firm: Firm) -> None:
    """DEC-43: Grace, walled from Ashford herself, previews and walls it as if unknown."""
    await firm.net.wall(firm.grace, firm.grace.user_id, firm.ashford.client_id)
    path = f"/v1/walls/preview?user_id={firm.lena.user_id}&client_id={firm.ashford.client_id}"
    response = await firm.call("GET", path, firm.grace)
    assert (response.status_code, response.json()) == (404, NOT_FOUND)
    assert (await firm.wall_lena()).status_code == 404


# --- AC8.2: only the named partner approves, once, with fresh MFA --------------------------------


async def test_ac8_2_only_margaret_approves_and_only_once(firm: Firm) -> None:
    wall_id = _body(await firm.wall_lena())["id"]
    path = f"/v1/walls/{wall_id}/approve"
    grace = await firm.call("POST", path, firm.grace)
    assert (grace.status_code, grace.json()) == (403, FORBIDDEN)  # INV-5: not for her
    daniel = await firm.call("POST", path, firm.daniel)
    assert (daniel.status_code, daniel.json()) == (403, {"detail": "not_named_approver"})
    stale = await firm.call("POST", path, firm.margaret, mfa_age=timedelta(minutes=20))
    assert stale.status_code == 403
    approved = await firm.call("POST", path, firm.margaret)
    assert approved.status_code == 200, approved.text
    body = _body(approved)
    assert body["approval_status"] == "approved"
    assert body["approved_at"] is not None
    again = await firm.call("POST", path, firm.margaret)
    assert (again.status_code, again.json()) == (409, {"detail": "already_approved"})
    [event] = await firm.audit("wall.approved")
    assert event["actor_id"] == str(firm.margaret.user_id)


async def test_ac8_2_the_approver_must_be_a_partner_other_than_the_walled_person(
    firm: Firm,
) -> None:
    other = await firm.net.person(firm.tenant_id)
    refused = await firm.wall_lena(approver=other)
    assert (refused.status_code, refused.json()["detail"]) == (422, "approver_not_partner")
    self_approved = await firm.call(
        "POST",
        "/v1/walls",
        firm.grace,
        {
            "user_id": str(firm.daniel.user_id),
            "client_id": str(firm.granite.client_id),
            "approver_user_id": str(firm.daniel.user_id),
        },
    )
    assert self_approved.status_code == 422
    assert await firm.net.wall_rows(firm.tenant_id) == 0


async def test_ac8_2_the_approval_is_forward_only_in_the_database(firm: Firm) -> None:
    wall_id = uuid.UUID(cast(str, _body(await firm.wall_lena())["id"]))
    assert (
        await firm.call("POST", f"/v1/walls/{wall_id}/approve", firm.margaret)
    ).status_code == 200
    with pytest.raises(Exception, match=r"approved once|immutable"):
        await firm.seed.run("UPDATE ethical_walls SET approved_at = now() WHERE id = $1", wall_id)
    with pytest.raises(Exception, match="immutable"):
        await firm.seed.run(
            "UPDATE ethical_walls SET approver_user_id = $2 WHERE id = $1",
            wall_id,
            firm.daniel.user_id,
        )


async def test_ac8_2_a_lifted_wall_cannot_be_approved(firm: Firm) -> None:
    wall_id = _body(await firm.wall_lena())["id"]
    assert (await firm.call("POST", f"/v1/walls/{wall_id}/remove", firm.daniel)).status_code == 200
    late = await firm.call("POST", f"/v1/walls/{wall_id}/approve", firm.margaret)
    assert (late.status_code, late.json()) == (404, NOT_FOUND)


# --- AC8.3: the relationship partner, and a duplicate --------------------------------------------


async def test_ac8_3_neil_ashcroft_leads_ashford_and_cannot_be_walled_from_it(firm: Firm) -> None:
    path = f"/v1/walls/preview?user_id={firm.neil.user_id}&client_id={firm.ashford.client_id}"
    preview = await firm.call("GET", path, firm.grace)
    assert _body(preview)["blockers"] == ["relationship_partner"]
    refused = await firm.call(
        "POST",
        "/v1/walls",
        firm.grace,
        {"user_id": str(firm.neil.user_id), "client_id": str(firm.ashford.client_id)},
    )
    assert (refused.status_code, refused.json()["detail"]) == (409, "relationship_partner")
    assert await firm.net.wall_rows(firm.tenant_id) == 0


async def test_ac8_3_a_second_active_wall_is_a_blocker_and_409(firm: Firm) -> None:
    assert (await firm.wall_lena()).status_code == 201
    path = f"/v1/walls/preview?user_id={firm.lena.user_id}&client_id={firm.ashford.client_id}"
    assert _body(await firm.call("GET", path, firm.grace))["blockers"] == ["wall_exists"]
    again = await firm.wall_lena()
    assert (again.status_code, again.json()) == (409, {"detail": "wall_exists"})


# --- AC8.4: the lift -----------------------------------------------------------------------------


async def test_ac8_4_a_partner_lifts_with_a_reason_and_the_row_keeps_its_history(
    firm: Firm,
) -> None:
    wall_id = _body(await firm.wall_lena())["id"]
    admin = await firm.call("POST", f"/v1/walls/{wall_id}/remove", firm.grace, {"reason": "x"})
    assert admin.status_code == 403
    lifted = await firm.call(
        "POST", f"/v1/walls/{wall_id}/remove", firm.daniel, {"reason": "Relative left Ashford"}
    )
    assert lifted.status_code == 200, lifted.text
    assert _body(lifted)["removed_reason"] == "Relative left Ashford"
    assert _body(lifted)["reason_code"] == "personal_relationship"
    changed = [e.payload.get("user_id") for e in await firm.outbox("access.changed")]
    assert changed.count(str(firm.lena.user_id)) == 2  # created, then lifted


# --- AC8.5: the consumer ends Lena's assignments on Ashford --------------------------------------


async def _assign(firm: Firm, site: Site, who: Person, function: str) -> uuid.UUID:
    work_item = cast(
        uuid.UUID,
        await firm.seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 LIMIT 1", site.engagement_id
        ),
    )
    await firm.seed.run(
        "INSERT INTO work_item_assignments (tenant_id, work_item_id, engagement_id, user_id, "
        "function, assigned_by) VALUES ($1, $2, $3, $4, $5, $6)",
        firm.tenant_id,
        work_item,
        site.engagement_id,
        who.user_id,
        function,
        firm.grace.user_id,
    )
    return work_item


async def test_ac8_5_the_consumer_ends_lenas_assignments_on_ashford_only(firm: Firm) -> None:
    items: dict[uuid.UUID, uuid.UUID] = {}
    for site in (firm.ashford, firm.granite):
        await firm.seed.member(site.engagement_id, firm.lena, "staff")
        items[site.client_id] = await _assign(firm, site, firm.lena, "preparer")
    assert (await firm.wall_lena()).status_code == 201
    [event] = await firm.outbox("wall.created")
    await end_assignments_for_wall(event)
    # ED-038: the removal row undoes the assignment for the matrix's `function_in` too.
    tenant = TenantContext(firm.tenant_id, "human", str(firm.grace.user_id))
    ashford_item, granite_item = items[firm.ashford.client_id], items[firm.granite.client_id]
    assert await functions_on(tenant, ashford_item, firm.lena.user_id) == frozenset()
    assert await functions_on(tenant, granite_item, firm.lena.user_id) == {"preparer"}
    members = await firm.seed.rows(
        "SELECT engagement_id FROM engagement_members WHERE user_id = $1", firm.lena.user_id
    )
    assert [r["engagement_id"] for r in members] == [firm.granite.engagement_id]
    removals = await firm.seed.rows(
        "SELECT engagement_id, assigned_by FROM work_item_assignments "
        "WHERE user_id = $1 AND removed_at IS NOT NULL",
        firm.lena.user_id,
    )
    assert [(r["engagement_id"], r["assigned_by"]) for r in removals] == [
        (firm.ashford.engagement_id, firm.grace.user_id)
    ]
    for action in ("engagement_member.removed", "work_item.unassigned"):
        [row] = await firm.audit(action)
        assert row["actor_kind"] == "system"
        assert row["on_behalf_of_user_id"] == firm.grace.user_id
        assert row["target_id"] == str(firm.ashford.engagement_id)
    # Idempotent: a re-run finds nothing left to end.
    await end_assignments_for_wall(event)
    assert len(await firm.audit("work_item.unassigned")) == 1
    assert len(await firm.audit("engagement_member.removed")) == 1
    path = f"/v1/walls/preview?user_id={firm.lena.user_id}&client_id={firm.granite.client_id}"
    assert _body(await firm.call("GET", path, firm.grace))["assignments_ended"] == 2


async def test_ac8_5_the_last_partner_stays_on_the_team_and_a_lifted_wall_ends_nothing(
    firm: Firm,
) -> None:
    await firm.seed.member(firm.ashford.engagement_id, firm.daniel, "engagement_partner")
    wall = await firm.call(
        "POST",
        "/v1/walls",
        firm.grace,
        {"user_id": str(firm.daniel.user_id), "client_id": str(firm.ashford.client_id)},
    )
    [event] = await firm.outbox("wall.created")
    await end_assignments_for_wall(event)
    assert await firm.audit("engagement_member.removed") == []  # the engagement keeps a partner
    await firm.seed.member(firm.granite.engagement_id, firm.lena, "staff")
    lena_wall = await firm.call(
        "POST",
        "/v1/walls",
        firm.grace,
        {"user_id": str(firm.lena.user_id), "client_id": str(firm.granite.client_id)},
    )
    await firm.call("POST", f"/v1/walls/{_body(lena_wall)['id']}/remove", firm.margaret)
    events = await firm.outbox("wall.created")
    await end_assignments_for_wall(events[-1])
    assert await firm.audit("engagement_member.removed") == []
    assert wall.status_code == 201


# --- AC8.6: the wall log -------------------------------------------------------------------------


async def test_ac8_6_the_wall_log_names_grace_then_margaret_newest_first(firm: Firm) -> None:
    wall_id = _body(await firm.wall_lena())["id"]
    await firm.call("POST", f"/v1/walls/{wall_id}/approve", firm.margaret)
    log = await firm.call("GET", f"/v1/walls/{wall_id}/events", firm.grace)
    assert log.status_code == 200, log.text
    body = _body(log)
    items = cast(list[Json], body["items"])
    assert [(i["event_type"], i["actor_user_id"]) for i in items] == [
        ("wall.approved", str(firm.margaret.user_id)),
        ("wall.created", str(firm.grace.user_id)),
    ]
    assert body["total"] == 2
    assert (
        await firm.call("GET", f"/v1/walls/{uuid.uuid4()}/events", firm.grace)
    ).status_code == 404


async def test_ac8_6_a_walled_partner_finds_no_trace_of_the_client_in_walls(firm: Firm) -> None:
    """DEC-43 for the register: a partner walled from Ashford neither lists nor reads walls on
    it, nor walls on themself; the firm's wall administrators keep the whole register."""
    wall_id = _body(await firm.wall_lena())["id"]
    await firm.net.wall(firm.grace, firm.daniel.user_id, firm.ashford.client_id)
    listed = await firm.call("GET", "/v1/walls", firm.daniel)
    assert listed.status_code == 200
    assert str(firm.ashford.client_id) not in listed.text
    log = await firm.call("GET", f"/v1/walls/{wall_id}/events", firm.daniel)
    assert (log.status_code, log.json()) == (404, NOT_FOUND)
    lift = await firm.call("POST", f"/v1/walls/{wall_id}/remove", firm.daniel)
    assert (lift.status_code, lift.json()) == (404, NOT_FOUND)
    register = await firm.call("GET", "/v1/walls", firm.grace)
    assert len(cast(list[Json], register.json())) == 2


# --- notifications -------------------------------------------------------------------------------


async def test_ac8_2_margaret_is_asked_and_grace_is_told(firm: Firm) -> None:
    wall_id = _body(await firm.wall_lena())["id"]
    [created] = await firm.outbox("wall.created")
    await NOTIFY["wall.created"](created)
    await firm.call("POST", f"/v1/walls/{wall_id}/approve", firm.margaret)
    [approved] = await firm.outbox("wall.approved")
    await NOTIFY["wall.approved"](approved)
    rows = await firm.seed.rows(
        "SELECT recipient_user_id, kind, subject_type, subject_id::text AS subject_id "
        "FROM notifications WHERE tenant_id = $1 ORDER BY created_at",
        firm.tenant_id,
    )
    assert [(r["recipient_user_id"], r["kind"], r["subject_type"]) for r in rows] == [
        (firm.margaret.user_id, "wall_approval_requested", "ethical_wall"),
        (firm.grace.user_id, "wall_approved", "ethical_wall"),
    ]
    assert {r["subject_id"] for r in rows} == {wall_id}
