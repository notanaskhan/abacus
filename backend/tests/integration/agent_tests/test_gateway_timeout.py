"""AC-16: `GatewayCall.timeout_seconds` bounds each provider call (TASK-011b contract, "Gateway and
spec changes"). A timeout records a `provider_error` usage row and raises `ProviderError`."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import time
import uuid
from collections.abc import Iterator
from decimal import Decimal
from typing import Literal

import pytest
from pydantic import BaseModel, Field

from abacus.ai_gateway import (
    Attribution,
    ContextBuilder,
    GatewayCall,
    ModelRequest,
    ModelResponse,
    ProviderError,
    call,
    configure_provider,
    cost,
    estimate_tokens,
    prompt,
)
from abacus.kernel.db import TenantContext

from .support import Seeder, World

REF = "evidence.screen@v0"
AGENT_ID = "evidence.screener"


class Verdict(BaseModel):
    action: Literal["ready", "revise"]
    confidence: float = Field(ge=0, le=1)


class Slow:
    """A provider that takes `delay` seconds to answer."""

    def __init__(self, delay: float) -> None:
        self.delay = delay
        self.started = 0
        self.finished = 0

    async def complete(self, request: ModelRequest) -> ModelResponse:
        self.started += 1
        await asyncio.sleep(self.delay)
        self.finished += 1
        text = json.dumps({"action": "ready", "confidence": 0.9})
        return ModelResponse(text, 10, 5, request.model)


@pytest.fixture(autouse=True)
def _reset_provider() -> Iterator[None]:
    yield
    configure_provider(None)


def _call(world: World) -> GatewayCall[Verdict]:
    actor = f"agent:{AGENT_ID}:{uuid.uuid4()}"
    built = ContextBuilder().text("engagement", "Period 2025.").task({"balanced": True}).build()
    return GatewayCall(
        purpose="screen a trial balance",
        prompt=REF,
        tier="small",
        output_schema=Verdict,
        budget_usd=Decimal("0.05"),
        attribution=Attribution(
            TenantContext(world.tenant_id, "agent", actor), world.engagement_id, AGENT_ID, None
        ),
        context=built,
        max_output_tokens=200,
    )


def test_ac16_the_default_timeout_is_sixty_seconds() -> None:
    fields = {f.name: f for f in dataclasses.fields(GatewayCall)}
    assert fields["timeout_seconds"].default == 60


async def test_ac16_a_provider_call_past_its_timeout_raises_provider_error_and_is_recorded(
    seed: Seeder, world: World
) -> None:
    provider = Slow(delay=5)
    configure_provider(provider)
    started = time.monotonic()
    with pytest.raises(ProviderError):
        await call(dataclasses.replace(_call(world), timeout_seconds=0.1))
    assert time.monotonic() - started < 3
    assert provider.started == 1
    assert provider.finished == 0
    [usage] = await seed.rows(
        "SELECT outcome, cost_usd, agent_id, engagement_id "
        "FROM usage_records WHERE tenant_id = $1",
        world.tenant_id,
    )
    assert usage["outcome"] == "provider_error"
    # A failed call is billed for its input estimate, not recorded as free.
    c = _call(world)
    expected = cost(c.tier, estimate_tokens(prompt(REF).text + c.context.render()), 0)
    assert usage["cost_usd"] == expected
    assert expected > 0
    assert (usage["agent_id"], usage["engagement_id"]) == (AGENT_ID, world.engagement_id)
    assert "model.called" in await seed.actions(world.tenant_id)


async def test_ac16_a_timeout_surfaces_as_provider_error_not_timeout_error(world: World) -> None:
    configure_provider(Slow(delay=5))
    with pytest.raises(ProviderError) as caught:
        await call(dataclasses.replace(_call(world), timeout_seconds=0.05))
    assert not isinstance(caught.value, TimeoutError)
    assert type(caught.value) is ProviderError


async def test_ac16_a_provider_call_within_its_timeout_is_recorded_as_ok(
    seed: Seeder, world: World
) -> None:
    provider = Slow(delay=0.05)
    configure_provider(provider)
    result = await call(dataclasses.replace(_call(world), timeout_seconds=5))
    assert result.status == "ok"
    [usage] = await seed.rows(
        "SELECT outcome FROM usage_records WHERE tenant_id = $1", world.tenant_id
    )
    assert usage["outcome"] == "ok"


async def test_ac16_the_timeout_applies_to_each_provider_call_not_the_whole_call(
    seed: Seeder, world: World
) -> None:
    # Two attempts (invalid, then repaired) each take 0.3s, past 0.5s together, within it singly.
    class Twice(Slow):
        async def complete(self, request: ModelRequest) -> ModelResponse:
            response = await super().complete(request)
            if self.finished == 1:
                return ModelResponse("not json", 10, 5, request.model)
            return response

    provider = Twice(delay=0.3)
    configure_provider(provider)
    result = await call(dataclasses.replace(_call(world), timeout_seconds=0.5))
    assert result.status == "repaired"
    assert provider.finished == 2
    outcomes = [
        r["outcome"]
        for r in await seed.rows(
            "SELECT outcome FROM usage_records WHERE tenant_id = $1 ORDER BY created_at",
            world.tenant_id,
        )
    ]
    assert outcomes == ["invalid", "repaired"]
