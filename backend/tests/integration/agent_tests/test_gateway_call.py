"""AC-16: `ai_gateway.call` against a real database (TASK-011a contract, "Gateway `call`").

One `usage_records` row per provider attempt, each with a `model.called` audit event by the
attribution's actor; refusals record nothing. The model is a `FakeModel` with scripted replies.
Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Iterator
from dataclasses import replace
from decimal import Decimal
from typing import Literal, cast

import asyncpg
import pytest
from pydantic import BaseModel, Field

from abacus.ai_gateway import (
    MODELS,
    Attribution,
    BudgetExceeded,
    ContextBuilder,
    FakeModel,
    GatewayCall,
    GatewayRefused,
    ModelRequest,
    ProviderError,
    Tier,
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


GOOD = json.dumps({"action": "ready", "confidence": 0.9})
BAD = '{"action": "maybe", "confidence": 7, "note": "ECHOED-BACK-MARKER"}'


class Scripted:
    """Replays replies in order (repeating the last) and records the requests."""

    def __init__(self, *replies: str) -> None:
        self.replies = replies
        self.requests: list[ModelRequest] = []

    def __call__(self, request: ModelRequest) -> str:
        self.requests.append(request)
        return self.replies[min(len(self.requests), len(self.replies)) - 1]


def _install(*replies: str) -> Scripted:
    script = Scripted(*replies)
    fake = FakeModel()
    fake.respond(REF, script)
    configure_provider(fake)
    return script


@pytest.fixture(autouse=True)
def _reset_provider() -> Iterator[None]:
    yield
    configure_provider(None)


def _attribution(world: World, run_id: uuid.UUID | None = None) -> Attribution:
    actor = f"agent:{AGENT_ID}:{run_id or uuid.uuid4()}"
    return Attribution(
        TenantContext(world.tenant_id, "agent", actor), world.engagement_id, AGENT_ID, run_id
    )


def _call(
    world: World,
    *,
    tier: Tier = "small",
    budget: Decimal = Decimal("0.05"),
    purpose: str = "screen a trial balance",
    prompt_ref: str = REF,
    attribution: Attribution | None = None,
    max_output_tokens: int = 200,
) -> GatewayCall[Verdict]:
    built = ContextBuilder().text("engagement", "Period 2025.").task({"balanced": True}).build()
    return GatewayCall(
        purpose=purpose,
        prompt=prompt_ref,
        tier=tier,
        output_schema=Verdict,
        work_class="time_sensitive",  # SPEC-003 018c: every call declares its class
        essential=True,
        budget_usd=budget,
        attribution=attribution or _attribution(world),
        context=built,
        max_output_tokens=max_output_tokens,
    )


async def _usage(seed: Seeder, world: World) -> list[asyncpg.Record]:
    return await seed.rows(
        "SELECT * FROM usage_records WHERE tenant_id = $1 ORDER BY created_at", world.tenant_id
    )


def _estimate(c: GatewayCall[Verdict]) -> Decimal:
    user = c.context.render()
    tokens = estimate_tokens(prompt(c.prompt).text + user)
    return cost(c.tier, tokens, c.max_output_tokens)


# --- the happy path ------------------------------------------------------------------------------


async def test_ac16_a_valid_reply_is_ok_in_one_attempt_with_one_usage_record(
    seed: Seeder, world: World
) -> None:
    script = _install(GOOD)
    c = _call(world)
    result = await call(c)
    assert result.status == "ok"
    assert result.attempts == 1
    assert result.output == Verdict(action="ready", confidence=0.9)
    assert len(script.requests) == 1
    [row] = await _usage(seed, world)
    assert row["tenant_id"] == world.tenant_id
    assert row["engagement_id"] == world.engagement_id
    assert row["agent_id"] == AGENT_ID
    assert row["agent_run_id"] is None
    assert (row["prompt_id"], row["prompt_version"]) == ("evidence.screen", "v0")
    assert row["model"] == MODELS["small"][0]
    assert row["tier"] == "small"
    assert row["outcome"] == "ok"
    assert row["input_tokens"] > 0
    assert row["output_tokens"] > 0
    assert row["cost_usd"] == cost("small", row["input_tokens"], row["output_tokens"])
    assert result.cost_usd == row["cost_usd"]


async def test_ac16_the_provider_gets_the_registered_prompt_and_the_rendered_context(
    seed: Seeder, world: World
) -> None:
    script = _install(GOOD)
    c = _call(world, max_output_tokens=321)
    await call(c)
    [request] = script.requests
    assert request.model == MODELS["small"][0]
    assert request.system == prompt(REF).text
    assert request.user == c.context.render()
    assert request.max_output_tokens == 321
    assert request.prompt_ref == REF


async def test_ac16_the_inputs_hash_is_the_sha256_of_the_reference_and_the_user_text(
    seed: Seeder, world: World
) -> None:
    script = _install(GOOD)
    result = await call(_call(world))
    expected = hashlib.sha256(f"{REF}\n{script.requests[0].user}".encode()).hexdigest()
    assert result.inputs_hash == expected
    [row] = await _usage(seed, world)
    assert row["inputs_hash"] == expected


@pytest.mark.parametrize("tier", ["small", "medium", "large"])
async def test_ac16_each_tier_routes_to_its_model_and_is_priced_from_its_table(
    seed: Seeder, world: World, tier: Tier
) -> None:
    script = _install(GOOD)
    result = await call(_call(world, tier=tier, budget=Decimal("5")))
    assert script.requests[0].model == MODELS[tier][0]
    assert result.model == MODELS[tier][0]
    [row] = await _usage(seed, world)
    assert (row["tier"], row["model"]) == (tier, MODELS[tier][0])
    assert row["cost_usd"] == cost(tier, row["input_tokens"], row["output_tokens"])


async def test_ac16_each_usage_record_comes_with_a_model_called_event_by_the_attribution(
    seed: Seeder, world: World
) -> None:
    _install(BAD, GOOD)
    attribution = _attribution(world)
    before = len(await seed.events(world.tenant_id))
    await call(_call(world, attribution=attribution))
    rows = await _usage(seed, world)
    events = (await seed.events(world.tenant_id))[before:]
    assert [e.action for e in events] == ["model.called", "model.called"]
    assert {(e.actor_kind, e.actor_id) for e in events} == {("agent", attribution.tenant.actor_id)}
    assert {e.target_id for e in events} == {str(r["id"]) for r in rows}


async def test_ac16_the_usage_record_never_carries_the_model_output_or_context(
    seed: Seeder, world: World
) -> None:
    _install(GOOD)
    await call(_call(world))
    [row] = await _usage(seed, world)
    blob = json.dumps({k: str(v) for k, v in dict(row).items()})
    assert "balanced" not in blob
    assert "Period 2025" not in blob
    assert "ready" not in blob


# --- repair and escalation -----------------------------------------------------------------------


async def test_ac14_an_invalid_reply_then_a_valid_one_is_repaired_in_two_attempts(
    seed: Seeder, world: World
) -> None:
    script = _install(BAD, GOOD)
    c = _call(world)
    result = await call(c)
    assert (result.status, result.attempts) == ("repaired", 2)
    assert result.output == Verdict(action="ready", confidence=0.9)
    first, second = script.requests
    assert first.user == c.context.render()
    assert second.user.startswith(c.context.render())
    assert "## repair" in second.user
    repair = second.user.split("## repair", 1)[1]
    assert "action" in repair  # where the first reply failed the schema
    assert "confidence" in repair
    assert second.system == first.system
    assert second.prompt_ref == REF
    rows = await _usage(seed, world)
    assert [r["outcome"] for r in rows] == ["invalid", "repaired"]
    assert result.cost_usd == sum((cast(Decimal, r["cost_usd"]) for r in rows), Decimal(0))


async def test_ac14_the_repair_request_does_not_echo_the_invalid_reply(world: World) -> None:
    script = _install(BAD, GOOD)
    await call(_call(world))
    assert "ECHOED-BACK-MARKER" not in script.requests[1].user


async def test_ac14_two_invalid_replies_escalate_with_no_output(
    seed: Seeder, world: World
) -> None:
    script = _install(BAD)
    result = await call(_call(world))
    assert result.status == "escalated"
    assert result.output is None
    assert len(script.requests) == 2
    assert [r["outcome"] for r in await _usage(seed, world)] == ["invalid", "invalid"]


async def test_ac14_a_reply_that_is_not_json_is_invalid_not_an_error(
    seed: Seeder, world: World
) -> None:
    _install("plain prose, no braces at all", GOOD)
    result = await call(_call(world))
    assert result.status == "repaired"


# --- budget --------------------------------------------------------------------------------------


async def test_ac16_a_budget_below_the_estimate_is_refused_before_the_provider_is_called(
    seed: Seeder, world: World
) -> None:
    script = _install(GOOD)
    with pytest.raises(BudgetExceeded):
        await call(_call(world, budget=Decimal("0.000001")))
    assert script.requests == []
    [row] = await _usage(seed, world)
    assert row["outcome"] == "budget_refused"
    assert row["input_tokens"] == 0
    assert row["output_tokens"] == 0
    assert row["cost_usd"] == 0
    assert row["tier"] == "small"


async def test_ac16_a_budget_exactly_the_estimate_is_allowed(seed: Seeder, world: World) -> None:
    _install(GOOD)
    c = _call(world)
    exact = _estimate(c)
    result = await call(_call(world, budget=exact))
    assert result.status == "ok"


async def test_ac16_a_budget_one_micro_dollar_under_the_estimate_is_refused(
    seed: Seeder, world: World
) -> None:
    script = _install(GOOD)
    under = _estimate(_call(world)) - Decimal("0.000001")
    with pytest.raises(BudgetExceeded):
        await call(_call(world, budget=under))
    assert script.requests == []


async def test_ac16_a_repair_that_would_overrun_the_budget_escalates_and_records_a_refusal(
    seed: Seeder, world: World
) -> None:
    script = _install(BAD, GOOD)
    first_estimate = _estimate(_call(world))
    result = await call(_call(world, budget=first_estimate))
    assert result.status == "escalated"
    assert result.output is None
    assert len(script.requests) == 1
    rows = await _usage(seed, world)
    assert [r["outcome"] for r in rows] == ["invalid", "budget_refused"]
    assert rows[1]["cost_usd"] == 0


# --- provider errors -----------------------------------------------------------------------------


async def test_ac16_a_provider_error_is_recorded_and_reraised(seed: Seeder, world: World) -> None:
    configure_provider(FakeModel())  # no responder for the prompt: a ProviderError
    c = _call(world)
    with pytest.raises(ProviderError):
        await call(c)
    [row] = await _usage(seed, world)
    assert row["outcome"] == "provider_error"
    assert row["input_tokens"] == 0
    # Contract revision 1 (011b): a failed call is billed its input estimate, not 0.
    expected = cost(c.tier, estimate_tokens(prompt(c.prompt).text + c.context.render()), 0)
    assert expected > 0
    assert row["cost_usd"] == expected
    assert "model.called" in await seed.actions(world.tenant_id)


# --- refusals ------------------------------------------------------------------------------------


def _refusals(world: World) -> list[tuple[str, GatewayCall[Verdict]]]:
    base = _call(world)
    return [
        ("blank purpose", _call(world, purpose="")),
        ("whitespace purpose", _call(world, purpose="   ")),
        ("not a pydantic schema", _replace(base, output_schema=cast(type[Verdict], dict))),
        ("zero budget", _call(world, budget=Decimal(0))),
        ("negative budget", _call(world, budget=Decimal("-1"))),
        ("unknown tier", _call(world, tier=cast(Tier, "huge"))),
        (
            "no tenant context",
            _call(
                world,
                attribution=Attribution(
                    cast(TenantContext, None), world.engagement_id, AGENT_ID, None
                ),
            ),
        ),
        (
            "no agent id",
            _call(
                world,
                attribution=Attribution(
                    TenantContext(world.tenant_id, "agent", f"agent:{AGENT_ID}:{uuid.uuid4()}"),
                    world.engagement_id,
                    "",
                    None,
                ),
            ),
        ),
        ("unregistered prompt", _call(world, prompt_ref="evidence.nothing@v9")),
        ("known id, unknown version", _call(world, prompt_ref="evidence.screen@v99")),
        ("malformed reference", _call(world, prompt_ref="evidence.screen")),
        ("empty reference", _call(world, prompt_ref="")),
        ("inline prompt text", _call(world, prompt_ref="You are a helpful assistant")),
    ]


def _replace(base: GatewayCall[Verdict], **changes: object) -> GatewayCall[Verdict]:
    return replace(base, **changes)


REFUSAL_NAMES = [
    "blank purpose",
    "whitespace purpose",
    "not a pydantic schema",
    "zero budget",
    "negative budget",
    "unknown tier",
    "no tenant context",
    "no agent id",
    "unregistered prompt",
    "known id, unknown version",
    "malformed reference",
    "empty reference",
    "inline prompt text",
]


@pytest.mark.parametrize("name", REFUSAL_NAMES)
async def test_ac16_a_call_missing_what_the_gateway_requires_is_refused_and_records_nothing(
    seed: Seeder, world: World, name: str
) -> None:
    script = _install(GOOD)
    c = dict(_refusals(world))[name]
    events = await seed.count("audit_events", world.tenant_id)
    with pytest.raises(GatewayRefused):
        await call(c)
    assert script.requests == []
    assert await _usage(seed, world) == []
    assert await seed.count("audit_events", world.tenant_id) == events
