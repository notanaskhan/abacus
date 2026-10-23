# ac-test-author: ayushkbhatia
"""SPEC-017 AC-1 to AC-6 (TASK-032; back-filled by Q-03-T007): engagement team management.

HTTP through `create_app()` against a real Postgres. Expectations come from SPEC-017. Client
users reach an engagement through C5 grants (F-03-T26, DEC-129), never as team members. The
added person's notification is replayed by handing the outbox event to notifications' public
subscriber, as the relay does. AC-7 (the People tab) is a component test:
`apps/web/src/legacy/spec017people.test.tsx`.
"""

from __future__ import annotations

import json
import uuid
from typing import cast

import httpx
import pytest

from abacus.kernel.uow import OutboxEvent
from abacus.modules.notifications.api import SUBSCRIPTIONS as NOTIFY

from .support import Net, Person, Seeder, Site

FORBIDDEN = 403
LAST_PARTNER = {"detail": "last_partner"}
REFUSED = (403, 404)


class Team:
    """One open engagement with a partner and a manager, plus a firm administrator."""

    def __init__(
        self,
        net: Net,
        tenant_id: uuid.UUID,
        admin: Person,
        partner: Person,
        manager: Person,
        site: Site,
    ) -> None:
        self.net = net
        self.seed = net.seed
        self.tenant_id = tenant_id
        self.admin = admin
        self.partner = partner
        self.manager = manager
        self.site = site
        self.base = f"/v1/engagements/{site.engagement_id}"

    async def staff(self) -> Person:
        return await self.seed.person(self.tenant_id)

    async def add(self, who: Person, person: Person | uuid.UUID, role: str) -> httpx.Response:
        user_id = person if isinstance(person, uuid.UUID) else person.user_id
        return await self.net.call(
            "POST", f"{self.base}/team", who, body={"user_id": str(user_id), "role": role}
        )

    async def change(self, who: Person, person: Person, role: str) -> httpx.Response:
        return await self.net.call(
            "PUT", f"{self.base}/team/{person.user_id}", who, body={"role": role}
        )

    async def remove(self, who: Person, person: Person) -> httpx.Response:
        return await self.net.call("DELETE", f"{self.base}/team/{person.user_id}", who)

    async def roles(self) -> dict[uuid.UUID, str]:
        response = await self.net.call("GET", f"{self.base}/team", self.partner)
        assert response.status_code == 200, response.text
        return {uuid.UUID(m["user_id"]): str(m["role"]) for m in response.json()}

    async def candidates(self, who: Person | None = None) -> set[uuid.UUID]:
        response = await self.net.call("GET", f"{self.base}/team/candidates", who or self.partner)
        assert response.status_code == 200, response.text
        return {uuid.UUID(c["user_id"]) for c in response.json()}

    async def actions(self) -> list[str]:
        return await self.seed.actions(self.tenant_id)


@pytest.fixture
async def team(net: Net, seed: Seeder) -> Team:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    partner = await seed.person(tenant_id)
    manager = await seed.person(tenant_id)
    site = await seed.site(tenant_id, partner.user_id, "Calloway")
    await seed.member(site, partner, "engagement_partner")
    await seed.member(site, manager, "manager")
    return Team(net, tenant_id, admin, partner, manager, site)


# --- AC-1: a partner adds anyone eligible, with any role -----------------------------------------


async def test_ac1_candidates_are_active_staff_not_on_the_team_and_not_walled(
    team: Team, seed: Seeder
) -> None:
    eligible = await team.staff()
    on_team = await team.staff()
    await seed.member(team.site, on_team, "senior")
    walled = await team.staff()
    await team.net.wall(team.admin, walled, team.site)
    revoked = await team.staff()
    await seed.revoke(revoked)
    client = await seed.client_contact(team.site)
    other_firm = await seed.firm()
    outsider = await seed.person(other_firm)

    found = await team.candidates()
    assert eligible.user_id in found
    assert team.admin.user_id in found  # a firm administrator is staff too
    for excluded in (on_team, walled, revoked, client, outsider, team.partner, team.manager):
        assert excluded.user_id not in found


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff", "reviewer"])
async def test_ac1_a_partner_adds_a_candidate_with_any_role_and_it_is_audited(
    team: Team, role: str
) -> None:
    person = await team.staff()
    response = await team.add(team.partner, person, role)
    assert response.status_code == 201, response.text
    assert {uuid.UUID(m["user_id"]): m["role"] for m in response.json()}[person.user_id] == role
    assert (await team.roles())[person.user_id] == role
    assert "engagement_member.added" in await team.actions()


