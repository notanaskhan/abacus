"""AC-17, AC-20: `authorise` and `visible` for an `AgentContext` (TASK-011a interface contract,
"AgentContext and `authorise`"): the matrix, the run's task scope, the live initiator check and the
reach rule for actions no human role holds (`screening.run`).

The contexts come from `agent_context_for_run`, the only issuer. Expectations come from the
contract, not the implementation.
"""

from __future__ import annotations

import json
import uuid
from typing import Literal, cast

import pytest
from sqlalchemy import Uuid, column, select, table

from abacus.kernel.db import tenant_session
from abacus.modules.identity.api import (
    AgentContext,
    Forbidden,
    NoActiveTenant,
    Resource,
    agent_context_for_run,
    agent_may_hold,
    authorise,
    is_active_member,
    visible,
)
from abacus.modules.identity.authz import UnknownAction

from .support import Person, Seeder, World

AGENT_ID = "evidence.screener"
FULL_SCOPE = frozenset(
    {"evidence.read", "screening.run", "fulfilment.propose", "request_item.read"}
)
Role = Literal["engagement_partner", "manager", "senior", "staff", "reviewer"]


async def _agent(
    world: World,
    *,
    initiator: Person | None = None,
    engagement_id: uuid.UUID | None = None,
    scope: frozenset[str] = FULL_SCOPE,
) -> AgentContext:
    return await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=uuid.uuid4(),
        agent_id=AGENT_ID,
        engagement_id=engagement_id or world.engagement_id,
        task_scope=scope,
        initiator_user_id=(initiator or world.requester).user_id,
    )


def _resource(world: World, *, archived: bool = False) -> Resource:
    return Resource.engagement(world.tenant_id, world.engagement_id, archived=archived)


async def _denied(agent: AgentContext, action: str, resource: Resource) -> str:
    with pytest.raises(Forbidden) as raised:
        await authorise(agent, action, resource)
    return raised.value.layer


async def _member(seed: Seeder, world: World, role: Role) -> Person:
    person = await seed.person(world.tenant_id)
    await seed.member(world.engagement_id, person, role)
    return person


# --- the issuer ----------------------------------------------------------------------------------


async def test_ac17_the_issued_context_acts_as_its_run_for_its_initiator(world: World) -> None:
    run_id = uuid.uuid4()
    agent = await agent_context_for_run(
        tenant_id=world.tenant_id,
        run_id=run_id,
        agent_id=AGENT_ID,
        engagement_id=world.engagement_id,
        task_scope=FULL_SCOPE,
        initiator_user_id=world.requester.user_id,
    )
    assert agent.tenant.actor_kind == "agent"
    assert agent.tenant.actor_id == f"agent:{AGENT_ID}:{run_id}"
    assert agent.tenant_id == world.tenant_id
    assert agent.initiator.user_id == world.requester.user_id
    assert agent.task_scope == FULL_SCOPE


async def test_ac17_an_unknown_initiator_gets_no_context(world: World) -> None:
    with pytest.raises(NoActiveTenant):
        await _agent(world, initiator=Person(uuid.uuid4(), world.tenant_id))


async def test_ac17_an_initiator_of_another_firm_gets_no_context(
    seed: Seeder, world: World
) -> None:
    other_firm = await seed.firm()
    stranger = await seed.person(other_firm)
    with pytest.raises(NoActiveTenant):
        await _agent(world, initiator=Person(stranger.user_id, world.tenant_id))


async def test_ac17_a_revoked_initiator_gets_no_context(seed: Seeder, world: World) -> None:
    colleague = await seed.person(world.tenant_id)
    await seed.revoke(colleague)
    with pytest.raises(NoActiveTenant):
        await _agent(world, initiator=colleague)


