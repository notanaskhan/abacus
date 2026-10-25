# ac-test-author: notanaskhan (G-01-T08; ADR-078's independent suite is G-01-T15)
"""G-01-T08 against Postgres (G-01 AC7.1 to AC7.4; DEC-30): offices with code, HQ, address,
lead and reviewer pool, and derived seats; registered office facts; unique codes and one HQ;
teams and groups with rosters kept as insert-only history; service lines that follow a person's
service-line teams; the Seasonal group's one date with an audit row per member; and no office
value in any authorisation decision.

Expectations come from G-01 section 3.7 and 4.2, not from the implementation."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from typing import cast

import pytest
from sqlalchemy import text

import abacus.modules.engagements.api  # registers the engagement-to-client lookup
import abacus.modules.organisations.api  # registers member teams, the office list and facts
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.identity import people
from abacus.modules.identity.api import (
    AuthContext,
    Forbidden,
    Resource,
    agent_context_for_run,
    allowed_actions,
)
from abacus.modules.organisations import org_structure, slots
from abacus.modules.organisations.org_structure import (
    OfficeCodeTaken,
    OneHq,
    OrgStructureInvalid,
    StaleOrgStructure,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.organisations.api
assert abacus.modules.engagements.api


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def _ctx(tenant: uuid.UUID, user: uuid.UUID, firm_role: str | None) -> AuthContext:
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


class Firm:
    def __init__(self, seed: Seeder, tenant: uuid.UUID) -> None:
        self.seed = seed
        self.tenant = tenant

    async def person(
        self,
        name: str,
        *,
        firm_role: str | None = None,
        level: str | None = "staff",
        office: uuid.UUID | None = None,
        lines: list[str] | None = None,
        ends: date | None = None,
    ) -> AuthContext:
        user = cast(
            uuid.UUID,
            await self.seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, $3) RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex[:10]}@example.test",
                name,
            ),
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level, office_id, "
            "service_lines, access_ends_on) VALUES ($1, $2, $3, 'active', $4, $5, $6, $7)",
            self.tenant,
            user,
            firm_role,
            level,
            office,
            lines or [],
            ends,
        )
        return _ctx(self.tenant, user, firm_role)

    async def lines(self, who: AuthContext) -> list[str]:
        return list(
            cast(
                list[str],
                await self.seed.value(
                    "SELECT service_lines FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                    self.tenant,
                    who.user_id,
                ),
            )
        )

    async def audit(self, action: str) -> list[dict[str, object]]:
        rows = await self.seed.rows(
            "SELECT actor_id, target_type, target_id::text AS target_id, after_ref::text AS a "
            "FROM audit_events WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant,
            action,
        )
        return [dict(r) for r in rows]


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    return Firm(seed, await seed.firm())


class _Picks:
    """A small deterministic sequence for the property tests (reproducible, not for secrets)."""

    def __init__(self, seed: int) -> None:
        self.state = seed

    def below(self, n: int) -> int:
        self.state = (self.state * 1103515245 + 12345) % 2**31
        return self.state % n

    def choice[T](self, items: list[T]) -> T:
        return items[self.below(len(items))]

    def chance(self, percent: int) -> bool:
        return self.below(100) < percent


def _office(name: str, code: str, **more: object) -> dict[str, object]:
    values: dict[str, object] = {
        "name": name,
        "code": code,
        "is_hq": False,
        "time_zone": "America/Chicago",
        "address_line1": None,
        "address_line2": None,
        "city": None,
        "region_code": None,
        "postal_code": None,
        "lead_user_id": None,
        "default_reviewer_pool_team_id": None,
    }
    return values | more


def _team(name: str, kind: str = "custom", line: str | None = None) -> dict[str, object]:
    return {
        "name": name,
        "kind": kind,
        "service_line": line,
        "office_id": None,
        "lead_user_id": None,
    }


# --- AC7.1: offices ------------------------------------------------------------------------------


async def test_ac7_1_offices_read_hq_first_with_address_lead_code_pool_and_derived_seats(
    firm: Firm,
) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    margaret = await firm.person("Margaret Okonkwo", level="partner")
    pool = await org_structure.create_team(grace, _team("EQR pool", "eqr_pool"))
    denver = await org_structure.create_office(
        grace, _office("Denver", "DEN", time_zone="America/Denver")
    )
    chicago = await org_structure.create_office(
        grace,
        _office(
            "Chicago",
            "CHI",
            is_hq=True,
            address_line1="311 West Brannock Street",
            address_line2="Suite 1700",
            city="Chicago",
            region_code="IL",
            postal_code="60606",
            lead_user_id=margaret.user_id,
            default_reviewer_pool_team_id=pool.id,
        ),
    )
    for _ in range(3):
        await firm.person("Chicago staff", office=chicago.id)
    await firm.person("Denver staff", office=denver.id)
    gone = await firm.person("Left", office=chicago.id)
    await firm.seed.run(
        "UPDATE memberships SET status = 'revoked', revoked_at = now() WHERE user_id = $1",
        gone.user_id,
    )
    found = await org_structure.list_offices(grace)
    assert [(o.code, o.is_hq, o.seats) for o in found] == [("CHI", True, 3), ("DEN", False, 1)]
    hq = found[0]
    assert (hq.address_line1, hq.address_line2, hq.city, hq.region_code, hq.postal_code) == (
        "311 West Brannock Street",
        "Suite 1700",
        "Chicago",
        "IL",
        "60606",
    )
    assert hq.lead_user_id == margaret.user_id
    assert hq.default_reviewer_pool_team_id == pool.id
    assert hq.time_zone == "America/Chicago"
    assert hq.allowed_actions == ["org_structure.manage"]
    # A partner reads offices (they are filters) but cannot manage them.
    read = await org_structure.list_offices(margaret)
    assert [o.code for o in read] == ["CHI", "DEN"]
    assert read[0].allowed_actions == []


async def test_ac7_1_registered_office_facts_appear_and_a_failing_one_is_left_out(
    firm: Firm, monkeypatch: pytest.MonkeyPatch
) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    chicago = await org_structure.create_office(grace, _office("Chicago", "CHI"))

    async def returns(_tenant: object) -> dict[uuid.UUID, int]:
        return {chicago.id: 98}

    async def fails(_tenant: object) -> dict[uuid.UUID, int]:
        raise RuntimeError("provider down")

    monkeypatch.setattr(slots, "_OFFICE_FACTS", {"ty2025_returns": returns, "broken": fails})
    [office] = await org_structure.list_offices(grace)
    assert office.facts == {"ty2025_returns": 98}
    monkeypatch.setattr(slots, "_OFFICE_FACTS", {})
    [bare] = await org_structure.list_offices(grace)
    assert bare.facts == {}


# --- AC7.2: unique codes, one HQ, IANA zones, versions, DEC-30 -----------------------------------


async def test_ac7_2_office_codes_are_unique_per_firm(firm: Firm, seed: Seeder) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    await org_structure.create_office(grace, _office("Chicago", "CHI"))
    with pytest.raises(OfficeCodeTaken):
        await org_structure.create_office(grace, _office("Chicago Loop", "CHI"))
    other = Firm(seed, await seed.firm())
    admin = await other.person("Other admin", firm_role="firm_admin", level="admin")
    assert (await org_structure.create_office(admin, _office("Chicago", "CHI"))).code == "CHI"


async def test_ac7_2_exactly_one_office_is_hq(firm: Firm) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    chicago = await org_structure.create_office(grace, _office("Chicago", "CHI", is_hq=True))
    with pytest.raises(OneHq):
        await org_structure.create_office(grace, _office("Denver", "DEN", is_hq=True))
    denver = await org_structure.create_office(grace, _office("Denver", "DEN"))
    with pytest.raises(OneHq):
        await org_structure.update_office(
            grace, denver.id, denver.version, _office("Denver", "DEN", is_hq=True)
        )
    # Moving the HQ: clear it, then set it elsewhere.
    await org_structure.update_office(
        grace, chicago.id, chicago.version, _office("Chicago", "CHI")
    )
    moved = await org_structure.update_office(
        grace, denver.id, denver.version, _office("Denver", "DEN", is_hq=True)
    )
    assert moved.is_hq
    assert moved.version == denver.version + 1
    updated = await firm.audit("office.updated")  # the refused write left no row
    assert [e["target_id"] for e in updated] == [str(chicago.id), str(denver.id)]


async def test_ac7_2_time_zones_are_iana_names_and_leads_are_active_staff(firm: Firm) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    with pytest.raises(OrgStructureInvalid) as refused:
        await org_structure.create_office(grace, _office("Mars", "MRS", time_zone="Mars/Olympus"))
    assert refused.value.facts == {"field": "time_zone"}
    with pytest.raises(OrgStructureInvalid):
        await org_structure.create_office(
            grace, _office("Denver", "DEN", lead_user_id=uuid.uuid4())
        )


async def test_ac7_2_a_stale_version_is_409_and_nothing_changes(firm: Firm) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    office = await org_structure.create_office(grace, _office("Chicago", "CHI"))
    await org_structure.update_office(grace, office.id, 0, _office("Chicago", "CHI", city="X"))
    with pytest.raises(StaleOrgStructure):
        await org_structure.update_office(grace, office.id, 0, _office("Chicago", "CHG"))
    assert (await org_structure.office(grace, office.id)).code == "CHI"
    with pytest.raises(NotFound):
        await org_structure.update_office(grace, uuid.uuid4(), 0, _office("Chicago", "CHI"))


async def test_ac7_2_only_firm_and_security_admins_manage_and_never_an_agent(
    firm: Firm, seed: Seeder
) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    felix = await firm.person("Felix Andersen", firm_role="security_admin", level="admin")
    daniel = await firm.person("Daniel Reyes", level="partner")
    kevin = await firm.person("Kevin Osei")
    assert (await org_structure.create_office(felix, _office("Denver", "DEN"))).code == "DEN"
    for who in (daniel, kevin):
        with pytest.raises(Forbidden):
            await org_structure.create_office(who, _office("Boston", "BOS"))
    with pytest.raises(Forbidden):
        await org_structure.list_offices(kevin)
    stale = AuthContext(
        tenant=grace.tenant,
        user_id=grace.user_id,
        membership_id=grace.membership_id,
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC) - timedelta(minutes=30),
    )
    with pytest.raises(Forbidden):
        await org_structure.create_office(stale, _office("Boston", "BOS"))
    entity = await seed.entity(firm.tenant)
    engagement = await seed.engagement(firm.tenant, entity, grace.user_id)
    run = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
            "initiator_user_id, task_scope, status) VALUES ($1, 'evidence.screener', 1, $2, $3, "
            "'{}', 'running') RETURNING id",
            firm.tenant,
            engagement,
            grace.user_id,
        ),
    )
    agent = await agent_context_for_run(
        tenant_id=firm.tenant,
        run_id=run,
        agent_id="evidence.screener",
        engagement_id=engagement,
        task_scope=frozenset(),
        initiator_user_id=grace.user_id,
    )
    from abacus.modules.identity.api import authorise

    with pytest.raises(Forbidden):
        await authorise(agent, "org_structure.manage", Resource.firm(firm.tenant))


async def test_ac7_2_dec30_no_office_value_changes_an_authorisation_decision(
    firm: Firm, seed: Seeder
) -> None:
    """DEC-30: `allowed_actions` on an engagement is the same whichever offices the person and
    the engagement are in (a property over random assignments)."""
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    offices = [
        (await org_structure.create_office(grace, _office(name, code))).id
        for name, code in (("Chicago", "CHI"), ("Denver", "DEN"), ("New York", "NYC"))
    ]
    entity = await seed.entity(firm.tenant)
    engagement = await seed.engagement(firm.tenant, entity, grace.user_id)
    people_by_role: list[tuple[AuthContext, str | None]] = []
    for role in ("engagement_partner", "manager", "staff", None):
        who = await firm.person(f"Member {role}")
        if role is not None:
            await seed.run(
                "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
                "VALUES ($1, $2, $3, $4)",
                firm.tenant,
                engagement,
                who.user_id,
                role,
            )
        people_by_role.append((who, role))
    people_by_role.append((grace, "firm_admin"))
    resource = Resource.engagement(firm.tenant, engagement, archived=False)
    baseline = {who.user_id: await allowed_actions(who, resource) for who, _ in people_by_role}
    rng = _Picks(30)
    for _ in range(4):
        await seed.run(
            "UPDATE engagements SET office_id = $1 WHERE id = $2", rng.choice(offices), engagement
        )
        for who, _ in people_by_role:
            await seed.run(
                "UPDATE memberships SET office_id = $1 WHERE tenant_id = $2 AND user_id = $3",
                rng.choice([*offices, None]),
                firm.tenant,
                who.user_id,
            )
        for who, _ in people_by_role:
            assert await allowed_actions(who, resource) == baseline[who.user_id]


async def test_ac7_2_an_office_inserted_without_a_code_takes_one_from_its_name(
    firm: Firm, seed: Seeder
) -> None:
    """0150's rule for older callers: the first three letters, then a free fourth letter."""
    for name in ("Chicago", "Chicago Loop", "Ny"):
        await seed.run(
            "INSERT INTO offices (tenant_id, name, time_zone) VALUES ($1, $2, 'America/Chicago')",
            firm.tenant,
            name,
        )
    rows = await seed.rows(
        "SELECT name, code FROM offices WHERE tenant_id = $1 ORDER BY name", firm.tenant
    )
    assert [(r["name"], r["code"]) for r in rows] == [
        ("Chicago", "CHI"),
        ("Chicago Loop", "CHIB"),
        ("Ny", "NYX"),
    ]


