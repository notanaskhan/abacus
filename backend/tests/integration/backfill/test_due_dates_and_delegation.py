"""SPEC-027 AC-9 and AC-8 (TASK-051): due dates (own, else the list's; set in bulk by people who
can update items) and the agent acting only as far as the person it acts for.

HTTP and `authorise` against a real Postgres. Expectations come from the spec and the matrix.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, timedelta
from typing import cast

import pytest

from abacus.modules.agents.follow_ups import today_in
from abacus.modules.identity.api import (
    AgentContext,
    Forbidden,
    Resource,
    agent_context_for_run,
    authorise,
)

from .support import Net, Person, Role, Seeder, Site

ZONE = "America/Chicago"
ROLES: tuple[Role, ...] = ("engagement_partner", "manager", "senior", "staff", "reviewer")
MAY_UPDATE = {"engagement_partner", "manager", "senior"}  # request_item.update in the matrix


@dataclass(frozen=True)
class Board:
    net: Net
    seed: Seeder
    tenant_id: uuid.UUID
    site: Site
    team: dict[str, Person]
    admin: Person

    @property
    def base(self) -> str:
        return f"/v1/engagements/{self.site.engagement_id}"

    def day(self, offset: int) -> date:
        return today_in(ZONE) + timedelta(days=offset)

    async def overdue(self, who: Person) -> int:
        """What the caller's waiting-on-the-client count says for this engagement."""
        response = await self.net.call("GET", "/v1/firm/waiting/overdue", who)
        assert response.status_code == 200, response.text
        counts = {r["engagement_id"]: r["count"] for r in response.json()}
        return int(counts.get(str(self.site.engagement_id), 0))

    async def own_due(self, item_id: uuid.UUID) -> date | None:
        value = await self.seed.value("SELECT due_on FROM request_items WHERE id = $1", item_id)
        return cast("date | None", value)


@pytest.fixture
async def board(net: Net, seed: Seeder) -> Board:
    tenant_id = await seed.firm()
    admin = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, admin.user_id, "due")
    team: dict[str, Person] = {}
    for role in ROLES:
        team[role] = await seed.person(tenant_id)
        await seed.member(site, team[role], role)
    return Board(net, seed, tenant_id, site, team, admin)


# --- AC-9: due dates -----------------------------------------------------------------------------


async def test_ac9_an_item_follows_the_lists_default_unless_it_has_its_own(board: Board) -> None:
    manager = board.team["manager"]
    inherited = board.site.item_id
    own = await board.seed.item(board.site, "Own date")
    assert await board.overdue(manager) == 0  # no dates anywhere
    set_default = await board.net.call(
        "PUT",
        f"{board.base}/request-items/default-due-date",
        manager,
        body={"due_on": board.day(-5).isoformat()},
    )
    assert set_default.status_code == 200, set_default.text
    got = await board.net.call("GET", f"{board.base}/request-items/default-due-date", manager)
    assert got.json() == {"due_on": board.day(-5).isoformat()}
    assert await board.overdue(manager) == 2  # both follow the default
    future = await board.net.call(
        "PUT",
        f"{board.base}/request-items/due-dates",
        manager,
        body={"item_ids": [str(own)], "due_on": board.day(10).isoformat()},
    )
    assert future.status_code == 200, future.text
    assert await board.overdue(manager) == 1  # its own date wins over the default
    assert await board.own_due(inherited) is None  # the other still has none of its own
    cleared = await board.net.call(
        "PUT",
        f"{board.base}/request-items/due-dates",
        manager,
        body={"item_ids": [str(own)], "due_on": None},
    )
    assert cleared.status_code == 200, cleared.text
    assert await board.own_due(own) is None
    assert await board.overdue(manager) == 2  # a cleared item follows the default again
    no_default = await board.net.call(
        "PUT", f"{board.base}/request-items/default-due-date", manager, body={"due_on": None}
    )
    assert no_default.status_code == 200
    assert await board.overdue(manager) == 0


async def test_ac9_a_bulk_change_sets_every_item_audits_each_and_tells_the_agent(
    board: Board,
) -> None:
    manager = board.team["manager"]
    items = [
        board.site.item_id,
        await board.seed.item(board.site, "B"),
        await board.seed.item(board.site, "C"),
    ]
    due = board.day(-2)
    response = await board.net.call(
        "PUT",
        f"{board.base}/request-items/due-dates",
        manager,
        body={"item_ids": [str(i) for i in items], "due_on": due.isoformat()},
    )
    assert response.status_code == 200, response.text
    assert {row["id"]: row["due_on"] for row in response.json()} == {
        str(i): due.isoformat() for i in items
    }
    for item in items:
        assert await board.own_due(item) == due
    actions = await board.seed.actions(board.tenant_id)
    assert actions.count("request_item.due_date_set") == 3
    events = await board.seed.value(
        "SELECT count(*) FROM outbox WHERE tenant_id = $1 AND event_type = 'due_dates.changed'",
        board.tenant_id,
    )
    assert events == 1  # one signal for the change, which restarts the reminder sequence
    assert await board.overdue(manager) == 3


