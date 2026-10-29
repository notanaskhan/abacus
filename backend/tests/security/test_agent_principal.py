"""ADR-005, AGENTS.md non-negotiable 5: agents propose, humans decide. An agent principal that
calls a human-only action is refused with a 403 and changes nothing, whatever its task scope
declares and however much its initiator may do.

The principal is the real `AgentContext` the issuer makes for a run (`agent_context_for_run`),
acting for a firm administrator who is also the engagement's partner, the most able initiator
there is. Two views of the same rule: every action in the permission matrix that is not the
agent's at `authorise`, and the routes people use to decide, called over HTTP with the agent as
the principal. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import cast

import httpx
import pytest

from abacus.api import create_app
from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import (
    AgentContext,
    AuthContext,
    Forbidden,
    Resource,
    agent_context_for_run,
    authorise,
    current_context,
)
from abacus.modules.identity.authz.matrix import RULES

from .support import Net, Person, Seeder, Site

AGENT_ID = "evidence.screener"
EVERYTHING = frozenset(RULES)
# What an agent may hold at all: a task-scope grant, or the autonomy policy for routine sends.
AGENT_MAY = frozenset(
    action
    for action, rule in RULES.items()
    if rule.decisions.get("agent") in ("task_scope", "allow")
    or str(rule.decisions.get("agent")).startswith("firm_setting")
)
HUMAN_ONLY = sorted(set(RULES) - AGENT_MAY)


@dataclass(frozen=True)
class Firm:
    tenant_id: uuid.UUID
    site: Site
    initiator: Person
    agent: AgentContext
    finding_id: uuid.UUID


@pytest.fixture
async def firm(seed: Seeder) -> Firm:
    tenant_id = await seed.firm()
    initiator = await seed.person(tenant_id, "firm_admin")
    site = await seed.site(tenant_id, initiator.user_id, "agent")
    await seed.member(site, initiator, "engagement_partner")
    finding_id = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO findings (tenant_id, engagement_id, title, raised_by) "
            "VALUES ($1, $2, 'Cut-off error', $3) RETURNING id",
            tenant_id,
            site.engagement_id,
            initiator.user_id,
        ),
    )
    agent = await agent_context_for_run(
        tenant_id=tenant_id,
        run_id=uuid.uuid4(),
        agent_id=AGENT_ID,
        engagement_id=site.engagement_id,
        task_scope=EVERYTHING,  # the run declares every action, and the matrix still decides
        initiator_user_id=initiator.user_id,
    )
    return Firm(tenant_id, site, initiator, agent, finding_id)


# --- at `authorise`: the whole matrix ------------------------------------------------------------


def test_adr005_the_matrix_has_many_human_only_actions() -> None:
    assert len(HUMAN_ONLY) > 60
    assert "evidence.accept" in HUMAN_ONLY
    assert "evidence.reject" in HUMAN_ONLY
    assert "fulfilment.confirm" in HUMAN_ONLY
    assert "wall.create" in HUMAN_ONLY
    assert "message.send" in HUMAN_ONLY


async def test_adr005_an_agent_is_refused_every_action_the_matrix_does_not_give_it(
    firm: Firm,
) -> None:
    allowed: list[str] = []
    for action in HUMAN_ONLY:
        for resource in (
            Resource.engagement(firm.tenant_id, firm.site.engagement_id, archived=False),
            Resource.firm(firm.tenant_id),
        ):
            try:
                await authorise(firm.agent, action, resource)
            except Forbidden:
                continue
            allowed.append(action)
    assert allowed == []


async def test_adr005_the_same_initiator_as_a_person_is_allowed_what_the_agent_is_refused(
    firm: Firm,
) -> None:
    """The control: the refusal is about the principal, not the action or the resource."""
    person = AuthContext(
        tenant=TenantContext(firm.tenant_id, "human", str(firm.initiator.user_id)),
        user_id=firm.initiator.user_id,
        membership_id=uuid.uuid4(),
        firm_role="firm_admin",
        mfa_at=datetime.now(UTC),
    )
    engagement = Resource.engagement(firm.tenant_id, firm.site.engagement_id, archived=False)
    await authorise(person, "evidence.accept", engagement)
    with pytest.raises(Forbidden) as raised:
        await authorise(firm.agent, "evidence.accept", engagement)
    assert raised.value.layer == "role"


# --- over HTTP: the routes people use to decide --------------------------------------------------


@pytest.fixture
async def as_agent(firm: Firm, net: Net) -> AsyncIterator[httpx.AsyncClient]:
    """The app with its sign-in dependency answering as the agent principal."""
    app = create_app()
    app.dependency_overrides[current_context] = lambda: firm.agent
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _decisions(firm: Firm) -> list[tuple[str, str, dict[str, object] | None]]:
    e = f"/v1/engagements/{firm.site.engagement_id}"
    v = firm.site.version_id
    unknown = uuid.uuid4()
    return [
        ("POST", f"{e}/evidence-versions/{v}/decision/accept", {}),
        ("POST", f"{e}/evidence-versions/{v}/decision/reject", {"reason_code": "other"}),
        ("POST", f"{e}/evidence-versions/{v}/decision/send-back", {"reason_code": "other"}),
        ("POST", f"{e}/review-queue/{v}/assign", {"user_id": str(firm.initiator.user_id)}),
        # SPEC-025's acceptance and independence adapters retired with P-07-T59 (DEC-905); the v2
        # routes refuse an agent at their gates (contracts/acceptance_independence).
        ("POST", f"{e}/team", {"user_id": str(firm.initiator.user_id), "role": "staff"}),
        ("POST", f"{e}/client-invitations", {"email": "x@client.example", "role": "client_admin"}),
        ("POST", f"{e}/materiality/decide", {"rationale": "Benchmark."}),
        ("POST", f"{e}/procedures/{unknown}/workpaper/sign-reviewed", None),
        ("POST", f"{e}/findings", {"title": "Planted"}),
        (
            "POST",
            f"{e}/findings/{firm.finding_id}/severity/conclude",
            {"severity": "material_weakness", "rationale": "Pervasive."},
        ),
        ("POST", f"{e}/adjustments/{unknown}/approve", None),
        ("POST", f"{e}/risks/{unknown}/approve", {}),
        ("PUT", f"{e}/ai-exclusion", {"excluded": True, "reason": "x"}),
        ("POST", f"{e}/agent/pause", {}),
        ("POST", "/v1/walls", {"user_id": str(firm.initiator.user_id), "client_id": str(unknown)}),
        ("PUT", "/v1/firm/autonomy", {"level": 2}),
        ("POST", "/v1/firm/staff/invitations", {"email": "x@firm.example", "firm_role": None}),
    ]


async def _audit_rows(seed: Seeder, tenant_id: uuid.UUID) -> object:
    return await seed.value("SELECT count(*) FROM audit_events WHERE tenant_id = $1", tenant_id)


@pytest.mark.parametrize("index", range(17))
async def test_adr005_an_agent_calling_a_human_only_route_gets_403_and_changes_nothing(
    firm: Firm, as_agent: httpx.AsyncClient, seed: Seeder, index: int
) -> None:
    method, path, body = _decisions(firm)[index]
    before = await _audit_rows(seed, firm.tenant_id)
    response = await as_agent.request(method, path, json=body)
    assert response.status_code == 403, (method, path, response.text)
    assert response.json() == {"detail": "forbidden"}
    assert await _audit_rows(seed, firm.tenant_id) == before


@pytest.mark.parametrize("index", range(17))
async def test_adr005_the_same_route_is_reachable_by_the_person_it_acts_for(
    firm: Firm, net: Net, index: int
) -> None:
    """The control: with a valid body the person gets past authorisation (no 403, no 422)."""
    method, path, body = _decisions(firm)[index]
    response = await net.call(method, path, firm.initiator, body=body)
    assert response.status_code not in (403, 422), (method, path, response.text)