async def test_ac17_is_active_member_follows_the_live_membership(
    seed: Seeder, world: World
) -> None:
    colleague = await seed.person(world.tenant_id)
    assert await is_active_member(world.tenant_id, colleague.user_id) is True
    await seed.revoke(colleague)
    assert await is_active_member(world.tenant_id, colleague.user_id) is False
    assert await is_active_member(world.tenant_id, uuid.uuid4()) is False


async def test_ac17_is_active_member_is_scoped_to_the_firm(seed: Seeder, world: World) -> None:
    other_firm = await seed.firm()
    assert await is_active_member(other_firm, world.requester.user_id) is False


# --- agent_may_hold ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "action",
    [
        "request_item.read",
        "evidence.read",
        "fulfilment.propose",
        "screening.run",
        "suggestion.create",
        "follow_up.draft",
        "support_match.run",
    ],
)
def test_ac17_agent_may_hold_is_true_for_task_scope_actions(action: str) -> None:
    assert agent_may_hold(action) is True


@pytest.mark.parametrize(
    "action",
    [
        "evidence.accept",
        "evidence.reject",
        "fulfilment.confirm",
        "suggestion.resolve",
        "follow_up.send",
        "evidence.upload",
        "request_item.mark_ready",
        "engagement.read",
        "connection.pull",
    ],
)
def test_ac17_agent_may_hold_is_false_for_everything_else(action: str) -> None:
    assert agent_may_hold(action) is False


def test_ac17_agent_may_hold_refuses_an_action_the_matrix_does_not_know() -> None:
    with pytest.raises(UnknownAction):
        agent_may_hold("evidence.invent")


# --- relationship and tenancy --------------------------------------------------------------------


async def test_ac20_an_agent_holds_the_role_agent_on_its_own_engagement_only(
    seed: Seeder, world: World
) -> None:
    agent = await _agent(world)
    await authorise(agent, "evidence.read", _resource(world))
    sibling = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    await seed.member(sibling, world.requester, "staff")
    other = Resource.engagement(world.tenant_id, sibling, archived=False)
    assert await _denied(agent, "evidence.read", other) == "relationship"


async def test_ac20_an_agent_has_no_relationship_to_a_firm_resource(world: World) -> None:
    agent = await _agent(world)
    assert await _denied(agent, "evidence.read", Resource.firm(world.tenant_id)) == "relationship"


async def test_ac20_an_agent_is_denied_in_another_firm_at_tenancy(
    seed: Seeder, world: World
) -> None:
    agent = await _agent(world)
    other_firm = await seed.firm()
    foreign = Resource.engagement(other_firm, world.engagement_id, archived=False)
    assert await _denied(agent, "evidence.read", foreign) == "tenancy"


# --- task scope and the matrix -------------------------------------------------------------------


async def test_ac17_an_action_in_the_runs_scope_is_allowed(world: World) -> None:
    agent = await _agent(world)
    for action in ("evidence.read", "screening.run", "request_item.read"):
        await authorise(agent, action, _resource(world))


async def test_ac17_a_task_scope_action_outside_the_runs_scope_is_denied_at_role(
    world: World,
) -> None:
    agent = await _agent(world, scope=frozenset({"evidence.read"}))
    assert await _denied(agent, "screening.run", _resource(world)) == "role"
    assert await _denied(agent, "request_item.read", _resource(world)) == "role"


async def test_ac17_an_empty_scope_grants_nothing(world: World) -> None:
    agent = await _agent(world, scope=frozenset())
    assert await _denied(agent, "evidence.read", _resource(world)) == "role"


@pytest.mark.parametrize(
    "action", ["evidence.accept", "evidence.reject", "fulfilment.confirm", "suggestion.resolve"]
)
async def test_ac17_a_decision_is_denied_at_role_even_when_the_scope_names_it(
    world: World, action: str
) -> None:
    agent = await _agent(world, scope=frozenset({action}))
    assert await _denied(agent, action, _resource(world)) == "role"