# --- AC7.3: teams, groups and the seasonal date --------------------------------------------------


async def test_ac7_3_teams_and_groups_list_with_their_rosters(firm: Firm) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    tw = await firm.person("Theo Walsh", level="partner")
    cm = await firm.person("Carmen Mills", level="partner")
    eqr = await org_structure.create_team(grace, _team("EQR pool", "eqr_pool"))
    done = await org_structure.set_team_members(grace, eqr.id, [tw.user_id, cm.user_id])
    assert done.member_ids == [tw.user_id, cm.user_id]
    assert done.version == eqr.version + 1
    teams = await org_structure.list_teams(grace)
    assert [(t.name, t.kind, len(t.member_ids)) for t in teams] == [("EQR pool", "eqr_pool", 2)]
    added = await firm.audit("team.member_added")
    assert [e["target_id"] for e in added] == [str(eqr.id), str(eqr.id)]
    with pytest.raises(OrgStructureInvalid):
        await org_structure.set_team_members(grace, eqr.id, [uuid.uuid4()])


async def test_ac7_3_a_service_line_team_names_its_line_and_only_it_does(firm: Firm) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    with pytest.raises(OrgStructureInvalid):
        await org_structure.create_team(grace, _team("Tax", "service_line"))
    with pytest.raises(OrgStructureInvalid):
        await org_structure.create_team(grace, _team("Pool", "eqr_pool", "tax"))


