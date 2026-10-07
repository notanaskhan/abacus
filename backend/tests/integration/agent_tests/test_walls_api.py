"""AC-1, AC-2, AC-3, AC-9, AC-10: the wall routes over HTTP (TASK-016 interface contract,
"Routes"; SPEC-002 §5, §8).

Rows are seeded as the superuser with a fresh firm per test. Expectations come from the contract,
not the implementation.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import cast

import httpx
import pytest

from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Role, Seeder
from .walls_support import (
    ENGAGEMENT_ROLES,
    FIRM_ROLES,
    FORBIDDEN,
    NOT_FOUND,
    WALL_KEYS,
    Json,
    Net,
    Site,
)


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@dataclass(frozen=True)
class Env:
    net: Net
    tenant_id: uuid.UUID
    admin: Person
    member: Person
    site: Site


@pytest.fixture
async def env(net: Net, seed: Seeder) -> Env:
    tenant_id = await seed.firm()
    admin = await net.person(tenant_id, "firm_admin")
    member = await net.person(tenant_id)
    site = await net.site(tenant_id, admin.user_id)
    return Env(net, tenant_id, admin, member, site)


def _body(response: httpx.Response) -> Json:
    return cast(Json, response.json())


async def _unchanged(env: Env) -> None:
    assert await env.net.wall_rows(env.tenant_id) == 0
    assert await env.net.audit(env.tenant_id, "wall.created") == []
    assert await env.net.audit(env.tenant_id, "wall.removed") == []


# --- AC-1: create --------------------------------------------------------------------------------


async def test_ac1_a_firm_admin_with_fresh_mfa_creates_a_wall(env: Env) -> None:
    response = await env.net.create_wall(env.admin, env.member.user_id, env.site.client_id)
    assert response.status_code == 201, response.text
    body = _body(response)
    assert set(body) == WALL_KEYS
    assert uuid.UUID(cast(str, body["id"]))
    assert body["user_id"] == str(env.member.user_id)
    assert body["client_id"] == str(env.site.client_id)
    assert body["status"] == "active"
    assert body["created_by"] == str(env.admin.user_id)
    assert datetime.fromisoformat(cast(str, body["created_at"])).tzinfo is not None
    assert body["removed_by"] is None
    assert body["removed_at"] is None


async def test_ac1_the_wall_row_exists_after_creating_it(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    [row] = await env.net.seed.rows(
        "SELECT tenant_id, user_id, client_id, status, created_by, removed_by, removed_at "
        "FROM ethical_walls WHERE id = $1",
        wall_id,
    )
    assert row["tenant_id"] == env.tenant_id
    assert row["user_id"] == env.member.user_id
    assert row["client_id"] == env.site.client_id
    assert row["status"] == "active"
    assert row["created_by"] == env.admin.user_id
    assert row["removed_by"] is None
    assert row["removed_at"] is None


async def test_ac1_wall_created_is_audited_with_actor_target_and_refs(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    [event] = await env.net.audit(env.tenant_id, "wall.created")
    assert event["actor_kind"] == "human"
    assert event["actor_id"] == str(env.admin.user_id)
    assert event["target_type"] == "ethical_wall"
    assert event["target_id"] == str(wall_id)
    after = cast(str, event["after_ref"])
    assert str(env.member.user_id) in after
    assert str(env.site.client_id) in after


async def test_ac1_the_person_is_walled_from_their_next_request(env: Env) -> None:
    await env.net.seed.member(env.site.engagement_id, env.member, "manager")
    path = f"/v1/engagements/{env.site.engagement_id}"
    before = await env.net.call("GET", path, env.member)
    assert before.status_code == 200
    await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    after = await env.net.call("GET", path, env.member)
    assert after.status_code == 404


async def test_ac1_a_firm_admin_may_wall_themself(env: Env) -> None:
    response = await env.net.create_wall(env.admin, env.admin.user_id, env.site.client_id)
    assert response.status_code == 201
    assert _body(response)["user_id"] == str(env.admin.user_id)


async def test_ac1_mfa_within_15_minutes_is_fresh(env: Env) -> None:
    response = await env.net.call(
        "POST",
        "/v1/walls",
        env.admin,
        body={"user_id": str(env.member.user_id), "client_id": str(env.site.client_id)},
        mfa_age=timedelta(minutes=10),
    )
    assert response.status_code == 201


# --- AC-2: who may not create --------------------------------------------------------------------


async def test_ac2_a_firm_admin_without_mfa_gets_403_and_nothing_changes(env: Env) -> None:
    response = await env.net.call(
        "POST",
        "/v1/walls",
        env.admin,
        body={"user_id": str(env.member.user_id), "client_id": str(env.site.client_id)},
        mfa=False,
    )
    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    await _unchanged(env)


async def test_ac2_mfa_older_than_15_minutes_gets_403_and_nothing_changes(env: Env) -> None:
    response = await env.net.call(
        "POST",
        "/v1/walls",
        env.admin,
        body={"user_id": str(env.member.user_id), "client_id": str(env.site.client_id)},
        mfa_age=timedelta(minutes=20),
    )
    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    await _unchanged(env)


@pytest.mark.parametrize("role", [None, *[r for r in FIRM_ROLES if r != "firm_admin"]])
async def test_ac2_other_firm_roles_get_403_and_nothing_changes(
    env: Env, role: str | None
) -> None:
    who = await env.net.person(env.tenant_id, role)
    response = await env.net.create_wall(who, env.member.user_id, env.site.client_id)
    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    await _unchanged(env)


@pytest.mark.parametrize("role", ENGAGEMENT_ROLES)
async def test_ac2_engagement_roles_get_403_and_nothing_changes(env: Env, role: str) -> None:
    who = await env.net.person(env.tenant_id)
    await env.net.seed.member(env.site.engagement_id, who, cast(Role, role))
    response = await env.net.create_wall(who, env.member.user_id, env.site.client_id)
    assert response.status_code == 403
    await _unchanged(env)


async def test_ac2_no_token_is_401(env: Env) -> None:
    response = await env.net.http.post(
        "/v1/walls",
        json={"user_id": str(env.member.user_id), "client_id": str(env.site.client_id)},
    )
    assert response.status_code == 401
    await _unchanged(env)


# --- create: unknown member or client is 404 -----------------------------------------------------


async def test_ac1_a_user_who_is_not_a_member_of_the_firm_is_404(env: Env, seed: Seeder) -> None:
    other_firm = await seed.firm()
    outsider = await env.net.person(other_firm)
    for user_id in (outsider.user_id, uuid.uuid4()):
        response = await env.net.create_wall(env.admin, user_id, env.site.client_id)
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
    await _unchanged(env)


async def test_ac1_a_client_that_is_not_in_the_firm_is_404(
    env: Env, net: Net, seed: Seeder
) -> None:
    other_firm = await seed.firm()
    foreign_admin = await net.person(other_firm, "firm_admin")
    foreign = await net.site(other_firm, foreign_admin.user_id)
    for client_id in (foreign.client_id, uuid.uuid4()):
        response = await env.net.create_wall(env.admin, env.member.user_id, client_id)
        assert response.status_code == 404
        assert response.json() == NOT_FOUND
    await _unchanged(env)
    assert await env.net.wall_rows(other_firm) == 0


# --- AC-3: a duplicate is 409 --------------------------------------------------------------------


async def test_ac3_the_same_wall_twice_is_409_wall_exists(env: Env) -> None:
    await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    again = await env.net.create_wall(env.admin, env.member.user_id, env.site.client_id)
    assert again.status_code == 409
    assert again.json() == {"detail": "wall_exists"}
    assert await env.net.wall_rows(env.tenant_id) == 1
    assert len(await env.net.audit(env.tenant_id, "wall.created")) == 1


async def test_ac3_a_different_user_or_client_is_not_a_duplicate(env: Env) -> None:
    await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    other_person = await env.net.person(env.tenant_id)
    other_site = await env.net.site(env.tenant_id, env.admin.user_id)
    assert (
        await env.net.create_wall(env.admin, other_person.user_id, env.site.client_id)
    ).status_code == 201
    assert (
        await env.net.create_wall(env.admin, env.member.user_id, other_site.client_id)
    ).status_code == 201


async def test_ac3_a_removed_wall_does_not_block_a_new_one_for_the_same_pair(env: Env) -> None:
    first = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    assert (await env.net.remove_wall(env.admin, first)).status_code == 200
    second = await env.net.create_wall(env.admin, env.member.user_id, env.site.client_id)
    assert second.status_code == 201
    assert _body(second)["id"] != str(first)
    assert _body(second)["status"] == "active"


# --- remove --------------------------------------------------------------------------------------


async def test_ac9_a_firm_admin_removes_a_wall_and_gets_it_back_marked_removed(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    response = await env.net.remove_wall(env.admin, wall_id)
    assert response.status_code == 200, response.text
    body = _body(response)
    assert set(body) == WALL_KEYS
    assert body["id"] == str(wall_id)
    assert body["status"] == "removed"
    assert body["user_id"] == str(env.member.user_id)
    assert body["client_id"] == str(env.site.client_id)
    assert body["removed_by"] == str(env.admin.user_id)
    removed_at = datetime.fromisoformat(cast(str, body["removed_at"]))
    assert removed_at.tzinfo is not None
    assert abs(datetime.now(UTC) - removed_at) < timedelta(minutes=5)


async def test_ac9_the_wall_row_is_kept_not_deleted(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    await env.net.remove_wall(env.admin, wall_id)
    [row] = await env.net.seed.rows(
        "SELECT status, removed_by, removed_at FROM ethical_walls WHERE id = $1", wall_id
    )
    assert row["status"] == "removed"
    assert row["removed_by"] == env.admin.user_id
    assert row["removed_at"] is not None


async def test_ac9_wall_removed_is_audited(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    await env.net.remove_wall(env.admin, wall_id)
    [event] = await env.net.audit(env.tenant_id, "wall.removed")
    assert event["actor_kind"] == "human"
    assert event["actor_id"] == str(env.admin.user_id)
    assert event["target_type"] == "ethical_wall"
    assert event["target_id"] == str(wall_id)
    assert str(env.member.user_id) in str(event["before_ref"])
    assert str(env.site.client_id) in str(event["before_ref"])


async def test_ac9_an_unknown_wall_is_404(env: Env) -> None:
    response = await env.net.remove_wall(env.admin, uuid.uuid4())
    assert response.status_code == 404
    assert response.json() == NOT_FOUND


async def test_ac9_an_already_removed_wall_is_404_and_audited_once(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    assert (await env.net.remove_wall(env.admin, wall_id)).status_code == 200
    again = await env.net.remove_wall(env.admin, wall_id)
    assert again.status_code == 404
    assert again.json() == NOT_FOUND
    assert len(await env.net.audit(env.tenant_id, "wall.removed")) == 1


async def test_ac9_another_firms_wall_is_404(env: Env, net: Net, seed: Seeder) -> None:
    other_firm = await seed.firm()
    other_admin = await net.person(other_firm, "firm_admin")
    other_member = await net.person(other_firm)
    other_site = await net.site(other_firm, other_admin.user_id)
    foreign = await net.wall(other_admin, other_member.user_id, other_site.client_id)
    response = await env.net.remove_wall(env.admin, foreign)
    assert response.status_code == 404
    [row] = await seed.rows("SELECT status FROM ethical_walls WHERE id = $1", foreign)
    assert row["status"] == "active"


async def test_ac9_removal_without_fresh_mfa_is_403_and_the_wall_stays(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    path = f"/v1/walls/{wall_id}/remove"
    for response in (
        await env.net.call("POST", path, env.admin, mfa=False),
        await env.net.call("POST", path, env.admin, mfa_age=timedelta(minutes=20)),
    ):
        assert response.status_code == 403
        assert response.json() == FORBIDDEN
    [row] = await env.net.seed.rows("SELECT status FROM ethical_walls WHERE id = $1", wall_id)
    assert row["status"] == "active"
    assert await env.net.audit(env.tenant_id, "wall.removed") == []


@pytest.mark.parametrize("role", [None, "practice_leader", "quality_partner"])
async def test_ac9_other_roles_cannot_remove_a_wall(env: Env, role: str | None) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    who = await env.net.person(env.tenant_id, role)
    response = await env.net.remove_wall(who, wall_id)
    assert response.status_code == 403
    assert response.json() == FORBIDDEN
    [row] = await env.net.seed.rows("SELECT status FROM ethical_walls WHERE id = $1", wall_id)
    assert row["status"] == "active"


async def test_ac9_the_person_walled_cannot_lift_their_own_wall(env: Env) -> None:
    # A walled non-admin has no right to remove walls at all.
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    response = await env.net.remove_wall(env.member, wall_id)
    assert response.status_code == 403


# --- a firm admin can't lift a wall on themself --------------------------------------------------


async def test_ac9_a_firm_admin_cannot_remove_a_wall_on_themself(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.admin.user_id, env.site.client_id)
    response = await env.net.remove_wall(env.admin, wall_id)
    assert response.status_code == 409
    assert response.json() == {"detail": "own_wall"}
    [row] = await env.net.seed.rows(
        "SELECT status, removed_by, removed_at FROM ethical_walls WHERE id = $1", wall_id
    )
    assert (row["status"], row["removed_by"], row["removed_at"]) == ("active", None, None)
    assert await env.net.audit(env.tenant_id, "wall.removed") == []


async def test_ac9_another_firm_admin_can_remove_a_wall_on_a_firm_admin(env: Env) -> None:
    wall_id = await env.net.wall(env.admin, env.admin.user_id, env.site.client_id)
    second = await env.net.person(env.tenant_id, "firm_admin")
    response = await env.net.remove_wall(second, wall_id)
    assert response.status_code == 200
    assert _body(response)["removed_by"] == str(second.user_id)
    assert len(await env.net.audit(env.tenant_id, "wall.removed")) == 1


async def test_ac9_a_firm_admin_can_still_remove_walls_on_others(env: Env) -> None:
    mine = await env.net.wall(env.admin, env.admin.user_id, env.site.client_id)
    theirs = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    assert (await env.net.remove_wall(env.admin, mine)).status_code == 409
    assert (await env.net.remove_wall(env.admin, theirs)).status_code == 200


# --- AC-10: list ---------------------------------------------------------------------------------


async def test_ac10_a_firm_admin_lists_each_wall_with_user_client_creator_and_time(
    env: Env,
) -> None:
    wall_id = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    response = await env.net.list_walls(env.admin)
    assert response.status_code == 200
    [wall] = cast(list[Json], response.json())
    assert set(wall) == WALL_KEYS
    assert wall["id"] == str(wall_id)
    assert wall["user_id"] == str(env.member.user_id)
    assert wall["client_id"] == str(env.site.client_id)
    assert wall["created_by"] == str(env.admin.user_id)
    assert datetime.fromisoformat(cast(str, wall["created_at"])).tzinfo is not None
    assert wall["status"] == "active"


async def test_ac10_the_list_is_every_wall_of_the_firm_newest_first_including_removed(
    env: Env,
) -> None:
    first = await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    other_site = await env.net.site(env.tenant_id, env.admin.user_id)
    second = await env.net.wall(env.admin, env.member.user_id, other_site.client_id)
    third = await env.net.wall(env.admin, env.admin.user_id, env.site.client_id)
    await env.net.remove_wall(env.admin, first)
    listed = cast(list[Json], (await env.net.list_walls(env.admin)).json())
    assert [w["id"] for w in listed] == [str(third), str(second), str(first)]
    assert [w["status"] for w in listed] == ["active", "active", "removed"]


async def test_ac10_the_list_has_only_this_firms_walls(env: Env, net: Net, seed: Seeder) -> None:
    other_firm = await seed.firm()
    other_admin = await net.person(other_firm, "firm_admin")
    other_member = await net.person(other_firm)
    other_site = await net.site(other_firm, other_admin.user_id)
    await net.wall(other_admin, other_member.user_id, other_site.client_id)
    assert (await env.net.list_walls(env.admin)).json() == []


async def test_ac10_an_empty_firm_lists_nothing(env: Env) -> None:
    response = await env.net.list_walls(env.admin)
    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("role", [None, "practice_leader", "quality_partner"])
async def test_ac10_no_one_else_may_list_walls(env: Env, role: str | None) -> None:
    await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    who = await env.net.person(env.tenant_id, role)
    response = await env.net.list_walls(who)
    assert response.status_code == 403
    assert response.json() == FORBIDDEN


@pytest.mark.parametrize("role", ENGAGEMENT_ROLES)
async def test_ac10_engagement_roles_may_not_list_walls(env: Env, role: str) -> None:
    who = await env.net.person(env.tenant_id)
    await env.net.seed.member(env.site.engagement_id, who, cast(Role, role))
    assert (await env.net.list_walls(who)).status_code == 403


async def test_ac10_listing_needs_fresh_mfa(env: Env) -> None:
    assert (await env.net.list_walls(env.admin, mfa=False)).status_code == 403
    response = await env.net.call("GET", "/v1/walls", env.admin, mfa_age=timedelta(minutes=20))
    assert response.status_code == 403


async def test_ac10_the_walled_person_cannot_see_the_list(env: Env) -> None:
    await env.net.wall(env.admin, env.member.user_id, env.site.client_id)
    assert (await env.net.list_walls(env.member)).status_code == 403
