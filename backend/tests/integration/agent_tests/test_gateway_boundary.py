"""SPEC-036 AC-2, AC-8 (TASK-075): the five-part check on every real-route call, through
`ai_gateway.call` against a real database and a stub provider on the real route.

A firm that is not synthetic reaches a real model only when every condition holds. With the
settings the product ships (`model_data_boundary: synthetic_only`, an empty provider terms
register) none does: the call is refused with its reason, no network call is made (the stub
records every call it gets), it is audited and counted once, and it is not retried or sent to
another route. A synthetic firm is unaffected, and its usage record says which basis allowed it.
Expectations come from the spec, not the implementation.
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
    prompt,
)
from abacus.ai_gateway.boundary import REASONS, DataBoundaryRefused, clear_cache
from abacus.ai_gateway.providers import Tier
from abacus.ai_gateway.routes import configure_route
from abacus.kernel.config import Route, settings
from abacus.kernel.db import TenantContext

from .support import Seeder, World

REF = "evidence.screen@v0"
AGENT_ID = "evidence.screener"
REPLY = json.dumps({"action": "ready", "confidence": 0.9})


class Verdict(BaseModel):
    action: str
    confidence: float


@dataclass
class Stub:
    """A real route's provider that records every call it receives."""

    calls: list[ModelRequest] = field(default_factory=list[ModelRequest])

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.calls.append(request)
        return ModelResponse(REPLY, 100, 20, request.model)


def _only_bedrock(route: Route) -> bool:
    return route == "bedrock"


def _only_direct(route: Route) -> bool:
    return route == "direct"


def _fake_models_on_bedrock(tier: Tier, route: Route) -> str | None:
    """Bedrock serves the catalog's models here, so the stub is admitted like the fake route."""
    return settings().model_catalog[tier].ids.get("fake")


@pytest.fixture
def stub(monkeypatch: pytest.MonkeyPatch) -> Iterator[Stub]:
    """Only the real `bedrock` route is enabled (the fake route is off), with a stub on it."""
    provider = Stub()
    configure_route("bedrock", provider)
    configure_provider(None)
    monkeypatch.setattr(gateway, "route_enabled", _only_bedrock)
    monkeypatch.setattr(gateway, "model_id", _fake_models_on_bedrock)
    clear_cache()
    yield provider
    configure_route("bedrock", None)
    clear_cache()


def _call(world: World) -> GatewayCall[Verdict]:
    actor = f"agent:{AGENT_ID}:{uuid.uuid4()}"
    return GatewayCall(
        purpose="screen a trial balance",
        prompt=REF,
        tier="small",
        output_schema=Verdict,
        work_class="time_sensitive",
        routes=("bedrock", "direct"),
        essential=True,
        budget_usd=Decimal("0.05"),
        attribution=Attribution(
            TenantContext(world.tenant_id, "agent", actor), world.engagement_id, AGENT_ID, None
        ),
        context=ContextBuilder()
        .text("engagement", "Period 2025.")
        .task({"balanced": True})
        .build(),
        max_output_tokens=200,
    )


async def _events(seed: Seeder, world: World, action: str) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT after_ref::text AS after FROM audit_events WHERE tenant_id = $1 AND action = $2",
        world.tenant_id,
        action,
    )
    return [json.loads(r["after"]) for r in rows]


async def test_ac2_a_real_firm_is_refused_on_the_real_route_and_nothing_leaves(
    seed: Seeder, world: World, stub: Stub
) -> None:
    assert prompt(REF)
    with pytest.raises(DataBoundaryRefused) as raised:
        await call(_call(world))
    assert raised.value.reason == "route"  # settings keep the boundary at synthetic_only
    assert stub.calls == []  # no network call was made
    [refusal] = await _events(seed, world, "ai.boundary_refused")  # audited, once
    assert refusal["reason"] == REASONS.index("route")
    assert await seed.count("usage_records", world.tenant_id) == 0  # not retried, not billed


async def test_ac2_a_refusal_is_not_retried_or_rerouted_on_a_second_identical_call(
    seed: Seeder, world: World, stub: Stub
) -> None:
    for _ in range(2):
        with pytest.raises(DataBoundaryRefused):
            await call(_call(world))
    assert stub.calls == []
    assert len(await _events(seed, world, "ai.boundary_refused")) == 2  # one per call, no more


async def test_ac2_the_direct_route_is_never_used_for_a_real_firm(
    seed: Seeder, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    direct = Stub()
    configure_route("direct", direct)
    monkeypatch.setattr(gateway, "route_enabled", _only_direct)
    monkeypatch.setattr(gateway, "model_id", _fake_models_on_bedrock)
    clear_cache()
    try:
        with pytest.raises(DataBoundaryRefused) as raised:
            await call(_call(world))
    finally:
        configure_route("direct", None)
    assert raised.value.reason == "route"
    assert direct.calls == []


async def test_ac8_a_synthetic_firm_is_unaffected_and_its_usage_says_why(
    seed: Seeder, world: World, stub: Stub
) -> None:
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    clear_cache(world.tenant_id)
    result = await call(_call(world))
    assert result.status == "ok"
    assert len(stub.calls) == 1
    [row] = await seed.rows(
        "SELECT boundary_basis, route FROM usage_records WHERE tenant_id = $1", world.tenant_id
    )
    assert (row["boundary_basis"], row["route"]) == ("synthetic", "bedrock")
    assert await _events(seed, world, "ai.boundary_refused") == []
