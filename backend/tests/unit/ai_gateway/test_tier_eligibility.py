"""SPEC-005 AC-13 (TASK-020): a cheaper tier is tried only when a passing evaluation run makes it
eligible; the call's own tier never needs one; evaluation mode pins the tier."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from pydantic import BaseModel

import abacus.ai_gateway as gateway
from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, NotAdmitted
from abacus.kernel.db import TenantContext

SCREEN = "evidence.screen@v0"


class Out(BaseModel):
    ok: bool


def _call() -> GatewayCall[BaseModel]:
    return GatewayCall(
        purpose="screen",
        prompt="evidence.screen@v0",
        tier="large",
        output_schema=Out,
        budget_usd=Decimal("1"),
        attribution=Attribution(
            TenantContext(uuid.uuid4(), "agent", "agent:x"),
            uuid.uuid4(),
            "evidence.screener",
            None,
        ),
        context=ContextBuilder().task({"a": 1}).build(),
        work_class="time_sensitive",
        essential=True,
        routes=("bedrock", "direct"),
        cheaper_tiers=("medium",),
    )


@pytest.fixture
def admits(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """The provider bucket admits only medium; record which models were asked."""
    asked: list[str] = []

    async def admit(*args: object) -> tuple[bool, int]:
        model = str(args[2])  # (tenant, route, model, ...): SPEC-010
        asked.append(model)
        return model == gateway.MODELS["medium"][0], 5

    monkeypatch.setattr(gateway, "admit", admit)
    return asked


async def test_ac13_an_ineligible_cheaper_tier_is_skipped(
    monkeypatch: pytest.MonkeyPatch, admits: list[str]
) -> None:
    async def never(*args: object) -> bool:
        return False

    monkeypatch.setattr(gateway, "eligible", never)
    with pytest.raises(NotAdmitted):
        await gateway._admitted(_call(), ("large", "medium"), 10, "evidence.screen@v0")  # pyright: ignore[reportPrivateUsage] -- the gateway's own internals
    assert admits == [gateway.MODELS["large"][0]]  # medium never asked


async def test_ac13_an_eligible_cheaper_tier_is_used(
    monkeypatch: pytest.MonkeyPatch, admits: list[str]
) -> None:
    async def always(*args: object) -> bool:
        return True

    monkeypatch.setattr(gateway, "eligible", always)
    tier, route, model = await gateway._admitted(  # pyright: ignore[reportPrivateUsage] -- the gateway's own internals
        _call(), ("large", "medium"), 10, "evidence.screen@v0"
    )
    assert (tier, route, model) == ("medium", "fake", gateway.MODELS["medium"][0])


async def test_ac13_eligibility_fails_closed_when_the_store_is_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(tenant: object) -> object:
        raise ConnectionError("down")

    monkeypatch.setattr(gateway, "tenant_session", broken)
    tenant = TenantContext(uuid.uuid4(), "agent", "agent:x")
    assert not await gateway.eligible(tenant, "evidence.screener", "fake", "small", "m", SCREEN)


@pytest.mark.parametrize(
    ("agent", "prompt_ref"),
    [("evidence.screener", "other.prompt@v0"), ("other.agent", SCREEN)],
)
async def test_ac13_eligibility_is_keyed_on_the_agents_own_prompt(
    monkeypatch: pytest.MonkeyPatch, agent: str, prompt_ref: str
) -> None:
    def never(tenant: object) -> object:
        raise AssertionError("the store isn't asked for another agent's prompt")

    monkeypatch.setattr(gateway, "tenant_session", never)
    tenant = TenantContext(uuid.uuid4(), "agent", "agent:x")
    assert not await gateway.eligible(tenant, agent, "fake", "small", "m", prompt_ref)


def test_ac13_the_screeners_suite_is_known_to_the_gateway() -> None:
    assert gateway.EVAL_SUITES["evidence.screener"][0] == SCREEN


def test_evaluation_mode_pins_the_tier_for_the_block() -> None:
    assert gateway._evaluation_tier.get() is None  # pyright: ignore[reportPrivateUsage] -- the gateway's own internals
    with gateway.evaluation("small"):
        assert gateway._evaluation_tier.get() == "small"  # pyright: ignore[reportPrivateUsage] -- the gateway's own internals
    assert gateway._evaluation_tier.get() is None  # pyright: ignore[reportPrivateUsage] -- the gateway's own internals