async def test_ac7_3_rosters_are_insert_only_history(firm: Firm, seed: Seeder) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    kevin = await firm.person("Kevin Osei")
    team = await org_structure.create_team(
        grace, _team("Monitoring reviewers", "monitoring_reviewers")
    )
    await org_structure.set_team_members(grace, team.id, [kevin.user_id])
    await org_structure.set_team_members(grace, team.id, [])
    await org_structure.set_team_members(grace, team.id, [kevin.user_id])
    rows = await seed.rows(
        "SELECT removed_at IS NOT NULL AS removed FROM team_rosters WHERE team_id = $1 "
        "ORDER BY seq",
        team.id,
    )
    assert [r["removed"] for r in rows] == [False, True, False]
    assert (await org_structure.team(grace, team.id)).member_ids == [kevin.user_id]
    assert len(await firm.audit("team.member_removed")) == 1


async def test_ac7_3_the_seasonal_date_sets_every_seasonal_member_with_one_audit_row_each(
    firm: Firm,
) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    seasonal = [
        await firm.person(f"Seasonal {n}", level="seasonal", ends=date(2026, 10, 31))
        for n in range(5)
    ]
    kevin = await firm.person("Kevin Osei")
    done = await org_structure.set_seasonal_group_date(grace, date(2026, 11, 15))
    assert (done.access_ends_on, done.members) == (date(2026, 11, 15), 5)
    rows = await firm.seed.rows(
        "SELECT user_id, access_ends_on FROM memberships WHERE tenant_id = $1 "
        "AND access_ends_on IS NOT NULL",
        firm.tenant,
    )
    assert {r["user_id"] for r in rows} == {p.user_id for p in seasonal}
    assert {r["access_ends_on"] for r in rows} == {date(2026, 11, 15)}
    events = await firm.audit("membership.attributes_changed")
    assert sorted(str(e["target_id"]) for e in events) == sorted(str(p.user_id) for p in seasonal)
    assert all(e["actor_id"] == str(grace.user_id) for e in events)
    with pytest.raises(Forbidden):
        await org_structure.set_seasonal_group_date(kevin, date(2026, 11, 15))


