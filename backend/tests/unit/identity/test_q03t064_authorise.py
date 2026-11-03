"""Q-03-T064 part 2 (TASK-2824): the identity/authz survivors in `authorise`'s role layer.

From the contracts in `identity.authz` (ADR-020, ADR-025, F-03-T24, SPEC-027):
- a person with no relationship to an engagement is refused at `client_scope` when they are a
  client user, else at `relationship`; a firm-level resource is always `relationship`;
- a cell `in_scope` is resolved only when no other role's cell already allows or denies; each
  `in_scope` role is asked in turn with the membership read so far, and allows when its scope
  holds;
- a person's `firm_setting(<key>)` cell allows when the firm has switched `<key>` on; an agent's
  `firm_setting` cell is its autonomy policy instead, allowed only for an action in its run's
  scope when the policy allows it now;
- the service-line reader's cell is narrowed by whatever narrows the `staff` cell it takes.
`Forbidden` names the action and the layer.

Equivalent survivors (recorded for approval in TASK-2824): `x_authorise__mutmut_122` and `_123`
rename the `task_scope` taken out of an agent's decisions; `allow` is added either way, and the
set is only asked whether it holds `deny` or `allow`, so leaving `task_scope` in changes nothing.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.authz import Forbidden, Resource
from abacus.modules.identity.authz.matrix import RULES, Rule
from abacus.modules.identity.context import Actor, AgentContext, AuthContext
from abacus.modules.identity.repository import FirmPolicy, MemberFacts

TENANT = uuid.uuid4()
ENGAGEMENT = uuid.uuid4()
ACTION = "q03t064a.update"
NOW = datetime(2027, 9, 1, 12, tzinfo=UTC)
REAL_AUTHORISE = authz.authorise
FIRST = MemberFacts(level="manager", offshore=False, service_lines=frozenset(), client=False)


@dataclass
class World:
    roles: set[str] = field(default_factory=set[str])
    policy: FirmPolicy = field(default_factory=lambda: FirmPolicy({}, frozenset()))
    scoped: dict[str, bool] = field(default_factory=dict[str, bool])
    in_scope_calls: list[tuple[object, ...]] = field(default_factory=list[tuple[object, ...]])
    autonomy: bool = True
    autonomy_calls: list[object] = field(default_factory=list[object])
    initiator_checks: list[tuple[object, str]] = field(default_factory=list[tuple[object, str]])


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> Iterator[World]:
    w = World()

    async def walled(*_: object) -> bool:
        return False

    async def roles(ctx: Actor, *_: object) -> set[str]:
        return {"agent"} if isinstance(ctx, AgentContext) else set(w.roles)

    async def firm_policy(_ctx: object) -> FirmPolicy:
        return w.policy

    async def in_scope(
        ctx: object, role: str, resource: object, member: MemberFacts | None
    ) -> tuple[MemberFacts | None, bool]:
        w.in_scope_calls.append((ctx, role, resource, member))
        return FIRST, w.scoped.get(role, False)

    async def autonomy_allows(ctx: object) -> bool:
        w.autonomy_calls.append(ctx)
        return w.autonomy

    async def access_has_ended(*_: object) -> bool:
        return False

    async def authorise(ctx: Actor, action: str, resource: Resource, **kw: object) -> None:
        if isinstance(ctx, AuthContext) and ctx.tenant.actor_id.startswith("initiator:"):
            w.initiator_checks.append((ctx, action))
            return
        await REAL_AUTHORISE(ctx, action, resource, **kw)  # pyright: ignore[reportArgumentType] -- passed through

    monkeypatch.setattr(authz, "_walled", walled)
    monkeypatch.setattr(authz, "_roles", roles)
    monkeypatch.setattr(authz, "_firm_policy", firm_policy)
    monkeypatch.setattr(authz, "_in_scope", in_scope)
    monkeypatch.setattr(authz, "_autonomy_allows", autonomy_allows)
    monkeypatch.setattr(authz, "access_has_ended", access_has_ended)
    monkeypatch.setattr(authz, "authorise", authorise)
    yield w


def _install(monkeypatch: pytest.MonkeyPatch, **over: object) -> None:
    values: dict[str, object] = {
        "action": ACTION,
        "decisions": {},
        "mfa_recent": False,
        "requires_reason": False,
        "notify": False,
    }
    values.update(over)
    monkeypatch.setitem(RULES, ACTION, Rule(**values))  # pyright: ignore[reportArgumentType] -- the rule under test


def _person(
    *, client: bool = False, kind: str = "human", firm_role: str | None = None
) -> AuthContext:
    user = uuid.uuid4()
    return AuthContext(
        TenantContext(TENANT, kind, f"user:{user}"),  # pyright: ignore[reportArgumentType] -- test kinds
        user,
        uuid.uuid4(),
        firm_role,  # pyright: ignore[reportArgumentType] -- test roles
        NOW,
        client=client,
    )


def _agent(scope: frozenset[str]) -> AgentContext:
    user = uuid.uuid4()
    initiator = AuthContext(
        TenantContext(TENANT, "human", f"initiator:{user}"), user, uuid.uuid4(), None, NOW
    )
    run = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(TENANT, "agent", f"agent:q03.agent:{run}"),
        agent_id="q03.agent",
        agent_run_id=run,
        engagement_id=ENGAGEMENT,
        task_scope=scope,
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


def _on_engagement() -> Resource:
    return Resource.engagement(TENANT, ENGAGEMENT, archived=False)


async def _refused(ctx: Actor, resource: Resource) -> Forbidden:
    with pytest.raises(Forbidden) as caught:
        await authz.authorise(ctx, ACTION, resource)
    assert caught.value.action == ACTION
    return caught.value


# --- no relationship -----------------------------------------------------------------------------


async def test_a_client_user_with_no_relationship_is_refused_at_client_scope(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"client_admin": "allow"})
    denied = await _refused(_person(client=True), _on_engagement())
    assert denied.layer == "client_scope"
    assert str(denied) == f"{ACTION} denied at client_scope"


@pytest.mark.parametrize(
    ("client", "resource"),
    [
        (False, Resource.engagement(TENANT, ENGAGEMENT, archived=False)),
        (True, Resource.firm(TENANT)),  # a firm-level resource is no client scope
    ],
)
async def test_otherwise_no_relationship_is_refused_at_relationship(
    world: World, monkeypatch: pytest.MonkeyPatch, client: bool, resource: Resource
) -> None:
    _install(monkeypatch, decisions={"manager": "allow"})
    assert (await _refused(_person(client=client), resource)).layer == "relationship"


# --- in_scope ------------------------------------------------------------------------------------


async def test_an_in_scope_role_allows_when_its_scope_holds(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"practice_leader": "in_scope"})
    world.roles = {"practice_leader"}
    world.scoped = {"practice_leader": True}
    person, resource = _person(), _on_engagement()
    await authz.authorise(person, ACTION, resource)
    assert world.in_scope_calls == [(person, "practice_leader", resource, None)]


async def test_an_in_scope_role_out_of_scope_is_refused(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"practice_leader": "in_scope"})
    world.roles = {"practice_leader"}
    assert (await _refused(_person(), _on_engagement())).layer == "role"
    assert len(world.in_scope_calls) == 1


async def test_each_in_scope_role_gets_the_membership_read_so_far(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"practice_leader": "in_scope", "quality_partner": "in_scope"})
    world.roles = {"practice_leader", "quality_partner"}
    world.scoped = {"quality_partner": True}
    person = _person()
    await authz.authorise(person, ACTION, _on_engagement())
    members = [call[3] for call in world.in_scope_calls]
    assert members[0] is None  # nothing read before the first
    assert members[1:] == [FIRST]  # the first one's read is passed on
    assert sorted(str(call[1]) for call in world.in_scope_calls) == [
        "practice_leader",
        "quality_partner",
    ]


@pytest.mark.parametrize("other", ["allow", "deny"])
async def test_in_scope_is_not_asked_when_another_role_decides(
    world: World, monkeypatch: pytest.MonkeyPatch, other: str
) -> None:
    _install(monkeypatch, decisions={"practice_leader": "in_scope", "manager": other})
    world.roles = {"practice_leader", "manager"}
    if other == "allow":
        await authz.authorise(_person(), ACTION, _on_engagement())
    else:
        assert (await _refused(_person(), _on_engagement())).layer == "role"
    assert world.in_scope_calls == []


# --- firm settings and the autonomy policy -------------------------------------------------------


@pytest.mark.parametrize(("on", "allowed"), [(True, True), (False, False)])
async def test_a_persons_firm_setting_cell_allows_when_the_setting_is_on(
    world: World, monkeypatch: pytest.MonkeyPatch, on: bool, allowed: bool
) -> None:
    _install(
        monkeypatch,
        decisions={"manager": "firm_setting"},
        firm_settings=(("manager", "q03_switch"),),
    )
    world.roles = {"manager"}
    world.policy = FirmPolicy({}, frozenset({"q03_switch"} if on else set()))
    if allowed:
        await authz.authorise(_person(), ACTION, _on_engagement())
    else:
        assert (await _refused(_person(), _on_engagement())).layer == "role"


async def test_an_agents_firm_setting_cell_is_never_a_firm_switch(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Out of its run's scope, an agent's `firm_setting` cell is refused even when the firm has
    the named setting on: that switch is a person's, and the agent's is its autonomy policy."""
    _install(
        monkeypatch,
        decisions={"agent": "firm_setting", "manager": "allow"},
        firm_settings=(("agent", "q03_switch"),),
    )
    world.policy = FirmPolicy({}, frozenset({"q03_switch"}))
    assert (await _refused(_agent(frozenset()), _on_engagement())).layer == "role"
    assert world.initiator_checks == []


