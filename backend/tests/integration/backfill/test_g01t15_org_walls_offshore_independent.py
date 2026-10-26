# ac-test-author: ayushkbhatia
"""G-01 AC7.1 to AC7.4, AC8.1 to AC8.7, AC9.1 to AC9.4, AC11.2; SPEC-002 AC-4 to AC-10 and AC-12
to AC-20 (G-01-T08, G-01-T09; G-01-T15): offices, teams and groups, walls v2 and offshore, read
from G-01 §3.7 to §3.9 and §4.3, SPEC-002 Stories 2, 3 and 5, the contract
`docs/contracts/firm-settings.md`, the identity and organisations permission matrices, and
DEC-30, DEC-43, DEC-73, DEC-317, DEC-318 and DEC-319 as amended by TASK-1207. Expectations come
from the specification, never from the implementation.

HTTP through `create_app()` against the migrated Postgres, with `firm_settings.v2` on; the agent
and system principals through `identity.api.authorise` and the compiled matrix `RULES`.
Decisions followed instead of the epic's wording:
- DEC-30 and the contract §2: one action pair, `org_structure.read`/`org_structure.manage`,
  covers offices and teams (the epic's `office.*`/`team.*`).
- DEC-317: offices and teams carry `version` (422 without on PATCH, 409 `stale_version`); a
  service-line team's roster is people management (`firm.manage_users`), so a security admin
  cannot change who holds a line.
- DEC-318: `wall.remove` is partners only; an approver must be an active partner other than the
  walled person and the creator (422 `approver_not_partner`); a partner does not see walls on
  themself or on clients hidden from them.
- DEC-319 as amended by TASK-1207 (G-01 AC9.1, AC9.2; SPEC-002 AC-18): offshore is not a wall.
  An offshore member reads by role; only `not_offshore` actions are refused (403); assignment
  fails closed with 409 `offshore_consent_required`; TINs reach them masked.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Final, cast

import asyncpg
import httpx
import pytest

from abacus.kernel.db import TenantContext
from abacus.kernel.uow import OutboxEvent, uow
from abacus.modules.identity.api import (
    RULES,
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    end_assignments_for_wall,
    engagement_resource,
)
from abacus.modules.identity.context import (
    _ISSUER,  # pyright: ignore[reportPrivateUsage] -- a test-only agent principal
)
from abacus.modules.organisations.api import seal_tin

from .support import Net, Person, Seeder, Site

pytestmark = pytest.mark.asyncio

Json = dict[str, object]
FLAG: Final = "firm_settings.v2"
NOT_FOUND: Final = {"detail": "not found"}
OFFICES: Final = "/v1/firm/offices"
TEAMS: Final = "/v1/firm/teams"
STAFF: Final = "/v1/firm/staff"
WALLS: Final = "/v1/walls"
# A fake EIN (9x campus prefix; the repository is public).
EIN: Final = "90-0000287"
EIN_DIGITS: Final = "900000287"
# G-01 §4.3 and the contract §2: every write this family adds, each denied to agent and system.
NEW_WRITES: Final = (
    "org_structure.manage",
    "firm.manage_users",
    "wall.create",
    "wall.approve",
    "wall.remove",
)


# ================================================================================================
# The firm: Brightwater Hale's cast, synthetic
# ================================================================================================


@dataclass(frozen=True)
class Firm:
    net: Net
    seed: Seeder
    tenant_id: uuid.UUID
    grace: Person  # Grace Holloway: firm admin
    margaret: Person  # Margaret Okonkwo: partner, the named approver
    daniel: Person  # Daniel Reyes: partner
    neil: Person  # Neil Ashcroft: Ashford's relationship partner
    lena: Person  # Lena Park: seasonal, walled from Ashford in the story
    kevin: Person  # Kevin Osei: staff, no firm role
    ashford: Site
    ridgeline: Site

    async def person(
        self,
        firm_role: str | None = None,
        *,
        level: str = "staff",
        offshore: bool = False,
        ends: date | None = None,
    ) -> Person:
        who = await self.seed.person(self.tenant_id, firm_role)
        await self.seed.run(
            "UPDATE memberships SET level = $3, offshore = $4, access_ends_on = $5 "
            "WHERE tenant_id = $1 AND user_id = $2",
            self.tenant_id,
            who.user_id,
            level,
            offshore,
            ends if ends is not None else (date(2027, 10, 31) if level == "seasonal" else None),
        )
        return who

    async def call(
        self,
        method: str,
        path: str,
        who: Person,
        body: Json | None = None,
        *,
        mfa: bool = True,
    ) -> httpx.Response:
        return await self.net.call(method, path, who, body=body, mfa=mfa)

    async def audit(self, action: str) -> list[asyncpg.Record]:
        return await self.seed.rows(
            "SELECT actor_kind, actor_id, on_behalf_of_user_id, target_id::text AS target_id, "
            "coalesce(before_ref::text, '') || coalesce(after_ref::text, '') AS refs "
            "FROM audit_events WHERE tenant_id = $1 AND action = $2 ORDER BY seq",
            self.tenant_id,
            action,
        )

    async def outbox(self, event_type: str) -> list[Json]:
        rows = await self.seed.rows(
            "SELECT payload FROM outbox WHERE tenant_id = $1 AND event_type = $2 "
            "ORDER BY occurred_at, id",
            self.tenant_id,
            event_type,
        )
        return [
            cast(Json, json.loads(r["payload"]) if isinstance(r["payload"], str) else r["payload"])
            for r in rows
        ]

    async def access_changed_for(self, who: Person) -> int:
        return len(
            [p for p in await self.outbox("access.changed") if str(who.user_id) in json.dumps(p)]
        )

    async def membership(self, who: Person) -> asyncpg.Record:
        return (
            await self.seed.rows(
                "SELECT status, office_id, service_lines, offshore, access_ends_on, version "
                "FROM memberships WHERE tenant_id = $1 AND user_id = $2",
                self.tenant_id,
                who.user_id,
            )
        )[0]

    def auth(self, who: Person, firm_role: str | None = None) -> AuthContext:
        return AuthContext(
            TenantContext(self.tenant_id, "human", str(who.user_id)),
            who.user_id,
            uuid.uuid4(),
            cast(None, firm_role),
            datetime.now(UTC) - timedelta(minutes=1),
        )


async def _flag(seed: Seeder, tenant: uuid.UUID, flag: str = FLAG) -> None:
    await seed.run(
        "INSERT INTO feature_flag_states (tenant_id, flag, value, set_by, reason) "
        "VALUES ($1, $2, 'true', 'test-seed', 'G-01-T15')",
        tenant,
        flag,
    )


async def _firm(net: Net) -> Firm:
    seed = net.seed
    tenant = await seed.firm()
    await _flag(seed, tenant)
    grace = await seed.person(tenant, "firm_admin")
    await seed.run(
        "UPDATE memberships SET level = 'admin' WHERE tenant_id = $1 AND user_id = $2",
        tenant,
        grace.user_id,
    )
    ashford = await seed.site(tenant, grace.user_id, "Ashford")
    ridgeline = await seed.site(tenant, grace.user_id, "Ridgeline")
    partial = Firm(net, seed, tenant, grace, grace, grace, grace, grace, grace, ashford, ridgeline)
    margaret = await partial.person(level="partner")
    daniel = await partial.person(level="partner")
    neil = await partial.person(level="partner")
    lena = await partial.person(level="seasonal")
    kevin = await partial.person()
    for site in (ashford, ridgeline):
        await seed.member(site, margaret, "engagement_partner")
        await seed.member(site, daniel, "manager")
        await seed.member(site, lena, "staff")
    await seed.run(
        "UPDATE clients SET relationship_partner_id = $2 WHERE id = $1",
        ashford.client_id,
        neil.user_id,
    )
    return Firm(net, seed, tenant, grace, margaret, daniel, neil, lena, kevin, ashford, ridgeline)


@pytest.fixture
async def firm(net: Net) -> Firm:
    return await _firm(net)


class _Sequence:
    """A reproducible pseudo-random sequence for the property tests (a linear congruential
    generator: the same seed walks the same cases on every run)."""

    def __init__(self, seed: int) -> None:
        self._state = seed

    def _next(self) -> int:
        self._state = (self._state * 6364136223846793005 + 1442695040888963407) % 2**64
        return self._state >> 33

    def random(self) -> float:
        return self._next() / 2**31

    def choice[T](self, items: Sequence[T]) -> T:
        return items[self._next() % len(items)]

    def sample[T](self, items: Sequence[T], count: int) -> list[T]:
        pool = list(items)
        return [pool.pop(self._next() % len(pool)) for _ in range(count)]


def _body(response: httpx.Response, *status: int) -> Json:
    assert response.status_code in (status or (200,)), response.text
    return cast(Json, response.json())


def _detail(response: httpx.Response) -> object:
    return cast(Json, response.json()).get("detail")


def _keys(value: object) -> Iterator[str]:
    if isinstance(value, dict):
        for key, inner in cast(Json, value).items():
            yield key
            yield from _keys(inner)
    elif isinstance(value, list):
        for inner in cast(list[object], value):
            yield from _keys(inner)


def _no_hidden(value: object) -> None:
    """AC8.7, DEC-43: no `hidden`, `hidden_count` or other hidden-derived field anywhere."""
    assert not [k for k in _keys(value) if "hidden" in k.lower()], value


def _agent(
    firm: Firm, initiator: Person, actions: tuple[str, ...], engagement: uuid.UUID | None
) -> AgentContext:
    person = firm.auth(initiator, "firm_admin" if initiator == firm.grace else None)
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(firm.tenant_id, "agent", f"agent:probe:{run}", initiator.user_id),
        agent_id="probe",
        agent_run_id=run,
        engagement_id=engagement,
        task_scope=frozenset(actions),
        initiator=person,
        issued_by=_ISSUER,
    )


async def _office(firm: Firm, code: str, *, hq: bool = False, **extra: object) -> httpx.Response:
    body: Json = {
        "name": f"Office {code} {uuid.uuid4().hex[:4]}",
        "code": code,
        "is_hq": hq,
        "time_zone": "America/Chicago",
        **extra,
    }
    return await firm.call("POST", OFFICES, firm.grace, body)


async def _offices(firm: Firm, who: Person | None = None) -> list[Json]:
    return cast(list[Json], await _list(firm, OFFICES, who or firm.grace))


async def _list(firm: Firm, path: str, who: Person) -> object:
    response = await firm.call("GET", path, who)
    assert response.status_code == 200, response.text
    return response.json()


# ================================================================================================
# Offices (AC7.1, AC7.2; DEC-317)
# ================================================================================================


async def test_ac7_2_office_codes_are_unique_per_firm_and_not_across_firms(
    firm: Firm, net: Net
) -> None:
    first = await _office(firm, "CHI", hq=True)
    assert first.status_code in (200, 201), first.text
    taken = await _office(firm, "CHI")
    assert taken.status_code == 409, taken.text
    assert _detail(taken) == "office_code_taken"
    assert [o["code"] for o in await _offices(firm)].count("CHI") == 1
    # Another firm uses CHI freely: the code is unique per firm only.
    other = await _firm(net)
    elsewhere = await _office(other, "CHI", hq=True)
    assert elsewhere.status_code in (200, 201), elsewhere.text
    # A code is two to six capital letters.
    for bad in ("chi", "C", "CHICAGO", "CH1"):
        refused = await _office(firm, bad)
        assert refused.status_code == 422, (bad, refused.text)


async def test_ac7_2_exactly_one_office_is_hq_on_create_and_on_patch(firm: Firm) -> None:
    chicago = _body(await _office(firm, "CHI", hq=True), 200, 201)
    second = await _office(firm, "NYC", hq=True)
    assert second.status_code == 409, second.text
    assert _detail(second) == "one_hq"
    denver = _body(await _office(firm, "DEN"), 200, 201)
    patched = await firm.call(
        "PATCH",
        f"{OFFICES}/{denver['id']}",
        firm.grace,
        {
            "version": denver["version"],
            "name": denver["name"],
            "code": "DEN",
            "is_hq": True,
            "time_zone": "America/Denver",
        },
    )
    assert patched.status_code == 409, patched.text
    assert _detail(patched) == "one_hq"
    hqs = [o["id"] for o in await _offices(firm) if o["is_hq"]]
    assert hqs == [chicago["id"]]
    # Database too: a second HQ row can't exist (the partial unique index).
    with pytest.raises(asyncpg.UniqueViolationError):
        await firm.seed.run(
            "UPDATE offices SET is_hq = true WHERE tenant_id = $1 AND id = $2",
            firm.tenant_id,
            uuid.UUID(str(denver["id"])),
        )


async def test_ac7_2_time_zones_are_iana_names(firm: Firm) -> None:
    refused = await _office(firm, "MRS", time_zone="Mars/Olympus_Mons")
    assert refused.status_code == 422, refused.text
    accepted = await _office(firm, "DEN", time_zone="America/Denver")
    assert accepted.status_code in (200, 201), accepted.text
    assert _body(accepted, 200, 201)["time_zone"] == "America/Denver"


async def test_ac7_1_seats_are_derived_from_memberships_and_the_lead_and_address_read_back(
    firm: Firm,
) -> None:
    created = _body(
        await _office(
            firm,
            "CHI",
            hq=True,
            address_line1="311 West Brannock Street",
            address_line2="Suite 1700",
            city="Chicago",
            region_code="IL",
            postal_code="60606",
            lead_user_id=str(firm.margaret.user_id),
        ),
        200,
        201,
    )
    for who in (firm.kevin, firm.lena):
        await firm.seed.run(
            "UPDATE memberships SET office_id = $3 WHERE tenant_id = $1 AND user_id = $2",
            firm.tenant_id,
            who.user_id,
            uuid.UUID(str(created["id"])),
        )
    [chicago] = [o for o in await _offices(firm) if o["id"] == created["id"]]
    assert chicago["seats"] == 2
    assert chicago["lead_user_id"] == str(firm.margaret.user_id)
    assert (chicago["address_line1"], chicago["city"], chicago["postal_code"]) == (
        "311 West Brannock Street",
        "Chicago",
        "60606",
    )
    # A revoked membership holds no seat.
    await firm.seed.revoke(firm.lena)
    [chicago] = [o for o in await _offices(firm) if o["id"] == created["id"]]
    assert chicago["seats"] == 1


async def test_ac7_2_a_patch_needs_the_version_and_a_stale_one_is_409(firm: Firm) -> None:
    office = _body(await _office(firm, "CHI", hq=True), 200, 201)
    path = f"{OFFICES}/{office['id']}"
    values: Json = {
        "name": "Chicago",
        "code": "CHI",
        "is_hq": True,
        "time_zone": "America/Chicago",
    }
    missing = await firm.call("PATCH", path, firm.grace, values)
    assert missing.status_code == 422, missing.text
    saved = await firm.call("PATCH", path, firm.grace, {**values, "version": office["version"]})
    assert saved.status_code == 200, saved.text
    stale = await firm.call(
        "PATCH", path, firm.grace, {**values, "name": "Chicago Loop", "version": office["version"]}
    )
    assert stale.status_code == 409, stale.text
    assert _detail(stale) == "stale_version"
    [row] = [o for o in await _offices(firm) if o["id"] == office["id"]]
    assert row["name"] == "Chicago"
    actions = [r["actor_id"] for r in await firm.audit("office.updated")]
    assert actions == [str(firm.grace.user_id)]
    assert [r["actor_id"] for r in await firm.audit("office.created")] == [str(firm.grace.user_id)]


async def test_ac7_2_who_reads_and_who_manages_offices_and_teams(firm: Firm) -> None:
    felix = await firm.person("security_admin", level="admin")
    by_felix = await firm.call(
        "POST",
        OFFICES,
        felix,
        {"name": "Denver", "code": "DEN", "time_zone": "America/Denver"},
    )
    assert by_felix.status_code in (200, 201), by_felix.text
    # A partner reads the structure and cannot change it (AC11.2: fieldset A locked).
    rows = await _offices(firm, firm.daniel)
    assert rows and all(
        "org_structure.manage" not in cast(list[str], o["allowed_actions"]) for o in rows
    )
    for who in (firm.daniel, firm.kevin):
        refused = await firm.call(
            "POST",
            OFFICES,
            who,
            {"name": "New York", "code": "NYC", "time_zone": "America/New_York"},
        )
        assert refused.status_code in (403, 404), refused.text
        team = await firm.call("POST", TEAMS, who, {"name": "Tax", "kind": "practice_group"})
        assert team.status_code in (403, 404), team.text
    staff_read = await firm.call("GET", OFFICES, firm.kevin)
    assert staff_read.status_code in (403, 404), staff_read.text
    # Fresh MFA for a write.
    stale = await firm.call(
        "POST",
        OFFICES,
        firm.grace,
        {"name": "New York", "code": "NYC", "time_zone": "America/New_York"},
        mfa=False,
    )
    assert stale.status_code == 403, stale.text
    assert [o["code"] for o in await _offices(firm)] == ["DEN"]


async def test_ac7_2_another_firms_office_and_team_answer_404_and_never_list(
    firm: Firm, net: Net
) -> None:
    other = await _firm(net)
    theirs = _body(await _office(other, "LON", hq=True), 200, 201)
    their_team = _body(
        await other.call("POST", TEAMS, other.grace, {"name": "Theirs", "kind": "custom"}),
        200,
        201,
    )
    assert theirs["id"] not in [o["id"] for o in await _offices(firm)]
    teams = cast(list[Json], await _list(firm, TEAMS, firm.grace))
    assert their_team["id"] not in [t["id"] for t in teams]
    patch = await firm.call(
        "PATCH",
        f"{OFFICES}/{theirs['id']}",
        firm.grace,
        {"version": theirs["version"], "name": "Mine", "code": "LON", "time_zone": "UTC"},
    )
    assert patch.status_code == 404, patch.text
    assert patch.json() == NOT_FOUND
    members = await firm.call(
        "PUT", f"{TEAMS}/{their_team['id']}/members", firm.grace, {"member_ids": []}
    )
    assert members.status_code == 404, members.text
    # Their person never joins our team.
    ours = _body(
        await firm.call("POST", TEAMS, firm.grace, {"name": "Ours", "kind": "custom"}), 200, 201
    )
    stranger = await other.person()
    joined = await firm.call(
        "PUT",
        f"{TEAMS}/{ours['id']}/members",
        firm.grace,
        {"member_ids": [str(stranger.user_id)]},
    )
    assert joined.status_code in (404, 422), joined.text
    [row] = [
        t for t in cast(list[Json], await _list(firm, TEAMS, firm.grace)) if t["id"] == ours["id"]
    ]
    assert row["member_ids"] == []


# ================================================================================================
# DEC-30: no office value ever takes part in an authorisation decision (AC7.2 property)
# ================================================================================================


async def _decisions(
    firm: Firm, principals: list[tuple[Person, str | None]], actions: list[str]
) -> dict[tuple[str, str, str], str]:
    resources = {
        "firm": Resource.firm(firm.tenant_id),
        "ashford": await engagement_resource(
            TenantContext(firm.tenant_id, "human", "probe"), firm.ashford.engagement_id
        ),
        "ridgeline": await engagement_resource(
            TenantContext(firm.tenant_id, "human", "probe"), firm.ridgeline.engagement_id
        ),
    }
    out: dict[tuple[str, str, str], str] = {}
    for who, role in principals:
        ctx = firm.auth(who, role)
        for name, resource in resources.items():
            for action in actions:
                try:
                    await authorise(ctx, action, resource)
                    outcome = "allow"
                except Exception as refused:
                    outcome = type(refused).__name__
                out[(str(who.user_id), name, action)] = outcome
    return out


async def _engagement_lists(firm: Firm, people: list[Person]) -> dict[str, list[str]]:
    lists: dict[str, list[str]] = {}
    for who in people:
        response = await firm.call("GET", "/v1/engagements", who)
        lists[str(who.user_id)] = (
            sorted(str(e["id"]) for e in cast(list[Json], response.json()))
            if response.status_code == 200
            else [f"status {response.status_code}"]
        )
    return lists


async def test_ac7_2_dec30_authorise_and_lists_are_invariant_to_every_office_value(
    firm: Firm,
) -> None:
    pl = await firm.person("practice_leader", level="partner")
    qp = await firm.person("quality_partner", level="partner")
    felix = await firm.person("security_admin", level="admin")
    principals: list[tuple[Person, str | None]] = [
        (firm.grace, "firm_admin"),
        (pl, "practice_leader"),
        (qp, "quality_partner"),
        (felix, "security_admin"),
        (firm.margaret, None),
        (firm.lena, None),
        (firm.kevin, None),
    ]
    rng = _Sequence(30)  # DEC-30
    actions = sorted(RULES)
    sample = sorted({*rng.sample(actions, min(40, len(actions))), *NEW_WRITES})
    people = [p for p, _ in principals]
    before = await _decisions(firm, principals, sample)
    lists_before = await _engagement_lists(firm, people)

    codes = ["CHI", "DEN", "NYC"]
    offices = [
        uuid.UUID(str(_body(await _office(firm, code, hq=code == "CHI"), 200, 201)["id"]))
        for code in codes
    ]
    for round_no in range(2):
        # Every office value moves: memberships, engagements, leads and the HQ.
        for who in people:
            await firm.seed.run(
                "UPDATE memberships SET office_id = $3 WHERE tenant_id = $1 AND user_id = $2",
                firm.tenant_id,
                who.user_id,
                rng.choice([*offices, None]),
            )
        for site in (firm.ashford, firm.ridgeline):
            await firm.seed.run(
                "UPDATE engagements SET office_id = $2 WHERE id = $1",
                site.engagement_id,
                rng.choice([*offices, None]),
            )
        await firm.seed.run(
            "UPDATE offices SET lead_user_id = $2 WHERE tenant_id = $1",
            firm.tenant_id,
            rng.choice(people).user_id,
        )
        after = await _decisions(firm, principals, sample)
        drift = {k: (before[k], after[k]) for k in before if before[k] != after[k]}
        assert drift == {}, (round_no, drift)
        assert await _engagement_lists(firm, people) == lists_before, round_no


async def test_ac7_2_dec30_no_matrix_rule_names_an_office() -> None:
    """The contract §2: no matrix rule names an office; offices and teams share one pair."""
    assert not [a for a in RULES if a.startswith("office.")]
    assert "org_structure.manage" in RULES and "org_structure.read" in RULES
    for action, rule in RULES.items():
        assert not [k for k in rule.decisions if "office" in k], action


# ================================================================================================
# Teams, groups and the service-line sync (AC7.3, AC7.4; DEC-317)
# ================================================================================================


async def _team(firm: Firm, name: str, kind: str, line: str | None = None) -> Json:
    body: Json = {"name": name, "kind": kind}
    if line is not None:
        body["service_line"] = line
    return _body(await firm.call("POST", TEAMS, firm.grace, body), 200, 201)


async def _roster(
    firm: Firm, team: Json, members: list[Person], who: Person | None = None
) -> httpx.Response:
    return await firm.call(
        "PUT",
        f"{TEAMS}/{team['id']}/members",
        who or firm.grace,
        {"member_ids": [str(m.user_id) for m in members]},
    )


async def test_ac7_3_a_service_line_team_names_its_line_and_only_it_does(firm: Firm) -> None:
    missing = await firm.call("POST", TEAMS, firm.grace, {"name": "Tax", "kind": "service_line"})
    assert missing.status_code == 422, missing.text
    stray = await firm.call(
        "POST",
        TEAMS,
        firm.grace,
        {"name": "EQR pool", "kind": "eqr_pool", "service_line": "tax"},
    )
    assert stray.status_code == 422, stray.text
    # The F-03 `offshore` and `wall_group` kinds are gone (offshore and walls are per person).
    for gone in ("offshore", "wall_group"):
        refused = await firm.call("POST", TEAMS, firm.grace, {"name": gone, "kind": gone})
        assert refused.status_code == 422, refused.text
    tax = await _team(firm, "Tax", "service_line", "tax")
    assert (tax["kind"], tax["service_line"]) == ("service_line", "tax")
    duplicate = await firm.call(
        "POST", TEAMS, firm.grace, {"name": "Tax", "kind": "service_line", "service_line": "tax"}
    )
    assert duplicate.status_code == 409, duplicate.text
    assert _detail(duplicate) == "team_name_taken"
    assert [r["actor_id"] for r in await firm.audit("team.created")] == [str(firm.grace.user_id)]


async def test_ac7_4_joining_and_leaving_a_service_line_team_moves_the_line_in_one_step(
    firm: Firm,
) -> None:
    tax = await _team(firm, "Tax", "service_line", "tax")
    joined = await _roster(firm, tax, [firm.kevin])
    assert joined.status_code == 200, joined.text
    assert list((await firm.membership(firm.kevin))["service_lines"]) == ["tax"]
    person = _body(await firm.call("GET", f"{STAFF}/{firm.kevin.user_id}", firm.grace))
    assert cast(Json, person["row"])["service_lines"] == ["tax"]
    assert [r["actor_id"] for r in await firm.audit("team.member_added")] == [
        str(firm.grace.user_id)
    ]
    assert await firm.access_changed_for(firm.kevin) >= 1
    left = await _roster(firm, tax, [])
    assert left.status_code == 200, left.text
    assert list((await firm.membership(firm.kevin))["service_lines"]) == []
    assert [r["actor_id"] for r in await firm.audit("team.member_removed")] == [
        str(firm.grace.user_id)
    ]
    assert await firm.access_changed_for(firm.kevin) >= 2


async def test_ac7_3_rosters_keep_their_history_a_removal_is_a_new_row(firm: Firm) -> None:
    group = await _team(firm, "Monitoring reviewers", "monitoring_reviewers")
    counts: list[int] = []
    for members in ([firm.kevin, firm.lena], [firm.kevin], [firm.kevin, firm.lena]):
        assert (await _roster(firm, group, members)).status_code == 200
        counts.append(
            int(
                str(
                    await firm.seed.value(
                        "SELECT count(*) FROM team_rosters WHERE tenant_id = $1 AND team_id = $2",
                        firm.tenant_id,
                        uuid.UUID(str(group["id"])),
                    )
                )
            )
        )
    assert counts[0] < counts[1] < counts[2]  # insert-only: every change adds a row
    teams = cast(list[Json], await _list(firm, TEAMS, firm.grace))
    [row] = [t for t in teams if t["id"] == group["id"]]
    assert sorted(cast(list[str], row["member_ids"])) == sorted(
        [str(firm.kevin.user_id), str(firm.lena.user_id)]
    )


async def test_ac7_4_property_service_lines_and_service_line_teams_never_disagree(
    firm: Firm,
) -> None:
    tax = await _team(firm, "Tax", "service_line", "tax")
    tax_two = await _team(firm, "Tax Denver", "service_line", "tax")
    cas = await _team(firm, "CAS", "service_line", "cas")
    other = await _team(firm, "Firm operations", "practice_group")
    people = [firm.kevin, firm.lena, firm.daniel, await firm.person()]
    teams = {"tax": tax, "tax2": tax_two, "cas": cas, "ops": other}
    lines = {"tax": "tax", "tax2": "tax", "cas": "cas", "ops": None}
    rosters: dict[str, set[uuid.UUID]] = {k: set() for k in teams}
    rng = _Sequence(74)
    for step in range(14):
        key = rng.choice(list(teams))
        roster = rosters[key]
        while roster == rosters[key]:  # a change each step (a no-op PUT has its own test)
            roster = {p.user_id for p in people if rng.random() < 0.5}
        rosters[key] = roster
        changed = await firm.call(
            "PUT",
            f"{TEAMS}/{teams[key]['id']}/members",
            firm.grace,
            {"member_ids": [str(u) for u in sorted(rosters[key])]},
        )
        assert changed.status_code == 200, (step, changed.text)
        for who in people:
            expected = {lines[k] for k, members in rosters.items() if who.user_id in members}
            expected.discard(None)
            held = set((await firm.membership(who))["service_lines"])
            # A managed line (tax, cas) is held exactly when one of the person's teams holds it.
            assert held & {"tax", "cas"} == expected, (step, who.user_id, held, expected)


async def test_ac7_3_putting_the_same_roster_again_changes_nothing_and_answers_200(
    firm: Firm,
) -> None:
    """`PUT …/members` sets the whole roster: the same roster twice is the same state."""
    for kind, line in (("service_line", "tax"), ("monitoring_reviewers", None)):
        team = await _team(firm, f"Team {kind}", kind, line)
        for members in ([firm.kevin], [firm.kevin], [], []):
            response = await _roster(firm, team, members)
            assert response.status_code == 200, (kind, members, response.text)
    assert list((await firm.membership(firm.kevin))["service_lines"]) == []
    assert len(await firm.audit("team.member_added")) == 2
    assert len(await firm.audit("team.member_removed")) == 2


async def test_ac7_4_a_person_edit_asking_for_a_line_their_teams_dont_hold_is_refused(
    firm: Firm,
) -> None:
    await _team(firm, "Tax", "service_line", "tax")  # the line is now managed by a team
    person = _body(await firm.call("GET", f"{STAFF}/{firm.kevin.user_id}", firm.grace))
    refused = await firm.call(
        "PATCH",
        f"{STAFF}/{firm.kevin.user_id}",
        firm.grace,
        {"version": person["version"], "service_lines": ["tax"]},
    )
    assert refused.status_code == 422, refused.text
    assert _detail(refused) == "person_invalid"
    assert list((await firm.membership(firm.kevin))["service_lines"]) == []


async def test_ac7_4_dec317_a_security_admin_cannot_change_who_holds_a_line(firm: Firm) -> None:
    felix = await firm.person("security_admin", level="admin")
    tax = await _team(firm, "Tax", "service_line", "tax")
    refused = await _roster(firm, tax, [firm.kevin], who=felix)
    assert refused.status_code == 403, refused.text
    assert list((await firm.membership(firm.kevin))["service_lines"]) == []
    made = await firm.call(
        "POST", TEAMS, felix, {"name": "CAS", "kind": "service_line", "service_line": "cas"}
    )
    assert made.status_code == 403, made.text
    # A team without a line stays a security admin's to manage.
    plain = await firm.call("POST", TEAMS, felix, {"name": "Reviewers", "kind": "reviewer_pool"})
    assert plain.status_code in (200, 201), plain.text


async def test_ac7_3_the_seasonal_date_sets_every_active_seasonal_member_one_audit_row_each(
    firm: Firm,
) -> None:
    others = [await firm.person(level="seasonal") for _ in range(2)]
    gone = await firm.person(level="seasonal", ends=date(2027, 6, 30))
    await firm.seed.revoke(gone)
    seasonal = [firm.lena, *others]
    path = "/v1/firm/groups/seasonal/access-ends"
    stale = await firm.call("PUT", path, firm.grace, {"access_ends_on": "2027-10-31"}, mfa=False)
    assert stale.status_code == 403, stale.text
    by_partner = await firm.call("PUT", path, firm.daniel, {"access_ends_on": "2027-10-31"})
    assert by_partner.status_code == 403, by_partner.text
    saved = _body(await firm.call("PUT", path, firm.grace, {"access_ends_on": "2027-10-31"}))
    assert saved["members"] == len(seasonal)
    for who in seasonal:
        assert (await firm.membership(who))["access_ends_on"] == date(2027, 10, 31)
    assert (await firm.membership(firm.kevin))["access_ends_on"] is None
    assert (await firm.membership(gone))["access_ends_on"] == date(2027, 6, 30)
    rows = await firm.audit("membership.attributes_changed")
    assert len(rows) == len(seasonal)  # one audit row per member
    assert {r["actor_id"] for r in rows} == {str(firm.grace.user_id)}


# ================================================================================================
# Walls v2: create at once, approver, blockers, preview (AC8.1, AC8.3; SPEC-002 AC-12 to AC-14)
# ================================================================================================


async def _wall(
    firm: Firm,
    who: Person,
    site: Site,
    *,
    by: Person | None = None,
    approver: Person | None = None,
    reason: str = "personal_relationship",
    text: str | None = "Family member employed at the client",
    mfa: bool = True,
) -> httpx.Response:
    body: Json = {
        "user_id": str(who.user_id),
        "client_id": str(site.client_id),
        "reason_code": reason,
    }
    if text is not None:
        body["reason_text"] = text
    if approver is not None:
        body["approver_user_id"] = str(approver.user_id)
    return await firm.call("POST", WALLS, by or firm.grace, body, mfa=mfa)


async def test_ac8_1_grace_walls_lena_from_ashford_active_at_once_awaiting_margaret(
    firm: Firm,
) -> None:
    engagement = f"/v1/engagements/{firm.ashford.engagement_id}"
    assert (await firm.call("GET", engagement, firm.lena)).status_code == 200
    created = await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret)
    wall = _body(created, 201)
    assert (wall["status"], wall["approval_status"]) == ("active", "awaiting")
    assert (wall["reason_code"], wall["approver_user_id"]) == (
        "personal_relationship",
        str(firm.margaret.user_id),
    )
    assert wall["created_by"] == str(firm.grace.user_id)
    # `wall.created` names the approver; the walled person's access.changed is emitted.
    [event] = await firm.outbox("wall.created")
    assert str(firm.margaret.user_id) in json.dumps(event)
    assert "Family member" not in json.dumps(event)  # identifier-only payloads
    [audited] = await firm.audit("wall.created")
    assert (audited["actor_kind"], audited["actor_id"]) == ("human", str(firm.grace.user_id))
    assert await firm.access_changed_for(firm.lena) >= 1
    # From Lena's next request (before any consumer runs): 404 exactly as an unknown id.
    unknown = await firm.call("GET", f"/v1/engagements/{uuid.uuid4()}", firm.lena)
    for tail in ("", "/request-items", "/team", "/work-items"):
        walled = await firm.call("GET", f"{engagement}{tail}", firm.lena)
        assert walled.status_code == 404, (tail, walled.text)
        assert walled.json() == unknown.json() == NOT_FOUND, tail
    listed = cast(list[Json], await _list(firm, "/v1/engagements", firm.lena))
    ids = [e["id"] for e in listed]
    assert str(firm.ashford.engagement_id) not in ids
    assert str(firm.ridgeline.engagement_id) in ids  # SPEC-002 AC-8: the rest is unchanged
    assert firm.ashford.marker not in json.dumps(listed)
    _no_hidden(listed)
    # Ridgeline's content still reads.
    items = await firm.call(
        "GET", f"/v1/engagements/{firm.ridgeline.engagement_id}/request-items", firm.lena
    )
    assert items.status_code == 200, items.text


async def test_ac8_1_spec002_ac6_a_later_engagement_of_the_client_is_walled_too(
    firm: Firm,
) -> None:
    assert (await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret)).status_code == 201
    later = cast(
        uuid.UUID,
        await firm.seed.value(
            "INSERT INTO engagements (tenant_id, client_id, client_entity_id, name, "
            "fiscal_period_start, fiscal_period_end, created_by) VALUES ($1, $2, $3, $4, "
            "'2026-01-01', '2026-12-31', $5) RETURNING id",
            firm.tenant_id,
            firm.ashford.client_id,
            firm.ashford.entity_id,
            f"Engagement {firm.ashford.marker} 2026",
            firm.grace.user_id,
        ),
    )
    await firm.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'staff')",
        firm.tenant_id,
        later,
        firm.lena.user_id,
    )
    response = await firm.call("GET", f"/v1/engagements/{later}", firm.lena)
    assert response.status_code == 404, response.text
    assert response.json() == NOT_FOUND


async def test_ac8_1_spec002_ac7_an_agent_acting_for_lena_is_refused_on_ashford_only(
    firm: Firm,
) -> None:
    assert (await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret)).status_code == 201
    tenant = TenantContext(firm.tenant_id, "human", "probe")
    for site, refused in ((firm.ashford, True), (firm.ridgeline, False)):
        agent = _agent(firm, firm.lena, ("request_item.read",), site.engagement_id)
        resource = await engagement_resource(tenant, site.engagement_id)
        if refused:
            with pytest.raises(Exception) as caught:
                await authorise(agent, "request_item.read", resource)
            assert type(caught.value).__name__ in ("Forbidden", "NotFound")
        else:
            await authorise(agent, "request_item.read", resource)


async def test_ac8_1_who_may_create_a_wall_and_the_reason_rules(firm: Firm) -> None:
    by_staff = await _wall(firm, firm.lena, firm.ashford, by=firm.kevin, approver=firm.margaret)
    assert by_staff.status_code == 403, by_staff.text
    stale = await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret, mfa=False)
    assert stale.status_code == 403, stale.text
    felix = await firm.person("security_admin", level="admin")
    by_felix = await _wall(firm, firm.lena, firm.ashford, by=felix, approver=firm.margaret)
    assert by_felix.status_code == 403, by_felix.text  # security admins list, never create
    bad_reason = await _wall(firm, firm.lena, firm.ashford, reason="grudge")
    assert bad_reason.status_code == 422, bad_reason.text
    too_long = await _wall(firm, firm.lena, firm.ashford, text="x" * 501)
    assert too_long.status_code == 422, too_long.text
    assert await firm.audit("wall.created") == []
    # A partner may wall too (DEC-73); the reason defaults to `other`.
    by_partner = await firm.call(
        "POST",
        WALLS,
        firm.daniel,
        {
            "user_id": str(firm.kevin.user_id),
            "client_id": str(firm.ridgeline.client_id),
            "approver_user_id": str(firm.margaret.user_id),
        },
    )
    wall = _body(by_partner, 201)
    assert (wall["reason_code"], wall["status"]) == ("other", "active")


async def test_ac12_the_named_approver_must_be_an_active_partner_other_than_walled_and_creator(
    firm: Firm,
) -> None:
    gone = await firm.person(level="partner")
    await firm.seed.revoke(gone)
    for approver in (firm.kevin, firm.grace, gone):
        refused = await _wall(firm, firm.lena, firm.ashford, approver=approver)
        assert refused.status_code == 422, (approver, refused.text)
        assert _detail(refused) == "approver_not_partner"
    # The walled partner can't approve their own wall; nor can its creator.
    self_named = await _wall(firm, firm.daniel, firm.ridgeline, approver=firm.daniel)
    assert self_named.status_code == 422, self_named.text
    assert _detail(self_named) == "approver_not_partner"
    creator_named = await _wall(
        firm, firm.kevin, firm.ridgeline, by=firm.margaret, approver=firm.margaret
    )
    assert creator_named.status_code == 422, creator_named.text
    assert _detail(creator_named) == "approver_not_partner"
    assert await firm.audit("wall.created") == []


async def test_ac8_3_neil_ashcroft_the_relationship_partner_is_a_blocker_and_409(
    firm: Firm,
) -> None:
    preview = _body(
        await firm.call(
            "GET",
            f"{WALLS}/preview?user_id={firm.neil.user_id}&client_id={firm.ashford.client_id}",
            firm.grace,
        )
    )
    assert "relationship_partner" in cast(list[str], preview["blockers"])
    refused = await _wall(firm, firm.neil, firm.ashford, approver=firm.margaret)
    assert refused.status_code == 409, refused.text
    assert _detail(refused) == "relationship_partner"
    assert await firm.audit("wall.created") == []
    # Neil is not Ridgeline's relationship partner: walling him there is allowed.
    elsewhere = await _wall(firm, firm.neil, firm.ridgeline, approver=firm.margaret)
    assert elsewhere.status_code == 201, elsewhere.text


async def test_ac8_3_a_duplicate_active_wall_is_a_blocker_and_409_wall_exists(firm: Firm) -> None:
    assert (await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret)).status_code == 201
    path = f"{WALLS}/preview?user_id={firm.lena.user_id}&client_id={firm.ashford.client_id}"
    assert "wall_exists" in cast(
        list[str], _body(await firm.call("GET", path, firm.grace))["blockers"]
    )
    again = await _wall(firm, firm.lena, firm.ashford, approver=firm.daniel)
    assert again.status_code == 409, again.text
    assert _detail(again) == "wall_exists"
    assert len(await firm.audit("wall.created")) == 1


async def test_ac14_the_preview_counts_assignments_on_that_client_only(firm: Firm) -> None:
    path = f"{WALLS}/preview?user_id={firm.lena.user_id}&client_id={firm.ashford.client_id}"
    preview = _body(await firm.call("GET", path, firm.grace))
    assert preview["blockers"] == []
    assert preview["assignments_ended"] == 1  # her one Ashford membership; Ridgeline's isn't
    nothing = _body(
        await firm.call(
            "GET",
            f"{WALLS}/preview?user_id={firm.kevin.user_id}&client_id={firm.ashford.client_id}",
            firm.grace,
        )
    )
    assert nothing["assignments_ended"] == 0
    _no_hidden(preview)


async def test_ac14_an_unseen_client_or_person_previews_as_unknown(firm: Firm, net: Net) -> None:
    other = await _firm(net)
    cases = [
        (firm.lena.user_id, uuid.uuid4()),
        (uuid.uuid4(), firm.ashford.client_id),
        (firm.lena.user_id, other.ashford.client_id),
        (other.lena.user_id, firm.ashford.client_id),
    ]
    for user_id, client_id in cases:
        response = await firm.call(
            "GET", f"{WALLS}/preview?user_id={user_id}&client_id={client_id}", firm.grace
        )
        assert response.status_code == 404, (user_id, client_id, response.text)
        assert response.json() == NOT_FOUND
    # A creator walled from the client learns nothing of it (DEC-43): the same 404.
    assert (
        await _wall(firm, firm.daniel, firm.ashford, approver=firm.margaret)
    ).status_code == 201
    walled = await firm.call(
        "GET",
        f"{WALLS}/preview?user_id={firm.kevin.user_id}&client_id={firm.ashford.client_id}",
        firm.daniel,
    )
    assert walled.status_code == 404, walled.text
    assert walled.json() == NOT_FOUND
    create = await _wall(firm, firm.kevin, firm.ashford, by=firm.daniel, approver=firm.margaret)
    assert create.status_code == 404, create.text
    # Another firm cannot wall our people from our clients.
    cross = await _wall(other, firm.lena, firm.ashford, approver=other.margaret)
    assert cross.status_code == 404, cross.text


# ================================================================================================
# Approval (AC8.2; SPEC-002 AC-15)
# ================================================================================================


async def test_ac8_2_only_margaret_approves_with_fresh_mfa_and_only_once(firm: Firm) -> None:
    wall = _body(await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret), 201)
    path = f"{WALLS}/{wall['id']}/approve"
    other_partner = await firm.call("POST", path, firm.daniel)
    assert other_partner.status_code == 403, other_partner.text
    assert _detail(other_partner) == "not_named_approver"
    by_grace = await firm.call("POST", path, firm.grace)  # Grace can't record it for her
    assert by_grace.status_code == 403, by_grace.text
    stale = await firm.call("POST", path, firm.margaret, mfa=False)
    assert stale.status_code == 403, stale.text
    assert await firm.audit("wall.approved") == []
    approved = _body(await firm.call("POST", path, firm.margaret))
    assert approved["approval_status"] == "approved"
    assert approved["approved_at"] is not None
    again = await firm.call("POST", path, firm.margaret)
    assert again.status_code == 409, again.text
    assert _detail(again) == "already_approved"
    [audited] = await firm.audit("wall.approved")
    assert (audited["actor_kind"], audited["actor_id"]) == ("human", str(firm.margaret.user_id))
    assert len(await firm.outbox("wall.approved")) == 1
    [row] = await firm.seed.rows(
        "SELECT approved_by, approved_at FROM ethical_walls WHERE id = $1",
        uuid.UUID(str(wall["id"])),
    )
    assert row["approved_by"] == firm.margaret.user_id
    # Forward-only in the database: the approval is never rewritten.
    with pytest.raises(asyncpg.PostgresError):
        await firm.seed.run(
            "UPDATE ethical_walls SET approved_by = $2, approved_at = now() WHERE id = $1",
            uuid.UUID(str(wall["id"])),
            firm.daniel.user_id,
        )
    with pytest.raises(asyncpg.PostgresError):
        await firm.seed.run(
            "UPDATE ethical_walls SET approved_by = NULL, approved_at = NULL WHERE id = $1",
            uuid.UUID(str(wall["id"])),
        )


async def test_ac15_a_wall_without_an_approver_is_approved_by_nobody(firm: Firm) -> None:
    wall = _body(await _wall(firm, firm.lena, firm.ashford), 201)
    assert wall["approval_status"] == "awaiting"
    for partner in (firm.margaret, firm.daniel):
        refused = await firm.call("POST", f"{WALLS}/{wall['id']}/approve", partner)
        assert refused.status_code == 403, refused.text
    assert await firm.audit("wall.approved") == []


async def test_ac15_a_lifted_wall_cannot_be_approved_and_answers_404(firm: Firm) -> None:
    wall = _body(await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret), 201)
    lifted = await firm.call(
        "POST", f"{WALLS}/{wall['id']}/remove", firm.daniel, {"reason": "Relative left Ashford"}
    )
    assert lifted.status_code == 200, lifted.text
    late = await firm.call("POST", f"{WALLS}/{wall['id']}/approve", firm.margaret)
    assert late.status_code == 404, late.text
    assert await firm.audit("wall.approved") == []
    with pytest.raises(asyncpg.PostgresError):  # never after removal, in the database too
        await firm.seed.run(
            "UPDATE ethical_walls SET approved_by = $2, approved_at = now() WHERE id = $1",
            uuid.UUID(str(wall["id"])),
            firm.margaret.user_id,
        )


# ================================================================================================
# Lift (AC8.4; SPEC-002 AC-9)
# ================================================================================================


async def test_ac8_4_a_partner_lifts_with_fresh_mfa_a_firm_admin_gets_403(firm: Firm) -> None:
    wall = _body(await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret), 201)
    path = f"{WALLS}/{wall['id']}/remove"
    by_grace = await firm.call("POST", path, firm.grace, {"reason": "Cleared"})
    assert by_grace.status_code == 403, by_grace.text
    by_staff = await firm.call("POST", path, firm.kevin, {"reason": "Cleared"})
    assert by_staff.status_code in (403, 404), by_staff.text
    stale = await firm.call("POST", path, firm.daniel, {"reason": "Cleared"}, mfa=False)
    assert stale.status_code == 403, stale.text
    assert await firm.audit("wall.removed") == []
    engagement = f"/v1/engagements/{firm.ashford.engagement_id}"
    assert (await firm.call("GET", engagement, firm.lena)).status_code == 404
    lifted = _body(await firm.call("POST", path, firm.daniel, {"reason": "Cleared"}))
    assert lifted["status"] == "removed"
    assert lifted["removed_by"] == str(firm.daniel.user_id)
    [audited] = await firm.audit("wall.removed")
    assert (audited["actor_kind"], audited["actor_id"]) == ("human", str(firm.daniel.user_id))
    # From the next request her access follows her roles again; the row keeps its history.
    assert (await firm.call("GET", engagement, firm.lena)).status_code == 200
    rows = cast(list[Json], await _list(firm, WALLS, firm.grace))
    [kept] = [w for w in rows if w["id"] == wall["id"]]
    assert (kept["status"], kept["created_by"]) == ("removed", str(firm.grace.user_id))
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM ethical_walls WHERE id = $1", uuid.UUID(str(wall["id"]))
        )
        == 1
    )
    assert await firm.access_changed_for(firm.lena) >= 2  # on create and on lift


async def test_ac8_4_a_partner_cannot_lift_a_wall_on_themself(firm: Firm) -> None:
    wall = _body(await _wall(firm, firm.daniel, firm.ashford, approver=firm.margaret), 201)
    own = await firm.call("POST", f"{WALLS}/{wall['id']}/remove", firm.daniel, {"reason": "Mine"})
    assert own.status_code == 409, own.text
    assert _detail(own) == "own_wall"
    by_margaret = await firm.call(
        "POST", f"{WALLS}/{wall['id']}/remove", firm.margaret, {"reason": "Cleared"}
    )
    assert by_margaret.status_code == 200, by_margaret.text


# ================================================================================================
# The register and its log (SPEC-002 AC-10, AC-17; AC8.6, AC8.7, AC11.2)
# ================================================================================================


async def test_ac10_admins_see_every_wall_a_partner_not_their_own_nor_a_hidden_client(
    firm: Firm,
) -> None:
    on_lena = _body(await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret), 201)
    on_daniel = _body(await _wall(firm, firm.daniel, firm.ashford, approver=firm.margaret), 201)
    on_kevin = _body(await _wall(firm, firm.kevin, firm.ridgeline, approver=firm.margaret), 201)
    every = {on_lena["id"], on_daniel["id"], on_kevin["id"]}
    felix = await firm.person("security_admin", level="admin")
    for reader in (firm.grace, felix):
        rows = cast(list[Json], await _list(firm, WALLS, reader))
        assert {w["id"] for w in rows} == every
        for w in rows:
            assert {"user_id", "client_id", "created_by", "created_at", "reason_code"} <= set(w)
            assert {"approver_user_id", "approval_status"} <= set(w)
        _no_hidden(rows)
    # Daniel: not his own wall, and nothing on Ashford (he is walled from it).
    seen = {w["id"] for w in cast(list[Json], await _list(firm, WALLS, firm.daniel))}
    assert seen == {on_kevin["id"]}
    for who in (firm.kevin, firm.lena):
        refused = await firm.call("GET", WALLS, who)
        assert refused.status_code == 403, refused.text
    stale = await firm.call("GET", WALLS, firm.grace, mfa=False)
    assert stale.status_code == 403, stale.text


async def test_ac11_2_a_partner_sees_approve_only_where_named_and_lift_except_their_own(
    firm: Firm,
) -> None:
    named_daniel = _body(await _wall(firm, firm.lena, firm.ridgeline, approver=firm.daniel), 201)
    named_margaret = _body(
        await _wall(firm, firm.kevin, firm.ridgeline, approver=firm.margaret), 201
    )
    rows = {
        w["id"]: cast(list[str], w["allowed_actions"])
        for w in cast(list[Json], await _list(firm, WALLS, firm.daniel))
    }
    assert "wall.approve" in rows[named_daniel["id"]]
    assert "wall.approve" not in rows[named_margaret["id"]]
    assert "wall.remove" in rows[named_margaret["id"]]
    grace_rows = {
        w["id"]: cast(list[str], w["allowed_actions"])
        for w in cast(list[Json], await _list(firm, WALLS, firm.grace))
    }
    assert "wall.approve" not in grace_rows[named_daniel["id"]]
    assert "wall.remove" not in grace_rows[named_daniel["id"]]


async def test_ac17_the_wall_log_is_newest_first_and_a_hidden_client_answers_404(
    firm: Firm, net: Net
) -> None:
    wall = _body(await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret), 201)
    assert (
        await firm.call("POST", f"{WALLS}/{wall['id']}/approve", firm.margaret)
    ).status_code == 200
    page = _body(await firm.call("GET", f"{WALLS}/{wall['id']}/events", firm.grace))
    events = cast(list[Json], page["items"])
    assert [(e["event_type"], e["actor_user_id"]) for e in events][:2] == [
        ("wall.approved", str(firm.margaret.user_id)),
        ("wall.created", str(firm.grace.user_id)),
    ]
    _no_hidden(page)
    # Daniel walled from Ashford: the log of a wall on Ashford is 404 like an unknown wall.
    assert (
        await _wall(firm, firm.daniel, firm.ashford, approver=firm.margaret)
    ).status_code == 201
    hidden = await firm.call("GET", f"{WALLS}/{wall['id']}/events", firm.daniel)
    unknown = await firm.call("GET", f"{WALLS}/{uuid.uuid4()}/events", firm.daniel)
    assert (hidden.status_code, unknown.status_code) == (404, 404), hidden.text
    assert hidden.json() == unknown.json() == NOT_FOUND
    staff = await firm.call("GET", f"{WALLS}/{wall['id']}/events", firm.kevin)
    assert staff.status_code in (403, 404), staff.text
    # Another firm's admin and partner find nothing of this wall.
    other = await _firm(net)
    for path, method in (
        (f"{WALLS}/{wall['id']}/events", "GET"),
        (f"{WALLS}/{wall['id']}/approve", "POST"),
        (f"{WALLS}/{wall['id']}/remove", "POST"),
    ):
        for who in (other.grace, other.margaret):
            cross = await other.call(method, path, who)
            assert cross.status_code in (403, 404), (path, cross.text)
            assert cross.status_code == 404 or who == other.grace, (path, cross.text)
    assert wall["id"] not in [
        w["id"] for w in cast(list[Json], await _list(other, WALLS, other.grace))
    ]
    [row] = await firm.seed.rows(
        "SELECT status, approved_by FROM ethical_walls WHERE id = $1", uuid.UUID(str(wall["id"]))
    )
    assert (row["status"], row["approved_by"]) == ("active", firm.margaret.user_id)


async def test_ac8_7_at_a_glance_shows_the_wall_count_only_to_wall_list_holders(
    firm: Firm,
) -> None:
    assert (await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret)).status_code == 201
    # A practice leader below partner level reads settings but holds no `wall.list`.
    pl = await firm.person("practice_leader", level="manager")

    async def glance(who: Person) -> Json:
        overview = _body(await firm.call("GET", "/v1/firm/settings/overview", who))
        _no_hidden(overview)
        rows = {cast(str, r["key"]): r for r in cast(list[Json], overview["at_a_glance"])}
        return cast(Json, rows["offices_teams"]["facts"])

    assert (await glance(firm.grace)).get("walls") == 1
    assert "walls" not in await glance(pl)


# ================================================================================================
# The wall consumer (AC8.5; SPEC-002 AC-16)
# ================================================================================================


async def test_ac8_5_access_is_denied_before_the_consumer_and_it_ends_ashford_only(
    firm: Firm,
) -> None:
    assert (await _wall(firm, firm.lena, firm.ashford, approver=firm.margaret)).status_code == 201
    # Before the consumer: her membership row still exists, yet every read is 404.
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
            firm.ashford.engagement_id,
            firm.lena.user_id,
        )
        == 1
    )
    response = await firm.call("GET", f"/v1/engagements/{firm.ashford.engagement_id}", firm.lena)
    assert response.status_code == 404
    [row] = await firm.seed.rows(
        "SELECT id, tenant_id, event_type, payload FROM outbox WHERE tenant_id = $1 "
        "AND event_type = 'wall.created'",
        firm.tenant_id,
    )
    payload = row["payload"]
    event = OutboxEvent(
        row["id"],
        row["tenant_id"],
        row["event_type"],
        cast(Json, json.loads(payload) if isinstance(payload, str) else payload),
    )
    for _ in range(2):  # idempotent
        await end_assignments_for_wall(event)
    members = await firm.seed.rows(
        "SELECT engagement_id FROM engagement_members WHERE tenant_id = $1 AND user_id = $2",
        firm.tenant_id,
        firm.lena.user_id,
    )
    assert [r["engagement_id"] for r in members] == [firm.ridgeline.engagement_id]
    [ended] = await firm.audit("engagement_member.removed")
    assert ended["actor_kind"] == "system"
    assert ended["on_behalf_of_user_id"] == firm.grace.user_id


# ================================================================================================
# Offshore, as amended (AC9.1 to AC9.4; SPEC-002 AC-18 to AC-20; DEC-319, TASK-1207)
# ================================================================================================


async def test_ac9_1_adm03d_lists_remy_with_0_consented_clients_and_toggles_locked_on(
    firm: Firm,
) -> None:
    remy = await firm.person(offshore=True)
    offshore = _body(await firm.call("GET", "/v1/firm/offshore", firm.grace))
    assert offshore["member_ids"] == [str(remy.user_id)]
    assert offshore["consented_client_count"] == 0  # no consent provider registered: fail closed
    assert (offshore["block_without_consent"], offshore["mask_tins"]) == (True, True)
    # There is no API to turn the toggles off.
    for method in ("PUT", "PATCH", "POST"):
        write = await firm.call(
            method,
            "/v1/firm/offshore",
            firm.grace,
            {"block_without_consent": False, "mask_tins": False},
        )
        assert write.status_code in (404, 405), (method, write.text)


async def test_ac9_1_remy_reads_the_clients_his_roles_reach_offshore_is_not_a_wall(
    firm: Firm,
) -> None:
    remy = await firm.person(offshore=True)
    await firm.seed.member(firm.ashford, remy, "staff")
    engagement = await firm.call("GET", f"/v1/engagements/{firm.ashford.engagement_id}", remy)
    assert engagement.status_code == 200, engagement.text
    items = await firm.call(
        "GET", f"/v1/engagements/{firm.ashford.engagement_id}/request-items", remy
    )
    assert items.status_code == 200, items.text
    ids = [e["id"] for e in cast(list[Json], await _list(firm, "/v1/engagements", remy))]
    assert ids == [str(firm.ashford.engagement_id)]
    # A wall binds him exactly like anyone else (404 everywhere).
    assert (await _wall(firm, remy, firm.ashford, approver=firm.margaret)).status_code == 201
    walled = await firm.call("GET", f"/v1/engagements/{firm.ashford.engagement_id}", remy)
    assert walled.status_code == 404
    assert walled.json() == NOT_FOUND


async def test_ac9_3_an_offshore_member_is_not_assignable_without_consent_409(
    firm: Firm,
) -> None:
    remy = await firm.person(offshore=True)
    path = f"/v1/engagements/{firm.ridgeline.engagement_id}/team"
    refused = await firm.call(
        "POST", path, firm.margaret, {"user_id": str(remy.user_id), "role": "staff"}
    )
    assert refused.status_code == 409, refused.text
    assert _detail(refused) == "offshore_consent_required"
    assert (
        await firm.seed.value(
            "SELECT count(*) FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
            firm.ridgeline.engagement_id,
            remy.user_id,
        )
        == 0
    )
    # The same add for an onshore colleague goes through (the guard is offshore's alone).
    added = await firm.call(
        "POST", path, firm.margaret, {"user_id": str(firm.kevin.user_id), "role": "staff"}
    )
    assert added.status_code in (200, 201), added.text


async def test_ac4_6_turning_offshore_on_over_assignments_is_409_and_changes_nothing(
    firm: Firm,
) -> None:
    person = _body(await firm.call("GET", f"{STAFF}/{firm.lena.user_id}", firm.grace))
    refused = await firm.call(
        "PATCH",
        f"{STAFF}/{firm.lena.user_id}",
        firm.grace,
        {"version": person["version"], "offshore": True},
    )
    assert refused.status_code == 409, refused.text
    assert _detail(refused) == "offshore_assignment_conflict"
    assert (await firm.membership(firm.lena))["offshore"] is False
    # Kevin holds no assignment: the flag turns on and access.changed goes out.
    kevin = _body(await firm.call("GET", f"{STAFF}/{firm.kevin.user_id}", firm.grace))
    turned = await firm.call(
        "PATCH",
        f"{STAFF}/{firm.kevin.user_id}",
        firm.grace,
        {"version": kevin["version"], "offshore": True},
    )
    assert turned.status_code == 200, turned.text
    assert (await firm.membership(firm.kevin))["offshore"] is True
    assert await firm.access_changed_for(firm.kevin) >= 1
    offshore = _body(await firm.call("GET", "/v1/firm/offshore", firm.grace))
    assert offshore["member_ids"] == [str(firm.kevin.user_id)]


async def test_ac9_dec319_nobody_clears_their_own_offshore_flag(firm: Firm) -> None:
    ada = await firm.person("firm_admin", level="admin", offshore=True)
    mine = _body(await firm.call("GET", f"{STAFF}/{ada.user_id}", ada))
    refused = await firm.call(
        "PATCH", f"{STAFF}/{ada.user_id}", ada, {"version": mine["version"], "offshore": False}
    )
    assert refused.status_code == 403, refused.text
    assert _detail(refused) == "own_offshore"
    assert (await firm.membership(ada))["offshore"] is True
    cleared = await firm.call(
        "PATCH",
        f"{STAFF}/{ada.user_id}",
        firm.grace,
        {"version": mine["version"], "offshore": False},
    )
    assert cleared.status_code == 200, cleared.text


async def test_ac9_4_tins_reach_an_offshore_partner_masked_and_no_reveal_is_offered(
    firm: Firm,
) -> None:
    await _flag(firm.seed, firm.tenant_id, "clients.v2")
    remy = await firm.person(level="partner", offshore=True)
    onshore = await firm.person(level="partner")
    for who in (remy, onshore):
        await firm.seed.member(firm.ridgeline, who, "engagement_partner")
    ctx = firm.auth(firm.grace, "firm_admin")
    async with uow(ctx.tenant) as tx:
        await seal_tin(tx, ctx, firm.ridgeline.entity_id, EIN, "ein")
    record = await firm.call("GET", f"/v1/clients/{firm.ridgeline.client_id}", remy)
    assert record.status_code == 200, record.text  # offshore is not a wall
    raw = record.text
    assert EIN not in raw and EIN_DIGITS not in raw
    for action in ("tin.reveal", "pii.reveal"):
        assert action not in raw, action  # never among his allowed actions
    revealed = await firm.call(
        "POST",
        f"/v1/client-entities/{firm.ridgeline.entity_id}/tin/reveal",
        remy,
        {"reason": "prepare_return"},
    )
    assert revealed.status_code == 403, revealed.text
    # SPEC-002 AC-18: refused at the condition layer, consent or not, by `authorise` itself.
    tenant = TenantContext(firm.tenant_id, "human", "probe")
    resource = await engagement_resource(tenant, firm.ridgeline.engagement_id)
    with pytest.raises(Forbidden):
        await authorise(firm.auth(remy), "tin.reveal", resource)


# ================================================================================================
# INV-1: agent and system refused on every new write (AC4.7; the contract §2)
# ================================================================================================


async def test_inv1_agent_and_system_are_refused_every_new_write(firm: Firm) -> None:
    agent = _agent(firm, firm.grace, NEW_WRITES, None)
    for action in NEW_WRITES:
        decisions = RULES[action].decisions
        for principal in ("agent", "system"):
            assert decisions.get(principal, "deny") == "deny", (action, decisions)
        assert not {r for r, d in decisions.items() if r.startswith("client_") and d != "deny"}
        with pytest.raises(Forbidden):
            await authorise(agent, action, Resource.firm(firm.tenant_id))