# --- AC7.4: service lines follow service-line teams ----------------------------------------------


async def test_ac7_4_joining_and_leaving_a_service_line_team_moves_the_line(firm: Firm) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    kevin = await firm.person("Kevin Osei", lines=["advisory"])
    tax = await org_structure.create_team(grace, _team("Tax", "service_line", "tax"))
    await org_structure.set_team_members(grace, tax.id, [kevin.user_id])
    assert await firm.lines(kevin) == ["tax", "advisory"]
    await org_structure.set_team_members(grace, tax.id, [])
    assert await firm.lines(kevin) == ["advisory"]  # a line no team manages is left as set


async def test_ac7_4_a_person_edit_that_disagrees_with_their_teams_is_refused(firm: Firm) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    kevin = await firm.person("Kevin Osei")
    tax = await org_structure.create_team(grace, _team("Tax", "service_line", "tax"))
    await org_structure.create_team(grace, _team("Audit & assurance", "service_line", "audit"))
    await people.update_person(grace, kevin.user_id, 1, {"team_ids": [tax.id]})
    assert await firm.lines(kevin) == ["tax"]
    version = cast(
        int,
        await firm.seed.value("SELECT version FROM memberships WHERE user_id = $1", kevin.user_id),
    )  # the edit, then the line the team gave him (each versioned)
    with pytest.raises(people.PersonInvalid) as refused:
        await people.update_person(
            grace, kevin.user_id, version, {"service_lines": ["audit", "tax"]}
        )
    assert refused.value.facts == {"field": "service_lines"}
    assert await firm.lines(kevin) == ["tax"]