async def test_ac1_the_person_added_is_notified(team: Team, seed: Seeder) -> None:
    person = await team.staff()
    response = await team.add(team.partner, person, "senior")
    assert response.status_code == 201, response.text
    rows = await seed.rows(
        "SELECT id, tenant_id, event_type, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'engagement_member.added' ORDER BY seq",
        team.tenant_id,
    )
    assert len(rows) == 1
    event = OutboxEvent(
        rows[0]["id"],
        rows[0]["tenant_id"],
        str(rows[0]["event_type"]),
        cast(dict[str, object], json.loads(str(rows[0]["payload"]))),
    )
    await NOTIFY[event.event_type](event)
    mine = await team.net.call("GET", "/v1/notifications", person)
    assert mine.status_code == 200, mine.text
    kinds = [n["kind"] for n in mine.json()["items"]]
    assert kinds == ["engagement_member.added"]
    others = await team.net.call("GET", "/v1/notifications", team.manager)
    assert [n["kind"] for n in others.json()["items"]] == []  # only the person added


async def test_ac1_someone_already_on_the_team_cannot_be_added_again(
    team: Team, seed: Seeder
) -> None:
    person = await team.staff()
    await seed.member(team.site, person, "staff")
    response = await team.add(team.partner, person, "senior")
    assert response.status_code != 201
    assert (await team.roles())[person.user_id] == "staff"


async def test_ac1_people_without_member_add_can_neither_list_candidates_nor_add(
    team: Team, seed: Seeder
) -> None:
    senior = await team.staff()
    await seed.member(team.site, senior, "senior")
    person = await team.staff()
    listed = await team.net.call("GET", f"{team.base}/team/candidates", senior)
    assert listed.status_code in REFUSED
    added = await team.add(senior, person, "staff")
    assert added.status_code in REFUSED
    assert person.user_id not in await team.roles()


# --- AC-2: managers handle seniors, staff and reviewers only -------------------------------------


@pytest.mark.parametrize("role", ["senior", "staff", "reviewer"])
async def test_ac2_a_manager_adds_changes_and_removes_junior_roles(team: Team, role: str) -> None:
    person = await team.staff()
    added = await team.add(team.manager, person, role)
    assert added.status_code == 201, added.text
    other = next(r for r in ("senior", "staff", "reviewer") if r != role)
    changed = await team.change(team.manager, person, other)
    assert changed.status_code == 200, changed.text
    assert (await team.roles())[person.user_id] == other
    removed = await team.remove(team.manager, person)
    assert removed.status_code == 200, removed.text
    assert person.user_id not in await team.roles()


@pytest.mark.parametrize("role", ["engagement_partner", "manager"])
async def test_ac2_a_manager_cannot_grant_partner_or_manager(team: Team, role: str) -> None:
    person = await team.staff()
    response = await team.add(team.manager, person, role)
    assert response.status_code == FORBIDDEN, response.text
    assert person.user_id not in await team.roles()


@pytest.mark.parametrize("role", ["engagement_partner", "manager"])
async def test_ac2_a_manager_cannot_promote_a_senior_to_partner_or_manager(
    team: Team, seed: Seeder, role: str
) -> None:
    senior = await team.staff()
    await seed.member(team.site, senior, "senior")
    response = await team.change(team.manager, senior, role)
    assert response.status_code == FORBIDDEN, response.text
    assert (await team.roles())[senior.user_id] == "senior"


async def test_ac2_a_manager_cannot_change_or_remove_a_partner_or_another_manager(
    team: Team, seed: Seeder
) -> None:
    second_partner = await team.staff()
    await seed.member(team.site, second_partner, "engagement_partner")
    second_manager = await team.staff()
    await seed.member(team.site, second_manager, "manager")
    for target in (second_partner, second_manager):
        changed = await team.change(team.manager, target, "senior")
        assert changed.status_code == FORBIDDEN, changed.text
        removed = await team.remove(team.manager, target)
        assert removed.status_code == FORBIDDEN, removed.text
    roles = await team.roles()
    assert roles[second_partner.user_id] == "engagement_partner"
    assert roles[second_manager.user_id] == "manager"


async def test_ac2_role_changes_and_removals_are_audited(team: Team) -> None:
    person = await team.staff()
    assert (await team.add(team.partner, person, "staff")).status_code == 201
    assert (await team.change(team.partner, person, "manager")).status_code == 200
    assert (await team.remove(team.partner, person)).status_code == 200
    actions = await team.actions()
    assert "engagement_member.role_changed" in actions
    assert "engagement_member.removed" in actions


