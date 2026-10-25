"""SPEC-319 AC-27 at the gateway (P-06-T20 security review; DEC-324): tax-return information
reaches no model at a firm that is not synthetic.

C19's §7216 consent registration does not exist yet, so the boundary step refuses fails closed
any agent call attributed to an engagement holding a `tax_return` work item, for every agent:
the screener, the inbox matcher and the upload reviewer. The refusal is non-retryable
(`DataBoundaryRefused`), audited, and no network call is made. A synthetic firm passes.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from dataclasses import dataclass, field
from decimal import Decimal

import pytest
from pydantic import BaseModel

import abacus.ai_gateway as gateway
from abacus.ai_gateway import (
    Attribution,
    ContextBuilder,
    GatewayCall,
    ModelRequest,
    ModelResponse,
    call,
    configure_provider,
)
from abacus.ai_gateway.boundary import REASONS, DataBoundaryRefused, clear_cache
from abacus.ai_gateway.providers import Tier
from abacus.ai_gateway.routes import configure_route
from abacus.kernel.config import Route, settings
from abacus.kernel.db import TenantContext

from .support import Seeder, World

AGENTS = [
    ("evidence.screener", "evidence.screen@v0"),
    ("evidence.matcher", "evidence.inbox_match@v2"),
    ("evidence.upload_reviewer", "evidence.upload_review@v3"),
]
REPLY = json.dumps({"action": "ready", "confidence": 0.9})


class Verdict(BaseModel):
    action: str
    confidence: float


@dataclass
class Stub:
    calls: list[ModelRequest] = field(default_factory=list[ModelRequest])

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(REPLY, 100, 20, request.model)


def _only_bedrock(route: Route) -> bool:
    return route == "bedrock"


def _fake_models_on_bedrock(tier: Tier, route: Route) -> str | None:
    return settings().model_catalog[tier].ids.get("fake")


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[Stub]:
    provider = Stub()
    configure_route("bedrock", provider)
    configure_provider(None)
    monkeypatch.setattr(gateway, "route_enabled", _only_bedrock)
    monkeypatch.setattr(gateway, "model_id", _fake_models_on_bedrock)
    clear_cache()
    yield provider
    configure_route("bedrock", None)
    clear_cache()


async def _tax_return(seed: Seeder, world: World) -> None:
    await seed.run(
        "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, kind, "
        "name, created_by) SELECT e.tenant_id, e.id, e.client_id, e.client_entity_id, "
        "'tax_return', 'Example 2025 return', $2 FROM engagements e WHERE e.id = $1",
        world.engagement_id,
        world.requester.user_id,
    )


def _call(world: World, agent_id: str, ref: str) -> GatewayCall[Verdict]:
    return GatewayCall(
        purpose="read an upload",
        prompt=ref,
        tier="small",
        output_schema=Verdict,
        work_class="time_sensitive",
        routes=("bedrock", "direct"),
        essential=True,
        budget_usd=Decimal("0.05"),
        attribution=Attribution(
            TenantContext(
                world.tenant_id, "agent", f"agent:{agent_id}:{uuid.uuid4()}", uuid.uuid4()
            ),
            world.engagement_id,
            agent_id,
            None,
        ),
        context=ContextBuilder().text("engagement", "Tax year 2025.").task({"a": 1}).build(),
        max_output_tokens=200,
    )


@pytest.mark.parametrize(("agent_id", "ref"), AGENTS)
async def test_ac27_every_agent_is_refused_tax_return_information_at_a_real_firm(
    seed: Seeder, world: World, stub: Stub, agent_id: str, ref: str
) -> None:
    await _tax_return(seed, world)
    with pytest.raises(DataBoundaryRefused) as raised:
        await call(_call(world, agent_id, ref))
    assert raised.value.reason == "tax_return_information"
    assert stub.calls == []
    rows = await seed.rows(
        "SELECT after_ref::text AS after FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'ai.boundary_refused'",
        world.tenant_id,
    )
    assert [json.loads(r["after"])["reason"] for r in rows] == [
        REASONS.index("tax_return_information")
    ]
    with pytest.raises(DataBoundaryRefused):  # never retried into a pass
        await call(_call(world, agent_id, ref))
    assert stub.calls == []


async def test_ac27_a_synthetic_firms_tax_return_work_still_reaches_the_model(
    seed: Seeder, world: World, stub: Stub
) -> None:
    await _tax_return(seed, world)
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    clear_cache(world.tenant_id)
    agent_id, ref = AGENTS[0]
    result = await call(_call(world, agent_id, ref))
    assert result.status == "ok"
    assert len(stub.calls) == 1


async def test_ac27_an_engagement_without_tax_return_work_keeps_its_old_reason(
    world: World, stub: Stub
) -> None:
    agent_id, ref = AGENTS[1]
    with pytest.raises(DataBoundaryRefused) as raised:
        await call(_call(world, agent_id, ref))
    assert raised.value.reason == "route"  # the shipped settings, unchanged
