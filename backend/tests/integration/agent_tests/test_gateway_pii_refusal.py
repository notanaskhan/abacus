"""Q-02 AC-22 (Q-02-T32; ADR-167 §2): an unmasked TIN in model context is refused, against a real
database, on the real route and on the fake one, for a synthetic firm too.

The refusal comes before any network call (the stub records every call it gets), is audited once
as `ai.boundary_refused` with the reason and the context part (indices only, never the value),
writes no usage record and is not retried or rerouted. A masked form passes and the call is made.
The TIN is a 9xx ITIN form (ADR-085). Expectations come from the spec, not the implementation.
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
    FakeModel,
    GatewayCall,
    ModelRequest,
    ModelResponse,
    call,
    configure_provider,
)
from abacus.ai_gateway.boundary import REASONS, DataBoundaryRefused, clear_cache
from abacus.ai_gateway.pii import PARTS
from abacus.ai_gateway.providers import Tier
from abacus.ai_gateway.routes import configure_route
from abacus.kernel.classification import mask
from abacus.kernel.config import Route, settings
from abacus.kernel.db import TenantContext

from .support import Seeder, World

REF = "evidence.screen@v0"
AGENT_ID = "evidence.screener"
REPLY = json.dumps({"action": "ready", "confidence": 0.9})
ITIN = "900-70-1234"


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
def bedrock(monkeypatch: pytest.MonkeyPatch) -> Iterator[Stub]:
    provider = Stub()
    configure_route("bedrock", provider)
    configure_provider(None)
    monkeypatch.setattr(gateway, "route_enabled", _only_bedrock)
    monkeypatch.setattr(gateway, "model_id", _fake_models_on_bedrock)
    clear_cache()
    yield provider
    configure_route("bedrock", None)
    clear_cache()


@pytest.fixture
def fake() -> Iterator[list[ModelRequest]]:
    seen: list[ModelRequest] = []

    def responder(request: ModelRequest) -> str:
        seen.append(request)
        return REPLY

    configure_provider(FakeModel({REF: responder}))
    clear_cache()
    yield seen
    configure_provider(None)
    clear_cache()


def _call(world: World, value: str) -> GatewayCall[Verdict]:
    actor = f"agent:{AGENT_ID}:{uuid.uuid4()}"
    return GatewayCall(
        purpose="screen a W-2",
        prompt=REF,
        tier="small",
        output_schema=Verdict,
        work_class="time_sensitive",
        routes=("bedrock", "direct"),
        essential=True,
        budget_usd=Decimal("0.05"),
        attribution=Attribution(
            TenantContext(world.tenant_id, "agent", actor, uuid.uuid4()),
            world.engagement_id,
            AGENT_ID,
            None,
        ),
        context=ContextBuilder()
        .text("engagement", "Period 2025.")
        .task(
            {"balanced": True, "document": {"lines": ["Form W-2", f"a {value}"]}},
            untrusted=("document",),
        )
        .build(),
        max_output_tokens=200,
    )


async def _refusals(seed: Seeder, world: World) -> list[dict[str, object]]:
    rows = await seed.rows(
        "SELECT after_ref::text AS after FROM audit_events WHERE tenant_id = $1 AND action = $2",
        world.tenant_id,
        "ai.boundary_refused",
    )
    return [json.loads(r["after"]) for r in rows]


async def _synthetic(seed: Seeder, world: World) -> None:
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", world.tenant_id)
    clear_cache(world.tenant_id)


async def test_ac22_a_synthetic_firm_on_the_real_route_is_refused_before_the_network(
    seed: Seeder, world: World, bedrock: Stub
) -> None:
    await _synthetic(seed, world)  # the firm would pass the boundary: the TIN alone refuses
    with pytest.raises(DataBoundaryRefused) as raised:
        await call(_call(world, ITIN))
    assert raised.value.reason == "pii_in_context"
    assert bedrock.calls == []
    [refusal] = await _refusals(seed, world)
    assert refusal == {
        "reason": REASONS.index("pii_in_context"),
        "part": PARTS.index("untrusted"),
    }
    assert ITIN not in json.dumps(refusal) and "900701234" not in json.dumps(refusal)
    assert await seed.count("usage_records", world.tenant_id) == 0  # not billed, not retried


async def test_ac22_the_fake_route_refuses_too(
    seed: Seeder, world: World, fake: list[ModelRequest]
) -> None:
    with pytest.raises(DataBoundaryRefused) as raised:
        await call(_call(world, ITIN))
    assert raised.value.reason == "pii_in_context"
    assert fake == []
    assert len(await _refusals(seed, world)) == 1
    assert await seed.count("usage_records", world.tenant_id) == 0


async def test_ac22_a_masked_form_passes_and_the_call_is_made(
    seed: Seeder, world: World, fake: list[ModelRequest]
) -> None:
    await seed.run("DELETE FROM provider_capacity")  # another test's block on the fake model
    result = await call(_call(world, mask(ITIN, "tin")))
    assert result.status == "ok"
    assert len(fake) == 1
    assert await _refusals(seed, world) == []
