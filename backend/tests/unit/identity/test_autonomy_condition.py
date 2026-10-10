"""SPEC-027 (TASK-051 D2): `firm_setting(autonomy_policy)` for agents. The engagement agent may
send a routine reminder (`follow_up.send`) at the firm's Routine autonomy or higher, within its
declared scope, and never beyond its initiator (ADR-025)."""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from typing import cast

import pytest
import yaml

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context, firm_settings
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    agent_may_hold,
    authorise,
    policy_agent_may_hold,
)
from abacus_tools.codegen import permission_matrix as pm


class _Fakes:
    def __init__(self) -> None:
        self.level = 1
        self.initiator_role: str | None = "engagement_partner"

    async def engagement_role(
        self, tenant: object, user_id: uuid.UUID, engagement: object
    ) -> str | None:
        return self.initiator_role

    async def walled(self, *_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def autonomy(self, tenant_id: uuid.UUID) -> int:
        return self.level


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> _Fakes:
    made = _Fakes()
    monkeypatch.setattr(authz, "engagement_role", made.engagement_role)
    monkeypatch.setattr(authz, "walled_clients", made.walled)
    monkeypatch.setattr(firm_settings, "autonomy_level", made.autonomy)
    return made


def _agent(scope: frozenset[str], engagement_id: uuid.UUID) -> AgentContext:
    user = uuid.uuid4()
    tenant = TenantContext(uuid.uuid4(), "human", str(user))
    initiator = AuthContext(
        tenant, user, uuid.uuid4(), None, datetime.now(UTC) - timedelta(minutes=1)
    )
    run_id = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(tenant.tenant_id, "agent", f"agent:engagement.agent:{run_id}"),
        agent_id="engagement.agent",
        agent_run_id=run_id,
        engagement_id=engagement_id,
        task_scope=scope,
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


def _on(agent: AgentContext) -> Resource:
    return Resource.engagement(agent.tenant_id, agent.engagement_id, archived=False)


SCOPE = frozenset({"follow_up.draft", "follow_up.send"})


async def test_d2_routine_lets_the_agent_send_a_reminder(fakes: _Fakes) -> None:
    agent = _agent(SCOPE, uuid.uuid4())
    await authorise(agent, "follow_up.send", _on(agent))


async def test_d2_advise_refuses_it(fakes: _Fakes) -> None:
    fakes.level = 0
    agent = _agent(SCOPE, uuid.uuid4())
    with pytest.raises(Forbidden) as raised:
        await authorise(agent, "follow_up.send", _on(agent))
    assert raised.value.layer == "role"


async def test_d2_outside_the_declared_scope_it_is_refused(fakes: _Fakes) -> None:
    agent = _agent(frozenset({"follow_up.draft"}), uuid.uuid4())
    with pytest.raises(Forbidden):
        await authorise(agent, "follow_up.send", _on(agent))


async def test_d2_never_beyond_its_initiator(fakes: _Fakes) -> None:
    fakes.initiator_role = "staff"  # staff may not send follow-ups
    agent = _agent(SCOPE, uuid.uuid4())
    with pytest.raises(Forbidden) as raised:
        await authorise(agent, "follow_up.send", _on(agent))
    assert raised.value.layer == "delegation"


async def test_d2_people_are_unaffected(fakes: _Fakes) -> None:
    """A senior's `firm_setting(seniors_can_accept)` stays unmodelled: still refused."""
    fakes.initiator_role = "senior"
    user = uuid.uuid4()
    person = AuthContext(
        TenantContext(uuid.uuid4(), "human", str(user)),
        user,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )
    with pytest.raises(Forbidden):
        await authorise(
            person,
            "evidence.accept",
            Resource.engagement(person.tenant_id, uuid.uuid4(), archived=False),
        )


def test_d1_only_policy_agents_may_declare_follow_up_send() -> None:
    assert not agent_may_hold("follow_up.send")  # model agents: unchanged
    assert policy_agent_may_hold("follow_up.send")
    assert policy_agent_may_hold("follow_up.draft")
    assert not policy_agent_may_hold("evidence.accept")


def test_the_matrix_s_only_agent_firm_setting_is_the_autonomy_policy() -> None:
    """The parsed matrix keeps `firm_setting`, not its name; `authorise` reads an agent's as the
    autonomy policy, so any other would be a silent grant. This fails first."""
    actions = cast(dict[str, dict[str, str]], yaml.safe_load(pm.SOURCE.read_text())["actions"])
    agent_settings = {
        name: entries["agent"]
        for name, entries in actions.items()
        if re.fullmatch(r"firm_setting\(.*\)", str(entries.get("agent", "")))
    }
    assert agent_settings == {"follow_up.send": "firm_setting(autonomy_policy)"}