# --- AC-3: never without a partner ---------------------------------------------------------------


async def test_ac3_the_last_partner_cannot_be_removed(team: Team) -> None:
    response = await team.remove(team.partner, team.partner)
    assert response.status_code == 409, response.text
    assert response.json() == LAST_PARTNER
    assert (await team.roles())[team.partner.user_id] == "engagement_partner"


@pytest.mark.parametrize("role", ["manager", "senior", "staff", "reviewer"])
async def test_ac3_the_last_partner_cannot_be_demoted(team: Team, role: str) -> None:
    response = await team.change(team.partner, team.partner, role)
    assert response.status_code == 409, response.text
    assert response.json() == LAST_PARTNER
    assert (await team.roles())[team.partner.user_id] == "engagement_partner"


async def test_ac3_with_two_partners_one_may_leave_but_then_not_the_other(
    team: Team, seed: Seeder
) -> None:
    second = await team.staff()
    await seed.member(team.site, second, "engagement_partner")
    left = await team.remove(team.partner, team.partner)  # removing yourself is allowed
    assert left.status_code == 200, left.text
    last = await team.remove(second, second)
    assert last.status_code == 409, last.text
    assert last.json() == LAST_PARTNER
    remaining = await team.net.call("GET", f"{team.base}/team", second)
    roles = {uuid.UUID(m["user_id"]): m["role"] for m in remaining.json()}
    assert roles[second.user_id] == "engagement_partner"
    assert team.partner.user_id not in roles


# --- AC-4: walls never leak ----------------------------------------------------------------------


async def test_ac4_a_walled_person_is_refused_with_the_same_404_as_an_unknown_one(
    team: Team,
) -> None:
    walled = await team.staff()
    await team.net.wall(team.admin, walled, team.site)
    assert walled.user_id not in await team.candidates()
    by_id = await team.add(team.partner, walled, "staff")
    unknown = await team.add(team.partner, uuid.uuid4(), "staff")
    assert by_id.status_code == 404
    assert (by_id.status_code, by_id.json()) == (unknown.status_code, unknown.json())
    assert walled.user_id not in await team.roles()


# --- AC-5: removal ends access and releases review assignments -----------------------------------


async def test_ac5_a_removed_member_is_refused_on_their_next_request(
    team: Team, seed: Seeder
) -> None:
    senior = await team.staff()
    await seed.member(team.site, senior, "senior")
    before = await team.net.call("GET", team.base, senior)
    assert before.status_code == 200, before.text
    removed = await team.remove(team.partner, senior)
    assert removed.status_code == 200, removed.text
    after = await team.net.call("GET", team.base, senior)
    assert after.status_code in REFUSED
    assert team.site.marker not in after.text


async def test_ac5_their_review_assignments_on_the_engagement_are_released_and_audited(
    team: Team, seed: Seeder
) -> None:
    senior = await team.staff()
    await seed.member(team.site, senior, "senior")
    await seed.run(
        "INSERT INTO review_assignments (tenant_id, evidence_version_id, engagement_id, "
        "assignee_user_id, assigned_by) VALUES ($1, $2, $3, $4, $5)",
        team.tenant_id,
        team.site.version_id,
        team.site.engagement_id,
        senior.user_id,
        team.partner.user_id,
    )
    removed = await team.remove(team.partner, senior)
    assert removed.status_code == 200, removed.text
    held = await seed.value(
        "SELECT count(*) FROM review_assignments WHERE tenant_id = $1 AND assignee_user_id = $2",
        team.tenant_id,
        senior.user_id,
    )
    assert held == 0
    assert "review.released" in await team.actions()


# --- AC-6: only the firm's own staff -------------------------------------------------------------


async def test_ac6_a_client_user_cannot_be_added(team: Team, seed: Seeder) -> None:
    client = await seed.client_contact(team.site)
    response = await team.add(team.partner, client, "staff")
    assert response.status_code == 404, response.text
    assert client.user_id not in await team.roles()


async def test_ac6_a_user_of_another_firm_cannot_be_added(team: Team, seed: Seeder) -> None:
    other_firm = await seed.firm()
    outsider = await seed.person(other_firm)
    response = await team.add(team.partner, outsider, "staff")
    assert response.status_code == 404, response.text
    assert outsider.user_id not in await team.roles()