async def test_the_autonomy_policy_allows_an_agent_action_in_its_scope(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"agent": "firm_setting", "manager": "allow"})
    agent = _agent(frozenset({ACTION}))
    await authz.authorise(agent, ACTION, _on_engagement())
    assert world.autonomy_calls == [agent]
    assert world.initiator_checks == [(agent.initiator, ACTION)]  # then the intersection


async def test_the_autonomy_policy_at_advise_refuses(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"agent": "firm_setting", "manager": "allow"})
    world.autonomy = False
    assert (await _refused(_agent(frozenset({ACTION})), _on_engagement())).layer == "role"


async def test_the_autonomy_policy_never_reaches_outside_the_run_scope(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"agent": "firm_setting", "manager": "allow"})
    assert (await _refused(_agent(frozenset({"other.update"})), _on_engagement())).layer == "role"
    assert world.autonomy_calls == []


async def test_an_agent_task_scope_cell_allows_only_its_declared_actions(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    _install(monkeypatch, decisions={"agent": "task_scope", "manager": "allow"})
    agent = _agent(frozenset({ACTION}))
    await authz.authorise(agent, ACTION, _on_engagement())
    assert world.initiator_checks == [(agent.initiator, ACTION)]
    assert (await _refused(_agent(frozenset()), _on_engagement())).layer == "role"


# --- the service-line reader ---------------------------------------------------------------------


@pytest.mark.parametrize(("narrowed", "allowed"), [("staff", False), ("manager", True)])
async def test_the_reader_is_narrowed_by_the_staff_cells_override(
    world: World, monkeypatch: pytest.MonkeyPatch, narrowed: str, allowed: bool
) -> None:
    read = "q03t064a.read"
    values: dict[str, object] = {
        "action": read,
        "decisions": {"staff": "allow", "manager": "allow"},
        "mfa_recent": False,
        "requires_reason": False,
        "notify": False,
    }
    monkeypatch.setitem(RULES, read, Rule(**values))  # pyright: ignore[reportArgumentType] -- the rule under test
    world.roles = {authz.SERVICE_LINE_READER}
    world.policy = FirmPolicy({(read, narrowed): "deny"}, frozenset())
    person = _person()
    if allowed:
        await authz.authorise(person, read, _on_engagement())
    else:
        with pytest.raises(Forbidden) as caught:
            await authz.authorise(person, read, _on_engagement())
        assert caught.value.layer == "role"
