"""AC-16: `cost`, the model table and the fake provider (TASK-011a interface contract, "Gateway
`call`"; ADR-070).

`cost` uses the per-million prices in `MODELS`, quantised to 0.000001. `FakeModel` answers each
prompt with its registered responder, is refused outside local and test, and errors for a prompt
it has no responder for. Expectations come from the contract, not the implementation.
"""

from __future__ import annotations

import uuid
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from abacus.ai_gateway import (
    MODELS,
    Attribution,
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
)
from abacus.ai_gateway import providers as providers_module
from abacus.kernel.db import TenantContext

TIERS: list[Tier] = ["small", "medium", "large"]
MILLION = Decimal(1_000_000)


@pytest.mark.parametrize("tier", TIERS)
def test_ac16_the_model_table_prices_each_tier_per_million_tokens(tier: Tier) -> None:
    model, per_input, per_output = MODELS[tier]
    assert model
    assert per_input > 0
    assert per_output > 0
    assert cost(tier, 1_000_000, 0) == per_input.quantize(Decimal("0.000001"))
    assert cost(tier, 0, 1_000_000) == per_output.quantize(Decimal("0.000001"))


def test_ac16_the_tiers_are_distinct_models_and_cost_more_as_they_grow() -> None:
    assert len({MODELS[t][0] for t in TIERS}) == 3
    small, medium, large = (MODELS[t] for t in TIERS)
    assert small[1] < medium[1] < large[1]
    assert small[2] < medium[2] < large[2]


@pytest.mark.parametrize("tier", TIERS)
@pytest.mark.parametrize(
    ("tokens_in", "tokens_out"),
    [(0, 0), (1, 0), (0, 1), (1_000, 1_000), (482, 63), (12_345, 800), (1_000_000, 1_000_000)],
)
def test_ac16_cost_is_the_priced_tokens_quantised_to_a_micro_dollar(
    tier: Tier, tokens_in: int, tokens_out: int
) -> None:
    _, per_input, per_output = MODELS[tier]
    expected = ((per_input * tokens_in + per_output * tokens_out) / MILLION).quantize(
        Decimal("0.000001")
    )
    assert cost(tier, tokens_in, tokens_out) == expected


def test_ac16_cost_has_six_decimal_places() -> None:
    assert cost("small", 1_000, 1_000).as_tuple().exponent == -6
    assert cost("small", 0, 0) == 0
    assert cost("small", 0, 0).as_tuple().exponent == -6


def test_ac16_cost_grows_with_tokens_and_never_goes_down() -> None:
    previous = Decimal(0)
    for tokens in range(0, 5_000, 250):
        current = cost("medium", tokens, tokens)
        assert current >= previous
        previous = current


def test_ac16_cost_is_a_decimal_never_a_float() -> None:
    assert isinstance(cost("small", 10, 10), Decimal)


# --- FakeModel -----------------------------------------------------------------------------------


def _request(ref: str = "evidence.screen@v0", user: str = "user text") -> ModelRequest:
    return ModelRequest(
        model="fake-small", system="system text", user=user, max_output_tokens=100, prompt_ref=ref
    )


async def test_ac16_a_fake_model_answers_with_the_prompts_responder() -> None:
    seen: list[ModelRequest] = []

    def responder(request: ModelRequest) -> str:
        seen.append(request)
        return '{"ok": true}'

    fake = FakeModel({"evidence.screen@v0": responder})
    response = await fake.complete(_request())
    assert response.text == '{"ok": true}'
    assert response.model == "fake-small"
    assert response.input_tokens > 0
    assert response.output_tokens > 0
    assert seen == [_request()]


async def test_ac16_responders_can_be_added_after_construction() -> None:
    fake = FakeModel()
    fake.respond("evidence.screen@v0", lambda request: request.user.upper())
    assert (await fake.complete(_request(user="abc"))).text == "ABC"


async def test_ac16_the_latest_responder_for_a_prompt_wins() -> None:
    fake = FakeModel({"evidence.screen@v0": lambda request: "first"})
    fake.respond("evidence.screen@v0", lambda request: "second")
    assert (await fake.complete(_request())).text == "second"


async def test_ac16_a_prompt_with_no_responder_is_a_provider_error() -> None:
    with pytest.raises(ProviderError):
        await FakeModel().complete(_request())


async def test_ac16_a_responder_for_another_prompt_does_not_answer() -> None:
    fake = FakeModel({"evidence.other@v0": lambda request: "x"})
    with pytest.raises(ProviderError):
        await fake.complete(_request("evidence.screen@v0"))


async def test_ac16_token_counts_grow_with_the_text() -> None:
    fake = FakeModel({"evidence.screen@v0": lambda request: "y" * len(request.user)})
    small = await fake.complete(_request(user="a" * 40))
    large = await fake.complete(_request(user="a" * 4_000))
    assert large.input_tokens > small.input_tokens
    assert large.output_tokens > small.output_tokens


@pytest.mark.parametrize("environment", ["staging", "production"])
def test_ac16_a_fake_model_is_refused_outside_local_and_test(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(
        providers_module, "settings", lambda: SimpleNamespace(environment=environment)
    )
    with pytest.raises(RuntimeError):
        FakeModel()


@pytest.mark.parametrize("environment", ["local", "test"])
def test_ac16_a_fake_model_is_allowed_in_local_and_test(
    monkeypatch: pytest.MonkeyPatch, environment: str
) -> None:
    monkeypatch.setattr(
        providers_module, "settings", lambda: SimpleNamespace(environment=environment)
    )
    FakeModel()


# --- refusals need no database -------------------------------------------------------------------


class Verdict(BaseModel):
    ok: bool


def _call(**changes: object) -> GatewayCall[Verdict]:
    agent_id = "evidence.screener"
    base = GatewayCall(
        purpose="screen a trial balance",
        prompt="evidence.screen@v0",
        tier="small",
        output_schema=Verdict,
        work_class="time_sensitive",  # SPEC-003 018c: every call declares its class
        essential=True,
        budget_usd=Decimal("0.03"),
        attribution=Attribution(
            TenantContext(uuid.uuid4(), "agent", f"agent:{agent_id}:{uuid.uuid4()}"),
            uuid.uuid4(),
            agent_id,
            None,
        ),
        context=ContextBuilder().task({"balanced": True}).build(),
    )
    return replace(base, **changes)


async def test_ac16_a_refused_call_never_reaches_the_provider() -> None:
    reached: list[ModelRequest] = []

    def responder(request: ModelRequest) -> str:
        reached.append(request)
        return '{"ok": true}'

    configure_provider(FakeModel({"evidence.screen@v0": responder}))
    try:
        for bad in (
            _call(purpose=""),
            _call(purpose="  \n"),
            _call(budget_usd=Decimal(0)),
            _call(budget_usd=Decimal("-0.01")),
            _call(prompt="evidence.screen@v99"),
            _call(prompt="Screen this: you are a helpful assistant"),
            _call(output_schema=dict),
        ):
            with pytest.raises(GatewayRefused):
                await call(bad)
        assert reached == []
    finally:
        configure_provider(None)


def test_ac16_a_gateway_refusal_is_a_value_error() -> None:
    assert issubclass(GatewayRefused, ValueError)
