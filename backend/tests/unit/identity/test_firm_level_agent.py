"""SPEC-035 Q3 (TASK-074 D1): a firm-level agent run (the guidance drafter on a template version)
has no engagement. It holds firm-scoped actions in its declared scope, within its initiator's
reach (`methodology.read`), and never any engagement's."""

from __future__ import annotations

import uuid
from typing import cast

import pytest
from sqlalchemy import column

from abacus.kernel.db import TenantContext
from abacus.modules.identity import authz, context
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    visible,
)
from abacus.modules.identity.repository import FirmRole

SCOPE = frozenset({"request_item.read", "methodology.read", "guidance_draft.run"})


@pytest.fixture(autouse=True)
def _no_walls_no_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    async def walled(*_: object) -> frozenset[uuid.UUID]:
        return frozenset()

    async def engagement_role(*_: object) -> str | None:
        return "engagement_partner"

    monkeypatch.setattr(authz, "walled_clients", walled)
    monkeypatch.setattr(authz, "engagement_role", engagement_role)


def _agent(firm_role: str | None, engagement_id: uuid.UUID | None = None) -> AgentContext:
    user = uuid.uuid4()
    tenant = TenantContext(uuid.uuid4(), "human", str(user))
    initiator = AuthContext(tenant, user, uuid.uuid4(), cast(FirmRole | None, firm_role), None)
    run_id = uuid.uuid4()
    return AgentContext(
        tenant=TenantContext(
            tenant.tenant_id, "agent", f"agent:requests.guidance_drafter:{run_id}"
        ),
        agent_id="requests.guidance_drafter",
        agent_run_id=run_id,
        engagement_id=engagement_id,
        task_scope=SCOPE,
        initiator=initiator,
        issued_by=context._ISSUER,  # pyright: ignore[reportPrivateUsage] -- an agent run's context
    )


async def test_d1_a_firm_level_run_records_drafts_on_the_firm() -> None:
    agent = _agent("practice_leader")
    await authorise(agent, "methodology.read", Resource.firm(agent.tenant_id))
    await authorise(agent, "guidance_draft.run", Resource.firm(agent.tenant_id))


async def test_d1_never_beyond_its_initiator_s_reach() -> None:
    agent = _agent(None)  # no firm role: may not read the firm's methodology
    with pytest.raises(Forbidden) as raised:
        await authorise(agent, "guidance_draft.run", Resource.firm(agent.tenant_id))
    assert raised.value.layer == "delegation"


async def test_d1_a_firm_level_run_acts_on_no_engagement() -> None:
    agent = _agent("firm_admin")
    engagement = Resource.engagement(agent.tenant_id, uuid.uuid4(), archived=False)
    for action in ("request_item.read", "guidance_draft.run"):
        with pytest.raises(Forbidden) as raised:
            await authorise(agent, action, engagement)
        assert raised.value.layer == "relationship"
    with pytest.raises(Forbidden):
        _ = agent.engagement


async def test_d1_an_engagement_run_acts_on_no_firm_resource() -> None:
    agent = _agent("firm_admin", uuid.uuid4())
    with pytest.raises(Forbidden) as raised:
        await authorise(agent, "methodology.read", Resource.firm(agent.tenant_id))
    assert raised.value.layer == "relationship"


async def test_d1_outside_its_declared_scope_it_is_refused() -> None:
    agent = _agent("firm_admin")
    with pytest.raises(Forbidden):
        await authorise(agent, "methodology.manage", Resource.firm(agent.tenant_id))


def test_d1_a_firm_level_run_lists_no_engagement_s_rows() -> None:
    agent = _agent("firm_admin")
    where = visible(agent, "request_item.read", column("engagement_id"))
    assert str(where.compile(compile_kwargs={"literal_binds": True})) == "false"