async def test_ac7_4_property_lines_and_teams_never_disagree(firm: Firm) -> None:
    """Random roster, person and team edits: afterwards every member holds a managed line
    exactly when one of their service-line teams does."""
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    staff = [await firm.person(f"Staff {n}") for n in range(4)]
    teams = [
        await org_structure.create_team(grace, _team("Audit", "service_line", "audit")),
        await org_structure.create_team(grace, _team("Tax", "service_line", "tax")),
        await org_structure.create_team(grace, _team("Tax Denver", "service_line", "tax")),
        await org_structure.create_team(grace, _team("Ops", "practice_group")),
    ]
    rng = _Picks(74)
    for _ in range(25):
        step = rng.below(3)
        if step == 0:
            team = rng.choice(teams)
            members = [p.user_id for p in staff if rng.chance(50)]
            await org_structure.set_team_members(grace, team.id, members)
        elif step == 1:
            who = rng.choice(staff)
            row = await firm.seed.value(
                "SELECT version FROM memberships WHERE user_id = $1", who.user_id
            )
            picked = [t.id for t in teams if rng.chance(40)]
            await people.update_person(grace, who.user_id, cast(int, row), {"team_ids": picked})
        else:
            team = (await org_structure.list_teams(grace))[rng.below(len(teams))]
            line = rng.choice(["audit", "tax", "cas", None])
            kind = "practice_group" if line is None else "service_line"
            await org_structure.update_team(
                grace, team.id, team.version, _team(team.name, kind, line)
            )
        current = {t.id: t for t in await org_structure.list_teams(grace)}
        managed = {t.service_line for t in current.values() if t.kind == "service_line"}
        for who in staff:
            held = {
                t.service_line
                for t in current.values()
                if t.kind == "service_line" and who.user_id in t.member_ids
            }
            assert set(await firm.lines(who)) & managed == held