@pytest.mark.parametrize(
    "action",
    ["evidence.upload", "request_item.mark_ready", "engagement.archive", "connection.pull"],
)
async def test_ac17_an_action_the_matrix_never_gives_agents_is_denied_at_role(
    world: World, action: str
) -> None:
    agent = await _agent(world, scope=frozenset({action}))
    assert await _denied(agent, action, _resource(world)) == "role"


async def test_ac17_a_firm_setting_grant_is_not_a_grant_for_an_agent(world: World) -> None:
    agent = await _agent(world, scope=frozenset({"follow_up.send"}))
    assert await _denied(agent, "follow_up.send", _resource(world)) == "role"


async def test_ac17_an_unknown_action_is_a_programming_error(world: World) -> None:
    agent = await _agent(world)
    with pytest.raises(UnknownAction):
        await authorise(agent, "evidence.invent", _resource(world))


# --- the intersection with the initiator, checked live -------------------------------------------


@pytest.mark.parametrize("role", ["engagement_partner", "manager", "senior", "staff", "reviewer"])
async def test_ac17_every_engagement_role_may_have_the_agent_read_and_screen(
    seed: Seeder, world: World, role: Role
) -> None:
    initiator = await _member(seed, world, role)
    agent = await _agent(world, initiator=initiator)
    await authorise(agent, "evidence.read", _resource(world))
    await authorise(agent, "screening.run", _resource(world))


async def test_ac17_a_reviewer_initiator_cannot_extend_the_agent_to_what_reviewers_may_not_do(
    seed: Seeder, world: World
) -> None:
    reviewer = await _member(seed, world, "reviewer")
    agent = await _agent(world, initiator=reviewer)
    assert await _denied(agent, "fulfilment.propose", _resource(world)) == "delegation"


async def test_ac17_a_staff_initiator_lets_the_agent_do_what_staff_may_do(
    world: World,
) -> None:
    agent = await _agent(world)
    await authorise(agent, "fulfilment.propose", _resource(world))


async def test_ac17_an_initiator_removed_from_the_engagement_is_denied_at_delegation(
    seed: Seeder, world: World
) -> None:
    agent = await _agent(world)
    await authorise(agent, "evidence.read", _resource(world))
    await seed.unmember(world.engagement_id, world.requester)
    assert await _denied(agent, "evidence.read", _resource(world)) == "delegation"
    assert await _denied(agent, "fulfilment.propose", _resource(world)) == "delegation"


async def test_ac17_the_reach_rule_denies_screening_run_to_an_initiator_who_cannot_read(
    seed: Seeder, world: World
) -> None:
    outsider = await seed.person(world.tenant_id)
    agent = await _agent(world, initiator=outsider)
    assert await _denied(agent, "screening.run", _resource(world)) == "delegation"
    assert await _denied(agent, "evidence.read", _resource(world)) == "delegation"


async def test_ac17_the_reach_rule_follows_the_initiators_membership_live(
    seed: Seeder, world: World
) -> None:
    agent = await _agent(world)
    await authorise(agent, "screening.run", _resource(world))
    await seed.unmember(world.engagement_id, world.requester)
    assert await _denied(agent, "screening.run", _resource(world)) == "delegation"


# --- archived engagements ------------------------------------------------------------------------


async def test_ac17_an_archived_engagement_is_read_only_for_the_agent(world: World) -> None:
    agent = await _agent(world)
    archived = _resource(world, archived=True)
    await authorise(agent, "evidence.read", archived)
    assert await _denied(agent, "screening.run", archived) == "attribute"


async def test_ac17_a_write_a_human_role_holds_is_denied_at_attribute_on_an_archived_engagement(
    world: World,
) -> None:
    agent = await _agent(world)
    assert await _denied(agent, "fulfilment.propose", _resource(world, archived=True)) == (
        "attribute"
    )


# --- logs ----------------------------------------------------------------------------------------


