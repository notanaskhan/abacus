# ac-test-author: ayushkbhatia
"""Q-03-T021: the tranche-0 TASK-029 suite (SPEC-014, `test_firm_level_reads.py`, re-run as is)
extended to the generalised `visible()` of ADR-145 (plan P-06, DEC-33): the scope kinds
`engagement`, `work_item`, `client`, `client_entity` and `portal_scope`.

Each kind has an allow, a deny and a cross-tenant case, a walled person sees nothing of the
walled client through any kind (ADR-145: "every kind evaluates ethical walls on client_id"), and
the exhaustive property test checks that `visible()` agrees with `authorise()` for every persona
and every row of the firm.

The boundary is identity's public `api.py` (`visible_scope`, `authorise`, `Resource`), applied to
the real tables on the migrated Postgres under the firm's tenant session, as a repository list
would apply it. The oracle for each kind is ADR-145's wording, not the implementation:
- `engagement`, `work_item`: the row's engagement, as `authorise` decides on that engagement;
- `client`, `client_entity`: "the user can read content on at least one non-walled engagement of
  that client": a content read (`engagement.read`) is used, so the ADR's metadata-only clause
  does not apply;
- `portal_scope`: a client user's grant on the scope (here an engagement-scope grant).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Final, cast

import pytest
from sqlalchemy import ColumnElement, Uuid, column, select, table

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.engagements import api as _engagements  # registers engagement lookups
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    VisibleScopeKind,
    authorise,
    visible_scope,
)

from .support import Net, Person, Seeder, Site

assert _engagements  # imported for its registrations

ENGAGEMENTS = table("engagements", column("id", Uuid()), column("client_id", Uuid()))
WORK_ITEMS = table("work_items", column("id", Uuid()), column("engagement_id", Uuid()))
CLIENTS = table("clients", column("id", Uuid()))
ENTITIES = table("client_entities", column("id", Uuid()), column("client_id", Uuid()))

# The read action each kind is exercised with (matrix: docs/architecture/permission-matrix).
ACTION: Final[dict[str, str]] = {
    "engagement": "engagement.read",  # content; ADR-024
    "work_item": "work_item.read_metadata",  # C1's work-item list (F-03-T05)
    "client": "engagement.read",
    "client_entity": "engagement.read",
    "portal_scope": "portal_documents.read",  # POR-03/04 (C5 portal-pbc)
}
FIRM_KINDS: Final = ("engagement", "work_item", "client", "client_entity")
KINDS: Final = (*FIRM_KINDS, "portal_scope")


def _ctx(who: Person, tenant: uuid.UUID | None = None, *, client: bool = False) -> AuthContext:
    firm = tenant or who.tenant_id
    return AuthContext(
        tenant=TenantContext(firm, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role=None,
        mfa_at=datetime.now(UTC),
        client=client,
    )


def _admin_ctx(who: Person) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(who.tenant_id, "human", str(who.user_id)),
        user_id=who.user_id,
        membership_id=uuid.uuid4(),
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC),
    )


@dataclass(frozen=True)
class Row:
    """One listable row of a kind and the engagements it hangs on (with their client)."""

    id: uuid.UUID
    engagements: tuple[tuple[uuid.UUID, uuid.UUID], ...]


@dataclass(frozen=True)
class Firm:
    tenant: uuid.UUID
    sites: tuple[Site, ...]
    work_items: dict[uuid.UUID, uuid.UUID]  # engagement -> its work item

    def rows(self, kind: str) -> list[Row]:
        out: list[Row] = []
        for s in self.sites:
            pair = ((s.engagement_id, s.client_id),)
            if kind in ("engagement", "portal_scope"):
                out.append(Row(s.engagement_id, pair))
            elif kind == "work_item":
                out.append(Row(self.work_items[s.engagement_id], pair))
            elif kind == "client":
                out.append(Row(s.client_id, pair))
            else:
                out.append(Row(s.entity_id, pair))
        return out


async def _work_item(seed: Seeder, site: Site, by: Person) -> uuid.UUID:
    found = await seed.value(
        "SELECT id FROM work_items WHERE engagement_id = $1 ORDER BY id LIMIT 1",
        site.engagement_id,
    )
    if found is not None:
        return cast(uuid.UUID, found)
    return cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Audit', $5) "
            "RETURNING id",
            site.tenant_id,
            site.engagement_id,
            site.client_id,
            site.entity_id,
            by.user_id,
        ),
    )


async def _firm(seed: Seeder, admin: Person, *labels: str) -> Firm:
    sites = tuple([await seed.site(admin.tenant_id, admin.user_id, label) for label in labels])
    items = {s.engagement_id: await _work_item(seed, s, admin) for s in sites}
    return Firm(admin.tenant_id, sites, items)


def _predicate(
    ctx: AuthContext, kind: str
) -> tuple[ColumnElement[uuid.UUID], ColumnElement[bool]]:
    """The listed id and `visible()` for the kind, as a repository list declares it."""
    action = ACTION[kind]
    scope = cast(VisibleScopeKind, kind)
    if kind == "engagement":
        return ENGAGEMENTS.c.id, visible_scope(ctx, action, scope, ENGAGEMENTS.c.id)
    if kind == "work_item":
        return WORK_ITEMS.c.id, visible_scope(ctx, action, scope, WORK_ITEMS.c.engagement_id)
    if kind == "client":
        return CLIENTS.c.id, visible_scope(ctx, action, scope, CLIENTS.c.id)
    if kind == "client_entity":
        return ENTITIES.c.id, visible_scope(ctx, action, scope, ENTITIES.c.client_id)
    return ENGAGEMENTS.c.id, visible_scope(
        ctx, action, scope, ENGAGEMENTS.c.id, grant_kind="engagement"
    )


async def _visible(ctx: AuthContext, kind: str) -> set[uuid.UUID]:
    listed, predicate = _predicate(ctx, kind)
    async with tenant_session(ctx.tenant) as session:
        found = await session.execute(select(listed).where(predicate))
        return set(found.scalars())


async def _authorised(
    ctx: AuthContext, kind: str, engagement: uuid.UUID, client: uuid.UUID
) -> bool:
    resource = Resource.engagement(ctx.tenant_id, engagement, archived=False, client_id=client)
    try:
        await authorise(ctx, ACTION[kind], resource)
    except Forbidden:
        return False
    return True


async def _oracle(ctx: AuthContext, kind: str, firm: Firm) -> set[uuid.UUID]:
    """ADR-145's rule, decided row by row with `authorise` on the row's engagements."""
    allowed: set[uuid.UUID] = set()
    for row in firm.rows(kind):
        for engagement, client in row.engagements:
            if await _authorised(ctx, kind, engagement, client):
                allowed.add(row.id)
                break
    return allowed


@dataclass(frozen=True)
class World:
    net: Net
    firm: Firm  # two engagements of two clients: sites[0] (ours) and sites[1] (another)
    other: Firm  # another firm with one engagement
    admin: Person
    senior: Person  # senior on sites[0] only
    walled: Person  # senior on sites[0], walled off its client
    outsider: Person  # a member with no role anywhere
    owner: Person  # client admin (owner grant) of sites[0]'s engagement
    traveller: Person  # no role in this firm; senior on the other firm's engagement

    @property
    def ours(self) -> Site:
        return self.firm.sites[0]

    @property
    def theirs(self) -> Site:
        return self.other.sites[0]

    def personas(self, kind: str) -> dict[str, AuthContext]:
        people = {
            "admin": _admin_ctx(self.admin),
            "senior": _ctx(self.senior),
            "walled": _ctx(self.walled),
            "outsider": _ctx(self.outsider),
            "traveller": _ctx(self.traveller, self.firm.tenant),
        }
        if kind == "portal_scope":
            people["owner"] = _ctx(self.owner, client=True)
        return people


@pytest.fixture
async def world(seed: Seeder, net: Net) -> World:
    tenant = await seed.firm()
    admin = await seed.person(tenant, "firm_admin")
    firm = await _firm(seed, admin, "t021-ours", "t021-another")
    senior = await seed.person(tenant)
    walled = await seed.person(tenant)
    outsider = await seed.person(tenant)
    await seed.member(firm.sites[0], senior, "senior")
    await seed.member(firm.sites[0], walled, "senior")
    await net.wall(admin, walled, firm.sites[0])
    owner = await seed.client_contact(firm.sites[0])

    other_tenant = await seed.firm()
    other_admin = await seed.person(other_tenant, "firm_admin")
    other = await _firm(seed, other_admin, "t021-elsewhere")
    traveller = await seed.person(tenant, also=other_tenant)
    there = Person(traveller.user_id, other_tenant, traveller.subject)
    await seed.member(other.sites[0], there, "senior")
    return World(net, firm, other, admin, senior, walled, outsider, owner, traveller)


def _row(world: World, kind: str, site: Site) -> uuid.UUID:
    firm = world.firm if site.tenant_id == world.firm.tenant else world.other
    return {
        "engagement": site.engagement_id,
        "portal_scope": site.engagement_id,
        "work_item": firm.work_items.get(site.engagement_id, uuid.uuid4()),
        "client": site.client_id,
        "client_entity": site.entity_id,
    }[kind]


# --- allow, deny, wall and cross-tenant per kind -----------------------------------------------


@pytest.mark.parametrize("kind", FIRM_KINDS)
async def test_p06_allow_a_team_member_lists_their_engagements_row(
    world: World, kind: str
) -> None:
    assert await _visible(_ctx(world.senior), kind) == {_row(world, kind, world.ours)}


@pytest.mark.parametrize("kind", FIRM_KINDS)
async def test_p06_deny_a_member_with_no_role_lists_nothing(world: World, kind: str) -> None:
    assert await _visible(_ctx(world.outsider), kind) == set()


@pytest.mark.parametrize("kind", FIRM_KINDS)
async def test_p06_deny_a_team_member_sees_no_row_of_another_client(
    world: World, kind: str
) -> None:
    another = world.firm.sites[1]
    assert _row(world, kind, another) not in await _visible(_ctx(world.senior), kind)


@pytest.mark.parametrize("kind", ["engagement", "client", "client_entity"])
async def test_p06_deny_a_firm_admin_reads_no_content_by_firm_role(
    world: World, kind: str
) -> None:
    """ADR-024: firm admins hold no content read; `engagement.read` names no firm role."""
    assert await _visible(_admin_ctx(world.admin), kind) == set()


async def test_p06_allow_a_firm_admin_lists_every_work_item_by_firm_role(world: World) -> None:
    """`work_item.read_metadata` allows `firm_admin` outright: every work item of the firm."""
    expected = set(world.firm.work_items.values())
    assert await _visible(_admin_ctx(world.admin), "work_item") == expected


@pytest.mark.parametrize("kind", KINDS)
async def test_p06_wall_a_walled_person_sees_nothing_of_the_client_through_any_kind(
    world: World, kind: str
) -> None:
    ctx = _ctx(world.walled)
    assert _row(world, kind, world.ours) not in await _visible(ctx, kind)
    assert not await _authorised(ctx, kind, world.ours.engagement_id, world.ours.client_id)


@pytest.mark.parametrize("kind", KINDS)
async def test_p06_cross_tenant_a_role_in_another_firm_shows_nothing_here(
    world: World, kind: str
) -> None:
    here = _ctx(world.traveller, world.firm.tenant)
    assert await _visible(here, kind) == set()
    there = _ctx(world.traveller, world.other.tenant)
    theirs = _row(world, kind, world.theirs)
    if kind != "portal_scope":  # the traveller is staff there, not a client user
        assert await _visible(there, kind) == {theirs}  # the positive control
    # The other firm's row through this firm's context: never authorised.
    resource = Resource.engagement(
        world.other.tenant,
        world.theirs.engagement_id,
        archived=False,
        client_id=world.theirs.client_id,
    )
    with pytest.raises(Forbidden):
        await authorise(here, ACTION[kind], resource)


async def test_p06_allow_portal_scope_a_client_owner_sees_their_granted_engagement(
    world: World,
) -> None:
    owner = _ctx(world.owner, client=True)
    assert await _visible(owner, "portal_scope") == {world.ours.engagement_id}


@pytest.mark.parametrize("who", ["senior", "outsider", "admin"])
async def test_p06_deny_portal_scope_firm_staff_hold_no_portal_grant(
    world: World, who: str
) -> None:
    ctx = _admin_ctx(world.admin) if who == "admin" else _ctx(cast(Person, getattr(world, who)))
    assert await _visible(ctx, "portal_scope") == set()


async def test_p06_cross_tenant_portal_scope_a_grant_in_one_firm_opens_nothing_in_another(
    world: World, seed: Seeder
) -> None:
    owner_there = await seed.client_contact(world.theirs)
    here = _ctx(Person(owner_there.user_id, world.firm.tenant, owner_there.subject), client=True)
    assert await _visible(here, "portal_scope") == set()
    there = _ctx(owner_there, client=True)
    assert await _visible(there, "portal_scope") == {world.theirs.engagement_id}


# --- the property: visible() agrees with authorise() --------------------------------------------


@pytest.mark.parametrize("kind", KINDS)
async def test_p06_property_visible_agrees_with_authorise_for_every_persona_and_row(
    world: World, kind: str
) -> None:
    """Exhaustive over this world's personas and every row of the firm: a row is listed exactly
    when `authorise` allows the kind's action on (one of) the row's engagement(s)."""
    disagreements: list[str] = []
    for name, ctx in world.personas(kind).items():
        listed = await _visible(ctx, kind)
        expected = await _oracle(ctx, kind, world.firm)
        if listed != expected:
            disagreements.append(f"{name}: visible {sorted(listed)} authorise {sorted(expected)}")
    assert disagreements == []