async def test_ac9_one_unknown_item_refuses_the_whole_change(board: Board) -> None:
    manager = board.team["manager"]
    other = await board.seed.site(board.tenant_id, board.admin.user_id, "elsewhere")
    for stranger in (uuid.uuid4(), other.item_id):  # no such item; another engagement's item
        response = await board.net.call(
            "PUT",
            f"{board.base}/request-items/due-dates",
            manager,
            body={
                "item_ids": [str(board.site.item_id), str(stranger)],
                "due_on": board.day(-1).isoformat(),
            },
        )
        assert response.status_code == 404, response.text
    assert await board.own_due(board.site.item_id) is None  # nothing was half-applied
    assert await board.own_due(other.item_id) is None
    assert "request_item.due_date_set" not in await board.seed.actions(board.tenant_id)


@pytest.mark.parametrize("role", ROLES)
async def test_ac9_people_who_can_update_items_can_set_due_dates_and_others_cannot(
    board: Board, role: str
) -> None:
    who = board.team[role]
    allowed = role in MAY_UPDATE
    body = {"item_ids": [str(board.site.item_id)], "due_on": board.day(3).isoformat()}
    bulk = await board.net.call("PUT", f"{board.base}/request-items/due-dates", who, body=body)
    default = await board.net.call(
        "PUT",
        f"{board.base}/request-items/default-due-date",
        who,
        body={"due_on": board.day(3).isoformat()},
    )
    expected = 200 if allowed else 403
    assert (bulk.status_code, default.status_code) == (expected, expected), (
        bulk.text,
        default.text,
    )
    assert (await board.own_due(board.site.item_id) is not None) == allowed
    read = await board.net.call("GET", f"{board.base}/request-items/default-due-date", who)
    assert read.status_code == 200  # everyone on the team can read it


async def test_ac9_a_client_cannot_set_due_dates(board: Board) -> None:
    contributor = await board.seed.client_contact(board.site, "client_contributor")
    response = await board.net.call(
        "PUT",
        f"{board.base}/request-items/due-dates",
        contributor,
        body={"item_ids": [str(board.site.item_id)], "due_on": board.day(3).isoformat()},
    )
    assert response.status_code == 403
    assert await board.own_due(board.site.item_id) is None


# --- AC-8: the agent never exceeds the person it acts for ----------------------------------------

DRAFT = "follow_up.draft"


async def _agent(
    board: Board, initiator: Person, scope: frozenset[str] = frozenset({DRAFT})
) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=board.tenant_id,
        run_id=uuid.uuid4(),
        agent_id="engagement.agent",
        engagement_id=board.site.engagement_id,
        task_scope=scope,
        initiator_user_id=initiator.user_id,
    )


async def _layer(board: Board, agent: AgentContext, action: str = DRAFT) -> str | None:
    """Where the agent is refused on its own engagement, or None if it is allowed."""
    resource = Resource.engagement(board.tenant_id, board.site.engagement_id, archived=False)
    try:
        await authorise(agent, action, resource)
    except Forbidden as denied:
        return denied.layer
    return None


async def test_ac8_the_agent_may_do_what_its_initiator_may(board: Board) -> None:
    partner = board.team["engagement_partner"]
    assert await _layer(board, await _agent(board, partner)) is None


async def test_ac8_an_initiator_removed_from_the_engagement_is_refused_at_delegation(
    board: Board,
) -> None:
    partner = board.team["engagement_partner"]
    agent = await _agent(board, partner)
    await board.seed.run(
        "DELETE FROM engagement_members WHERE engagement_id = $1 AND user_id = $2",
        board.site.engagement_id,
        partner.user_id,
    )
    assert await _layer(board, agent) == "delegation"  # read live, on the next step


async def test_ac8_an_initiator_who_may_not_do_it_by_the_matrix_is_refused_at_delegation(
    board: Board,
) -> None:
    reviewer = board.team["reviewer"]
    assert await _layer(board, await _agent(board, reviewer)) == "delegation"


async def test_ac8_an_initiator_who_has_not_confirmed_independence_is_refused_at_delegation(
    board: Board,
) -> None:
    newcomer = await board.seed.person(board.tenant_id)
    await board.seed.run(
        "INSERT INTO engagement_members (tenant_id, engagement_id, user_id, role) "
        "VALUES ($1, $2, $3, 'manager')",
        board.tenant_id,
        board.site.engagement_id,
        newcomer.user_id,
    )
    # Reading evidence is client data: the agent reads it only for someone who may.
    agent = await _agent(board, newcomer, frozenset({DRAFT, "evidence.read"}))
    assert await _layer(board, agent, "evidence.read") == "delegation"
    assert await _layer(board, agent, DRAFT) is None  # not client data: no confirmation needed


async def test_ac8_a_walled_initiator_is_refused_whatever_the_agent_was_given(
    board: Board,
) -> None:
    partner = board.team["engagement_partner"]
    agent = await _agent(board, partner)
    await board.net.wall(board.admin, partner, board.site)
    assert await _layer(board, agent) == "wall"  # SPEC-002 AC-7 names the layer
