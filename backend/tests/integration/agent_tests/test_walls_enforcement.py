"""AC-4, AC-5, AC-6, AC-8, AC-9, AC-20: walls enforced over HTTP, in `authorise` and in `visible`
against a real Postgres (TASK-016 interface contract, "Enforcement").

Each test has its own firm: a walled client A (an engagement, a request item, an evidence version)
and an unrelated client B. People are made for every role, wall A off from them through the API,
and expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import dataclasses
import uuid
from dataclasses import dataclass
from typing import cast

import httpx
import pytest
from sqlalchemy import Uuid, column, select, table

from abacus.kernel.db import tenant_session
from abacus.kernel.uow import MissingAuditEvent, uow
from abacus.modules.engagements.api import EngagementRef, get_ref, lock_ref
from abacus.modules.identity import authz
from abacus.modules.identity.api import (
    Forbidden,
    Resource,
    authorise,
    system_context_for_run,
    visible,
)
from abacus_tools.fakes.identity import FakeIdentityProvider

from .support import Person, Role, Seeder, World, uploaded_version
from .walls_support import (
    ENGAGEMENT_ROLES,
    FIRM_ROLES,
    NOT_FOUND,
    Json,
    Net,
    Site,
    context,
    firm_role_of,
    ids,
)

ALL_ROLES = (*FIRM_ROLES, *ENGAGEMENT_ROLES)
CAN_ADD_ITEMS = {*FIRM_ROLES, "engagement_partner", "manager", "senior"}
ITEM: Json = {"description": "Bank confirmations", "audit_area": "Cash"}
READS = ("", "/request-items", "/evidence-versions", "/screening-results")
READ_ACTIONS = (
    "engagement.read_metadata",
    "engagement.read",
    "request_item.read",
    "evidence.read",
    "audit_event.read",
)


@pytest.fixture
def net(seed: Seeder, http: httpx.AsyncClient, idp: FakeIdentityProvider) -> Net:
    return Net(seed, http, idp)


@dataclass(frozen=True)
class Env:
    net: Net
    world: World
    admin: Person
    client_a: uuid.UUID
    site_b: Site
    item_b: uuid.UUID

    @property
    def tenant_id(self) -> uuid.UUID:
        return self.world.tenant_id

    @property
    def eng_a(self) -> uuid.UUID:
        return self.world.engagement_id

    @property
    def eng_b(self) -> uuid.UUID:
        return self.site_b.engagement_id

    async def actor(self, role: str) -> Person:
        """A person holding `role`, on both engagements (as a manager, for a firm role) so that
        every read route would answer 200 for them."""
        firm_role = role if role in FIRM_ROLES else None
        who = await self.net.person(self.tenant_id, firm_role)
        member = "manager" if firm_role else role
        for engagement_id in (self.eng_a, self.eng_b):
            await self.net.seed.member(engagement_id, who, cast(Role, member))
        return who

    async def get(self, who: Person, engagement_id: uuid.UUID, tail: str = "") -> httpx.Response:
        return await self.net.call("GET", f"/v1/engagements/{engagement_id}{tail}", who)

    async def wall(self, who: Person, client_id: uuid.UUID | None = None) -> uuid.UUID:
        return await self.net.wall(self.admin, who.user_id, client_id or self.client_a)


@pytest.fixture
async def env(net: Net, seed: Seeder, world: World) -> Env:
    admin = await net.person(world.tenant_id, "firm_admin")
    client_a = cast(
        uuid.UUID,
        await seed.value("SELECT client_id FROM client_entities WHERE id = $1", world.entity_id),
    )
    site_b = await net.site(world.tenant_id, admin.user_id)
    item_b = await seed.item(world.tenant_id, site_b.engagement_id, admin.user_id)
    await uploaded_version(seed, world)
    await uploaded_version(seed, dataclasses.replace(world, engagement_id=site_b.engagement_id))
    return Env(net, world, admin, client_a, site_b, item_b)


def _not_found(response: httpx.Response) -> None:
    assert response.status_code == 404, response.text
    assert response.json() == NOT_FOUND
    assert "WWW-Authenticate" not in response.headers


# --- AC-4: every role gets 404, not 403 ----------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac4_a_walled_person_gets_404_on_every_engagement_route_whatever_their_role(
    env: Env, role: str
) -> None:
    who = await env.actor(role)
    for tail in READS:
        assert (await env.get(who, env.eng_a, tail)).status_code == 200, (role, tail)
    await env.wall(who)
    for tail in READS:
        _not_found(await env.get(who, env.eng_a, tail))


@pytest.mark.parametrize("role", sorted(CAN_ADD_ITEMS))
async def test_ac4_a_walled_person_cannot_add_a_request_item_and_nothing_is_written(
    env: Env, role: str
) -> None:
    who = await env.actor(role)
    path = f"/v1/engagements/{env.eng_a}/request-items"
    assert (await env.net.call("POST", path, who, body=ITEM)).status_code == 201
    await env.wall(who)
    count = await env.net.seed.value(
        "SELECT count(*) FROM request_items WHERE engagement_id = $1", env.eng_a
    )
    _not_found(await env.net.call("POST", path, who, body=ITEM))
    assert (
        await env.net.seed.value(
            "SELECT count(*) FROM request_items WHERE engagement_id = $1", env.eng_a
        )
        == count
    )


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac4_the_404_is_the_same_as_for_an_engagement_that_does_not_exist(
    env: Env, role: str
) -> None:
    who = await env.actor(role)
    await env.wall(who)
    walled = await env.get(who, env.eng_a)
    missing = await env.get(who, uuid.uuid4())
    assert (walled.status_code, walled.json(), dict(walled.headers).keys()) == (
        missing.status_code,
        missing.json(),
        dict(missing.headers).keys(),
    )


async def test_ac4_starting_and_reading_a_retrieval_on_a_walled_engagement_is_404(
    env: Env,
) -> None:
    who = await env.actor("manager")
    await env.wall(who)
    body: Json = {
        "request_item_id": str(env.world.item_id),
        "period_start": "2025-01-01",
        "period_end": "2025-12-31",
    }
    runs = await env.net.seed.value("SELECT count(*) FROM sync_runs")
    _not_found(
        await env.net.call("POST", f"/v1/engagements/{env.eng_a}/retrievals", who, body=body)
    )
    _not_found(await env.get(who, env.eng_a, f"/retrievals/{uuid.uuid4()}"))
    assert await env.net.seed.value("SELECT count(*) FROM sync_runs") == runs


async def test_ac4_a_wall_does_not_turn_other_denials_into_404(env: Env) -> None:
    # A reviewer may not add items: still 403 on a client they are not walled from.
    who = await env.actor("reviewer")
    await env.wall(who, env.site_b.client_id)
    response = await env.net.call(
        "POST", f"/v1/engagements/{env.eng_a}/request-items", who, body=ITEM
    )
    assert response.status_code == 403
    assert response.json() == {"detail": "forbidden"}


async def test_ac4_someone_not_on_the_engagement_is_still_403_when_not_walled(env: Env) -> None:
    outsider = await env.net.person(env.tenant_id)
    response = await env.get(outsider, env.eng_a, "/request-items")
    assert response.status_code == 403


# --- AC-5: lists ---------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac5_the_engagement_list_excludes_the_walled_clients_engagements(
    env: Env, role: str
) -> None:
    who = await env.actor(role)
    later = await env.net.later_engagement(
        Site(env.client_a, env.world.entity_id, env.eng_a), env.tenant_id, env.admin.user_id
    )
    await env.net.seed.member(later, who, "manager")
    everything = ids(await env.net.call("GET", "/v1/engagements", who))
    assert {str(env.eng_a), str(env.eng_b), str(later)} <= set(everything)
    await env.wall(who)
    shown = ids(await env.net.call("GET", "/v1/engagements", who))
    assert str(env.eng_a) not in shown
    assert str(later) not in shown
    assert str(env.eng_b) in shown


async def test_ac5_the_list_shows_a_firm_admin_every_other_engagement_and_none_of_the_walled_one(
    env: Env,
) -> None:
    other = await env.net.person(env.tenant_id, "firm_admin")
    await env.wall(other)
    shown = ids(await env.net.call("GET", "/v1/engagements", other))
    assert shown == [str(env.eng_b)]


async def test_ac5_the_per_engagement_lists_show_the_unwalled_clients_rows_and_hide_the_walled(
    env: Env,
) -> None:
    who = await env.actor("manager")
    await env.wall(who)
    items = ids(await env.get(who, env.eng_b, "/request-items"))
    assert items == [str(env.item_b)]
    assert len(ids(await env.get(who, env.eng_b, "/evidence-versions"))) == 1
    assert ids(await env.get(who, env.eng_b, "/screening-results")) == []
    for tail in ("/request-items", "/evidence-versions", "/screening-results"):
        _not_found(await env.get(who, env.eng_a, tail))


async def test_ac5_several_walls_exclude_each_clients_engagements(env: Env) -> None:
    who = await env.actor("manager")
    await env.wall(who, env.client_a)
    await env.wall(who, env.site_b.client_id)
    assert ids(await env.net.call("GET", "/v1/engagements", who)) == []
    _not_found(await env.get(who, env.eng_a))
    _not_found(await env.get(who, env.eng_b))


# --- AC-6: future engagements --------------------------------------------------------------------


async def test_ac6_an_engagement_created_later_for_the_walled_client_is_walled_too(
    env: Env,
) -> None:
    who = await env.actor("manager")
    await env.wall(who)
    later = await env.net.later_engagement(
        Site(env.client_a, env.world.entity_id, env.eng_a), env.tenant_id, env.admin.user_id
    )
    await env.net.seed.item(env.tenant_id, later, env.admin.user_id)
    await env.net.seed.member(later, who, "engagement_partner")
    for tail in READS:
        _not_found(await env.get(who, later, tail))
    assert str(later) not in ids(await env.net.call("GET", "/v1/engagements", who))


async def test_ac6_the_later_engagement_is_walled_for_a_firm_admin_who_is_not_on_it(
    env: Env,
) -> None:
    other = await env.net.person(env.tenant_id, "firm_admin")
    await env.wall(other)
    later = await env.net.later_engagement(
        Site(env.client_a, env.world.entity_id, env.eng_a), env.tenant_id, env.admin.user_id
    )
    _not_found(await env.get(other, later))
    # Not walled: the metadata read is still the firm admin's.
    assert (await env.get(env.admin, later)).status_code == 200


# --- AC-8: other clients and other people --------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac8_access_to_other_clients_is_unchanged(env: Env, role: str) -> None:
    who = await env.actor(role)
    before = {tail: (await env.get(who, env.eng_b, tail)).json() for tail in READS}
    await env.wall(who)
    for tail in READS:
        response = await env.get(who, env.eng_b, tail)
        assert response.status_code == 200
        assert response.json() == before[tail]


async def test_ac8_other_people_keep_their_access_to_the_walled_client(env: Env) -> None:
    walled = await env.actor("manager")
    colleague = await env.actor("manager")
    await env.wall(walled)
    for tail in READS:
        assert (await env.get(colleague, env.eng_a, tail)).status_code == 200
    assert (await env.get(env.admin, env.eng_a)).status_code == 200


# --- AC-9: removal -------------------------------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac9_after_removal_access_follows_roles_again(env: Env, role: str) -> None:
    who = await env.actor(role)
    wall_id = await env.wall(who)
    _not_found(await env.get(who, env.eng_a))
    assert (await env.net.remove_wall(env.admin, wall_id)).status_code == 200
    for tail in READS:
        assert (await env.get(who, env.eng_a, tail)).status_code == 200, (role, tail)
    assert str(env.eng_a) in ids(await env.net.call("GET", "/v1/engagements", who))


async def test_ac9_a_new_wall_after_removal_walls_again(env: Env) -> None:
    who = await env.actor("senior")
    wall_id = await env.wall(who)
    await env.net.remove_wall(env.admin, wall_id)
    assert (await env.get(who, env.eng_a)).status_code == 200
    await env.wall(who)
    _not_found(await env.get(who, env.eng_a))


async def test_ac9_removing_one_of_two_walls_keeps_the_other(env: Env) -> None:
    who = await env.actor("manager")
    first = await env.wall(who, env.client_a)
    await env.wall(who, env.site_b.client_id)
    await env.net.remove_wall(env.admin, first)
    assert (await env.get(who, env.eng_a)).status_code == 200
    _not_found(await env.get(who, env.eng_b))


# --- authorise against the database --------------------------------------------------------------


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac4_authorise_denies_at_layer_wall_for_a_resource_without_a_client_id(
    env: Env, role: str
) -> None:
    who = await env.actor(role)
    await env.wall(who)
    ctx = context(who, firm_role_of(role))
    resource = Resource.engagement(env.tenant_id, env.eng_a, archived=False)
    for action in READ_ACTIONS:
        with pytest.raises(Forbidden) as raised:
            await authorise(ctx, action, resource)
        assert raised.value.layer == "wall", (role, action)


async def test_ac4_the_registered_lookup_is_used_when_the_resource_has_no_client(
    env: Env,
) -> None:
    who = await env.actor("manager")
    ctx = context(who)
    bare = Resource.engagement(env.tenant_id, env.eng_a, archived=False)
    await authorise(ctx, "request_item.read", bare)
    await env.wall(who)
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, "request_item.read", bare)
    assert raised.value.layer == "wall"
    other = Resource.engagement(env.tenant_id, env.eng_b, archived=False)
    await authorise(ctx, "request_item.read", other)


async def test_ac4_a_resource_client_id_decides_without_asking_the_engagement(env: Env) -> None:
    who = await env.actor("manager")
    await env.wall(who)
    ctx = context(who)
    # The wall is on client A; this resource says client B, so it is not walled (client_id wins).
    claimed = Resource.engagement(
        env.tenant_id, env.eng_a, archived=False, client_id=env.site_b.client_id
    )
    await authorise(ctx, "request_item.read", claimed)
    walled = Resource.engagement(env.tenant_id, env.eng_b, archived=False, client_id=env.client_a)
    with pytest.raises(Forbidden) as raised:
        await authorise(ctx, "request_item.read", walled)
    assert raised.value.layer == "wall"


async def test_ac4_engagement_refs_carry_the_client_and_resource_sets_it(env: Env) -> None:
    who = await env.actor("manager")
    ctx = context(who)
    ref = await get_ref(ctx, env.eng_a)
    assert ref.client_id == env.client_a
    assert ref.resource().client_id == env.client_a
    refs: list[EngagementRef] = []
    with pytest.raises(MissingAuditEvent):  # a read-only unit of work records nothing
        async with uow(ctx.tenant) as tx:
            refs.append(await lock_ref(tx, env.eng_b))
    [locked] = refs
    assert locked.client_id == env.site_b.client_id
    assert locked.resource().client_id == env.site_b.client_id


async def test_ac20_a_wall_applies_to_a_system_run_acting_for_the_person(env: Env) -> None:
    who = await env.actor("manager")
    system = system_context_for_run(
        tenant_id=env.tenant_id,
        run_id=uuid.uuid4(),
        engagement_id=env.eng_a,
        on_behalf_of=who.user_id,
    )
    resource = Resource.engagement(env.tenant_id, env.eng_a, archived=False)
    await authorise(system, "connection.pull", resource)
    await env.wall(who)
    with pytest.raises(Forbidden) as raised:
        await authorise(system, "connection.pull", resource)
    assert raised.value.layer == "wall"


# --- visible against the database ----------------------------------------------------------------

ITEMS = table("request_items", column("id", Uuid()), column("engagement_id", Uuid()))
ENGAGEMENTS = table("engagements", column("id", Uuid()), column("client_id", Uuid()))


async def _visible_items(who: Person, firm_role: str | None, action: str) -> set[uuid.UUID]:
    ctx = context(who, firm_role_of(firm_role))
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(ITEMS.c.engagement_id).where(visible(ctx, action, ITEMS.c.engagement_id))
        )
        return set(rows.scalars().all())


async def _visible_engagements(who: Person, firm_role: str | None) -> set[uuid.UUID]:
    ctx = context(who, firm_role_of(firm_role))
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(ENGAGEMENTS.c.id).where(
                visible(ctx, "engagement.read_metadata", ENGAGEMENTS.c.id)
            )
        )
        return set(rows.scalars().all())


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac5_visible_on_another_table_hides_the_walled_clients_rows(
    env: Env, role: str
) -> None:
    who = await env.actor(role)
    firm_role = role if role in FIRM_ROLES else None
    action = "request_item.read"
    assert await _visible_items(who, firm_role, action) == {env.eng_a, env.eng_b}
    await env.wall(who)
    assert await _visible_items(who, firm_role, action) == {env.eng_b}


@pytest.mark.parametrize("role", ALL_ROLES)
async def test_ac5_visible_correlates_when_the_outer_query_is_on_engagements_itself(
    env: Env, role: str
) -> None:
    who = await env.actor(role)
    firm_role = role if role in FIRM_ROLES else None
    assert {env.eng_a, env.eng_b} <= await _visible_engagements(who, firm_role)
    await env.wall(who)
    shown = await _visible_engagements(who, firm_role)
    assert env.eng_a not in shown
    assert env.eng_b in shown


async def test_ac5_visible_hides_a_later_engagement_of_the_walled_client(env: Env) -> None:
    who = await env.actor("firm_admin")
    await env.wall(who)
    later = await env.net.later_engagement(
        Site(env.client_a, env.world.entity_id, env.eng_a), env.tenant_id, env.admin.user_id
    )
    assert later not in await _visible_engagements(who, "firm_admin")


@pytest.mark.parametrize("action", READ_ACTIONS)
async def test_ac20_visible_agrees_with_authorise_for_walled_people(env: Env, action: str) -> None:
    people: list[tuple[Person, str | None]] = []
    for firm_role in (None, *FIRM_ROLES):
        for member in (None, "manager"):
            who = await env.net.person(env.tenant_id, firm_role)
            if member is not None:
                for engagement_id in (env.eng_a, env.eng_b):
                    await env.net.seed.member(engagement_id, who, "manager")
            await env.wall(who)
            people.append((who, firm_role))
    for who, firm_role in people:
        shown = await _visible_items(who, firm_role, action)
        ctx = context(who, firm_role_of(firm_role))
        for engagement_id in (env.eng_a, env.eng_b):
            try:
                await authorise(
                    ctx, action, Resource.engagement(env.tenant_id, engagement_id, archived=False)
                )
                allowed = True
            except Forbidden:
                allowed = False
            assert (engagement_id in shown) == allowed, (action, firm_role, engagement_id)


async def test_ac20_visible_unregistered_fails_closed_for_a_walled_person(
    env: Env, monkeypatch: pytest.MonkeyPatch
) -> None:
    who = await env.actor("manager")
    free = await env.actor("manager")
    await env.wall(who)
    monkeypatch.setattr(authz, "_engagement_client", None)
    assert await _visible_items(who, None, "request_item.read") == set()
    assert await _visible_items(free, None, "request_item.read") == {env.eng_a, env.eng_b}