# --- security review (G-01-T08): service-line teams are people management ------------------------


async def test_review_a_security_admin_cannot_change_who_holds_a_service_line(firm: Firm) -> None:
    """Service lines drive `in_scope` for practice leaders and quality partners, so anything
    that moves them needs `firm.manage_users` (a firm admin), as setting them directly does;
    a security admin manages offices and other teams only."""
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    felix = await firm.person("Felix Andersen", firm_role="security_admin", level="admin")
    kevin = await firm.person("Kevin Osei")
    with pytest.raises(Forbidden):
        await org_structure.create_team(felix, _team("Tax", "service_line", "tax"))
    pool = await org_structure.create_team(felix, _team("EQR pool", "eqr_pool"))  # not a line
    with pytest.raises(Forbidden):
        await org_structure.update_team(
            felix, pool.id, pool.version, _team("EQR pool", "service_line", "audit")
        )
    tax = await org_structure.create_team(grace, _team("Tax", "service_line", "tax"))
    with pytest.raises(Forbidden):
        await org_structure.set_team_members(felix, tax.id, [kevin.user_id])
    with pytest.raises(Forbidden):
        await org_structure.update_team(felix, tax.id, tax.version, _team("Tax", "custom"))
    assert await firm.lines(kevin) == []
    await org_structure.set_team_members(felix, pool.id, [kevin.user_id])  # still allowed
    await org_structure.set_team_members(grace, tax.id, [kevin.user_id])
    assert await firm.lines(kevin) == ["tax"]


async def test_review_a_line_moved_by_a_team_is_audited_versioned_and_ends_cached_access(
    firm: Firm,
) -> None:
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    kevin = await firm.person("Kevin Osei")
    tax = await org_structure.create_team(grace, _team("Tax", "service_line", "tax"))
    before = await firm.seed.value(
        "SELECT version FROM memberships WHERE user_id = $1", kevin.user_id
    )
    await org_structure.set_team_members(grace, tax.id, [kevin.user_id])
    after = await firm.seed.value(
        "SELECT version FROM memberships WHERE user_id = $1", kevin.user_id
    )
    assert after == cast(int, before) + 1
    events = [
        e
        for e in await firm.audit("membership.attributes_changed")
        if e["target_id"] == str(kevin.user_id)
    ]
    assert len(events) == 1
    assert "service_lines" in str(events[0]["a"])
    changed = await firm.seed.rows(
        "SELECT payload->>'user_id' AS u FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'access.changed'",
        firm.tenant,
    )
    assert str(kevin.user_id) in [r["u"] for r in changed]


# --- security review (0150): the default-code trigger function -----------------------------------


async def test_review_the_default_code_function_pins_its_search_path_and_is_not_public(
    firm: Firm, seed: Seeder
) -> None:
    config = await seed.value(
        "SELECT proconfig FROM pg_proc WHERE proname = 'offices_default_code'"
    )
    assert "search_path=pg_catalog, public, pg_temp" in cast(list[str], config)
    assert (
        await seed.value(
            "SELECT has_function_privilege('abacus_app', 'offices_default_code()', 'EXECUTE')"
        )
        is False
    )
    # The trigger still fires for the app role (EXECUTE is checked when a trigger is created).
    grace = await firm.person("Grace Holloway", firm_role="firm_admin", level="admin")
    async with uow(grace.tenant) as tx:
        await tx.session.execute(
            text(
                "INSERT INTO offices (tenant_id, name, time_zone) "
                "VALUES (:t, 'Boston', 'America/New_York')"
            ),
            {"t": firm.tenant},
        )
        tx.record("office.created", target=Target("office", firm.tenant))
    assert await seed.value("SELECT code FROM offices WHERE tenant_id = $1", firm.tenant) == "BOS"
