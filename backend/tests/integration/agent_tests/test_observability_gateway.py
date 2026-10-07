"""AC-16, AC-20: the `ai.call` span and its `ai.attempt` events (TASK-013 interface contract,
"Gateway"; ADR-019, ADR-022).

One span per `call()` with identifiers and outcome as attributes, one event per attempt, and
never the prompt, the rendered context or the model's output. The model is a `FakeModel` with
scripted replies. Expectations come from the contract.
"""

from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from contextlib import suppress
from decimal import Decimal
from typing import Literal

import pytest
from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import StatusCode
from pydantic import BaseModel, Field

from abacus.ai_gateway import (
    MODELS,
    Attribution,
    BudgetExceeded,
    ContextBuilder,
    FakeModel,
    GatewayCall,
    GatewayResult,
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
from abacus.kernel.telemetry import current_trace_id, tracer

from . import tracing_support
from .support import World

REF = "evidence.screen@v0"
AGENT_ID = "evidence.screener"
CONTEXT_MARKER = "CONTEXT-MARKER-5120-trial-balance-row"
GOOD = json.dumps({"action": "ready", "confidence": 0.9})
BAD = '{"action": "maybe", "confidence": 7, "note": "ECHOED-BACK-MARKER-6642"}'


class Verdict(BaseModel):
    action: Literal["ready", "revise"]
    confidence: float = Field(ge=0, le=1)


class Scripted:
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


@pytest.fixture(autouse=True)
def exporter() -> InMemorySpanExporter:
    memory = tracing_support.install()
    memory.clear()
    return memory


def _call(
    world: World,
    *,
    tier: Tier = "small",
    budget: Decimal = Decimal("0.05"),
    purpose: str = "screen a trial balance",
) -> GatewayCall[Verdict]:
    run_id = uuid.uuid4()
    actor = f"agent:{AGENT_ID}:{run_id}"
    return GatewayCall(
        purpose=purpose,
        prompt=REF,
        tier=tier,
        output_schema=Verdict,
        work_class="time_sensitive",  # SPEC-003 018c: every call declares its class
        routes=("bedrock", "direct"),  # SPEC-010: the fake route serves synthetic runs
        essential=True,
        budget_usd=budget,
        attribution=Attribution(
            TenantContext(world.tenant_id, "agent", actor), world.engagement_id, AGENT_ID, None
        ),
        context=ContextBuilder()
        .text("engagement", CONTEXT_MARKER)
        .task({"balanced": True})
        .build(),
        max_output_tokens=200,
    )


async def _traced(c: GatewayCall[Verdict]) -> tuple[str, list[ReadableSpan]]:
    """Run `call(c)` under a parent span; return its trace ID and that trace's spans."""
    with tracer("test").start_as_current_span("parent"):
        trace_id = current_trace_id()
        assert trace_id is not None
        with suppress(BudgetExceeded, ProviderError):
            await call(c)
    return trace_id, tracing_support.spans_of(trace_id)


def _ai_calls(spans: list[ReadableSpan]) -> list[ReadableSpan]:
    return [s for s in spans if s.name == "ai.call"]


def _attempts(span: ReadableSpan) -> list[dict[str, object]]:
    return [dict(e.attributes or {}) for e in span.events if e.name == "ai.attempt"]


# --- the span ------------------------------------------------------------------------------------


async def test_ac20_a_call_makes_exactly_one_ai_call_span_in_the_callers_trace(
    world: World,
) -> None:
    _install(GOOD)
    trace_id, spans = await _traced(_call(world))
    [span] = _ai_calls(spans)
    assert tracing_support.trace_hex(span) == trace_id
    assert span.parent is not None


async def test_ac20_the_ai_call_span_carries_the_call_and_its_result(world: World) -> None:
    _install(GOOD)
    c = _call(world, tier="small", purpose="screen a trial balance")
    with tracer("test").start_as_current_span("parent"):
        trace_id = current_trace_id()
        assert trace_id is not None
        result: GatewayResult[Verdict] = await call(c)
    [span] = _ai_calls(tracing_support.spans_of(trace_id))
    attributes = dict(span.attributes or {})
    assert attributes["ai.prompt"] == REF
    assert attributes["ai.tier"] == "small"
    assert attributes["ai.agent_id"] == AGENT_ID
    assert "ai.purpose" not in attributes  # free text: stays in the usage record
    assert "ai.inputs_hash" not in attributes  # a hash of client context
    assert attributes["ai.status"] == "ok" == result.status
    assert attributes["ai.attempts"] == 1 == result.attempts
    assert attributes["ai.model"] == MODELS["small"][0] == result.model
    assert re.fullmatch(r"[0-9a-f]{64}", result.inputs_hash)
    cost = attributes["ai.cost_usd"]
    assert isinstance(cost, str)  # a string: never a float
    assert Decimal(cost) == result.cost_usd
    assert Decimal(cost) > 0


@pytest.mark.parametrize("tier", ["small", "medium", "large"])
async def test_ac20_the_span_names_the_tier_and_its_model(world: World, tier: Tier) -> None:
    _install(GOOD)
    _, spans = await _traced(_call(world, tier=tier))
    [span] = _ai_calls(spans)
    assert (span.attributes or {})["ai.tier"] == tier
    assert (span.attributes or {})["ai.model"] == MODELS[tier][0]


async def test_ac20_each_call_gets_its_own_span(world: World) -> None:
    _install(GOOD)
    with tracer("test").start_as_current_span("parent"):
        trace_id = current_trace_id()
        assert trace_id is not None
        await call(_call(world))
        await call(_call(world))
    assert len(_ai_calls(tracing_support.spans_of(trace_id))) == 2


# --- attempts as events --------------------------------------------------------------------------


async def test_ac20_a_successful_call_has_one_ok_attempt_event(world: World) -> None:
    _install(GOOD)
    _, spans = await _traced(_call(world))
    [span] = _ai_calls(spans)
    [attempt] = _attempts(span)
    assert attempt["outcome"] == "ok"
    assert isinstance(attempt["input_tokens"], int)
    assert isinstance(attempt["output_tokens"], int)
    assert attempt["input_tokens"] > 0
    assert attempt["output_tokens"] > 0
    assert isinstance(attempt["cost_usd"], str)
    assert Decimal(str(attempt["cost_usd"])) > 0
    assert set(attempt) == {"outcome", "input_tokens", "output_tokens", "cost_usd"}


async def test_ac20_a_repair_has_one_attempt_event_per_attempt(world: World) -> None:
    script = _install(BAD, GOOD)
    _, spans = await _traced(_call(world))
    [span] = _ai_calls(spans)
    attempts = _attempts(span)
    assert len(script.requests) == 2
    assert len(attempts) == 2
    assert attempts[0]["outcome"] == "invalid"
    assert attempts[1]["outcome"] in ("ok", "repaired")
    assert (span.attributes or {})["ai.attempts"] == 2
    assert (span.attributes or {})["ai.status"] == "repaired"
    total = sum(Decimal(str(a["cost_usd"])) for a in attempts)
    assert Decimal(str((span.attributes or {})["ai.cost_usd"])) == total


async def test_ac20_a_refused_budget_is_an_attempt_event_with_nothing_spent(
    world: World,
) -> None:
    script = _install(GOOD)
    _, spans = await _traced(_call(world, budget=Decimal("0.000001")))
    [span] = _ai_calls(spans)
    [attempt] = _attempts(span)
    assert script.requests == []
    assert attempt["outcome"] == "budget_refused"
    assert attempt["input_tokens"] == 0
    assert attempt["output_tokens"] == 0
    assert Decimal(str(attempt["cost_usd"])) == 0


async def test_ac20_a_provider_error_is_an_attempt_event_with_nothing_spent(
    world: World,
) -> None:
    configure_provider(FakeModel())  # no responder for the prompt: a ProviderError
    _, spans = await _traced(_call(world))
    [span] = _ai_calls(spans)
    [attempt] = _attempts(span)
    assert attempt["outcome"] == "provider_error"
    assert attempt["input_tokens"] == 0
    assert attempt["output_tokens"] == 0
    assert isinstance(attempt["cost_usd"], str)
    assert Decimal(str(attempt["cost_usd"])) >= 0  # the input may be billed (see the gateway)


async def test_ac20_a_repair_refused_for_budget_records_both_attempts(world: World) -> None:
    _install(BAD, GOOD)
    first_estimate = estimate_tokens(prompt(REF).text + _call(world).context.render())
    assert first_estimate > 0
    c = _call(world)
    cheap = _estimate(c)
    _, spans = await _traced(_call(world, budget=cheap))
    [span] = _ai_calls(spans)
    outcomes = [a["outcome"] for a in _attempts(span)]
    assert outcomes == ["invalid", "budget_refused"]
    assert (span.attributes or {})["ai.status"] == "escalated"


def _estimate(c: GatewayCall[Verdict]) -> Decimal:
    tokens = estimate_tokens(prompt(c.prompt).text + c.context.render())
    return cost(c.tier, tokens, c.max_output_tokens)


# --- no text -------------------------------------------------------------------------------------


@pytest.mark.parametrize("replies", [(GOOD,), (BAD, GOOD)])
async def test_ac20_no_span_attribute_event_or_name_holds_the_prompt_context_or_output(
    world: World, replies: tuple[str, ...]
) -> None:
    _install(*replies)
    c = _call(world)
    _, spans = await _traced(c)
    text = tracing_support.everything(spans)
    assert CONTEXT_MARKER not in text
    assert "ECHOED-BACK-MARKER-6642" not in text
    for hidden in (prompt(REF).text, c.context.render(), GOOD, BAD):
        assert hidden not in text
    for line in prompt(REF).text.splitlines():
        if len(line.strip()) > 20:
            assert line.strip() not in text


async def test_ac20_a_refused_call_ends_in_error_status_named_by_class_with_no_exception_event(
    world: World,
) -> None:
    _install(GOOD)
    _, spans = await _traced(_call(world, budget=Decimal("0.000001")))
    [span] = _ai_calls(spans)
    assert span.status.status_code is StatusCode.ERROR
    assert span.status.description == "BudgetExceeded"
    assert [e for e in span.events if e.name == "exception"] == []


async def test_ac20_a_provider_failure_ends_in_error_status_named_by_class(
    world: World,
) -> None:
    configure_provider(FakeModel())
    _, spans = await _traced(_call(world))
    [span] = _ai_calls(spans)
    assert span.status.status_code is StatusCode.ERROR
    assert span.status.description == "ProviderError"
    assert [e for e in span.events if e.name == "exception"] == []


async def test_ac20_a_successful_call_has_no_error_status(world: World) -> None:
    _install(GOOD)
    _, spans = await _traced(_call(world))
    [span] = _ai_calls(spans)
    assert span.status.status_code is not StatusCode.ERROR


async def test_ac20_a_refused_call_holds_no_text_either(world: World) -> None:
    _install(GOOD)
    c = _call(world, budget=Decimal("0.000001"))
    _, spans = await _traced(c)
    assert CONTEXT_MARKER not in tracing_support.everything(spans)
    assert c.context.render() not in tracing_support.everything(spans)