def _lines(capsys: pytest.CaptureFixture[str]) -> list[dict[str, object]]:
    return [
        cast(dict[str, object], json.loads(line))
        for line in capsys.readouterr().out.splitlines()
        if line.startswith("{")
    ]


async def test_ac17_allowed_checks_log_the_agent_run_and_initiator(
    world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    agent = await _agent(world)
    capsys.readouterr()
    await authorise(agent, "evidence.read", _resource(world))
    [allowed] = [e for e in _lines(capsys) if e.get("event") == "authz.allowed"][-1:]
    assert allowed["agent_id"] == AGENT_ID
    assert allowed["agent_run_id"] == str(agent.agent_run_id)
    assert allowed["on_behalf_of"] == str(world.requester.user_id)


async def test_ac17_denied_checks_log_the_agent_run_and_initiator(
    seed: Seeder, world: World, capsys: pytest.CaptureFixture[str]
) -> None:
    agent = await _agent(world)
    await seed.unmember(world.engagement_id, world.requester)
    capsys.readouterr()
    await _denied(agent, "evidence.read", _resource(world))
    denied = [e for e in _lines(capsys) if e.get("event") == "authz.denied"][-1]
    assert denied["agent_id"] == AGENT_ID
    assert denied["agent_run_id"] == str(agent.agent_run_id)
    assert denied["on_behalf_of"] == str(world.requester.user_id)
    assert denied["layer"] == "delegation"


# --- visible -------------------------------------------------------------------------------------

ENGAGEMENTS = table("engagements", column("id", Uuid), column("tenant_id", Uuid))


async def _visible_ids(agent: AgentContext, action: str) -> set[uuid.UUID]:
    query = select(ENGAGEMENTS.c.id).where(visible(agent, action, ENGAGEMENTS.c.id))
    async with tenant_session(agent.tenant) as session:
        return set((await session.execute(query)).scalars())


async def test_ac20_visible_for_an_agent_is_its_engagement_and_nothing_else(
    seed: Seeder, world: World
) -> None:
    sibling = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    await seed.member(sibling, world.requester, "staff")
    agent = await _agent(world)
    assert await _visible_ids(agent, "evidence.read") == {world.engagement_id}


async def test_ac20_visible_for_an_agent_is_also_bounded_by_what_the_initiator_sees(
    seed: Seeder, world: World
) -> None:
    agent = await _agent(world)
    await seed.unmember(world.engagement_id, world.requester)
    assert await _visible_ids(agent, "evidence.read") == set()


async def test_ac20_visible_is_empty_for_an_agent_whose_initiator_never_saw_its_engagement(
    seed: Seeder, world: World
) -> None:
    other = await seed.engagement(world.tenant_id, world.entity_id, world.requester.user_id)
    agent = await _agent(world, engagement_id=other)
    assert await _visible_ids(agent, "evidence.read") == set()


async def test_ac20_visible_is_empty_for_a_read_outside_the_runs_scope(world: World) -> None:
    agent = await _agent(world, scope=frozenset({"evidence.read"}))
    assert await _visible_ids(agent, "request_item.read") == set()
    assert await _visible_ids(agent, "evidence.read") == {world.engagement_id}


async def test_ac20_visible_is_empty_for_a_read_agents_are_never_given(world: World) -> None:
    agent = await _agent(world)
    assert await _visible_ids(agent, "engagement.read") == set()


async def test_ac20_visible_refuses_a_write_action(world: World) -> None:
    agent = await _agent(world)
    with pytest.raises(ValueError, match="read"):
        visible(agent, "screening.run", ENGAGEMENTS.c.id)


async def test_ac20_visible_agrees_with_authorise_for_a_reviewer_initiator(
    seed: Seeder, world: World
) -> None:
    reviewer = await _member(seed, world, "reviewer")
    agent = await _agent(world, initiator=reviewer)
    await authorise(agent, "evidence.read", _resource(world))
    assert await _visible_ids(agent, "evidence.read") == {world.engagement_id}
