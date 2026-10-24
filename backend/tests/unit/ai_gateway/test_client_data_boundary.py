"""SPEC-036 AC-2 (TASK-075): a firm that isn't synthetic reaches a real model only when every
condition holds; each failing condition refuses on its own, with its reason, audited."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import cast

import pytest

from abacus.ai_gateway import boundary
from abacus.ai_gateway.boundary import Basis, DataBoundaryRefused, enforce_boundary
from abacus.kernel import _provider_terms, provider_terms
from abacus.kernel.config import Route
from abacus.kernel.db import TenantContext
from abacus.kernel.provider_terms import TermsEntry

AGENT = "evidence.screener"
PROMPT = "evidence.screen@v0"


@dataclass
class _World:
    synthetic: bool = False
    opted_in: bool = True
    cleared: bool = True
    excluded: bool = False
    stage: str | None = "live"
    boundary: str = "client_data"
    terms: bool = True
    tax_return: bool = False  # P-06-T20 security review (DEC-324)
    audited: list[tuple[str, object]] = field(default_factory=list[tuple[str, object]])


class _Tx:
    def __init__(self, world: _World) -> None:
        self.world = world

    def record(self, action: str, **kwargs: object) -> None:
        self.world.audited.append((action, kwargs.get("after")))


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch) -> _World:
    made = _World()

    @asynccontextmanager
    async def fake_uow(tenant: object) -> AsyncGenerator[_Tx]:
        yield _Tx(made)

    async def synthetic(tenant: TenantContext) -> bool:
        return made.synthetic

    async def opted_in(tenant: TenantContext) -> bool:
        return made.opted_in

    async def excluded(tenant: TenantContext, engagement: uuid.UUID) -> bool:
        return made.excluded

    async def stage(tenant: TenantContext, agent: str) -> str | None:
        return made.stage

    async def tax_return(tenant: TenantContext, engagement: uuid.UUID) -> bool:
        return made.tax_return

    class _Settings:
        @property
        def model_data_boundary(self) -> str:
            return made.boundary

    today = date.today()
    entry = TermsEntry("bedrock", "AWS", "us-east-1", today - timedelta(1), today + timedelta(9))
    monkeypatch.setattr(boundary, "uow", fake_uow)
    monkeypatch.setattr(boundary, "settings", lambda: _Settings())
    monkeypatch.setattr(boundary, "_check", synthetic)
    monkeypatch.setattr(boundary, "_opted_in", opted_in)
    monkeypatch.setattr(boundary, "_excluded", excluded)
    monkeypatch.setattr(boundary, "_stage", stage)
    monkeypatch.setattr(boundary, "_tax_return", tax_return)

    def cleared(agent: str) -> bool:
        return made.cleared

    def covering(route: str, on: date) -> TermsEntry | None:
        return entry if made.terms else None

    monkeypatch.setattr(boundary, "_cleared", cleared)
    monkeypatch.setattr(provider_terms, "covering", covering)
    monkeypatch.setattr(_provider_terms, "VERSION", "a" * 64)
    boundary.clear_cache()
    return made


def _tenant() -> TenantContext:
    return TenantContext(uuid.uuid4(), "system", "test")


async def _call(route: str = "bedrock", engagement: uuid.UUID | None = None) -> Basis | None:
    return await enforce_boundary(
        _tenant(),
        cast(Route, route),
        PROMPT,
        agent_id=AGENT,
        engagement_id=engagement or uuid.uuid4(),
    )


async def test_ac2_every_condition_met_allows_client_data(world: _World) -> None:
    assert await _call() == Basis("client_data", "a" * 64)
    assert world.audited == []


async def test_ac2_a_synthetic_firm_needs_none_of_them(world: _World) -> None:
    world.synthetic, world.opted_in, world.cleared = True, False, False
    assert await _call("direct") == Basis("synthetic")


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"boundary": "synthetic_only"}, "route"),
        ({"terms": False}, "terms"),
        ({"opted_in": False}, "firm"),
        ({"cleared": False}, "agent"),
        ({"excluded": True}, "engagement"),
        ({"stage": None}, "stage"),
        ({"stage": "off"}, "stage"),
        ({"tax_return": True}, "tax_return_information"),
    ],
)
async def test_ac2_each_condition_refuses_on_its_own(
    world: _World, change: dict[str, object], reason: str
) -> None:
    for key, value in change.items():
        setattr(world, key, value)
    with pytest.raises(DataBoundaryRefused) as raised:
        await _call()
    assert raised.value.reason == reason
    [(action, after)] = world.audited
    assert action == "ai.boundary_refused"
    assert after is not None and boundary.REASONS.index(raised.value.reason) >= 0


async def test_ac2_the_direct_route_never_carries_client_data(world: _World) -> None:
    with pytest.raises(DataBoundaryRefused) as raised:
        await _call("direct")
    assert raised.value.reason == "route"


async def test_ac2_shadow_counts_as_allowed(world: _World) -> None:
    world.stage = "shadow"
    assert (await _call()) is not None


async def test_ac2_unregistered_facts_refuse(
    world: _World, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(boundary, "_opted_in", None)
    with pytest.raises(DataBoundaryRefused) as raised:
        await _call()
    assert raised.value.reason == "firm"


async def test_ac2_a_call_without_an_engagement_skips_exclusion(world: _World) -> None:
    world.excluded = True
    found = await enforce_boundary(_tenant(), "bedrock", PROMPT, agent_id=AGENT)
    assert found is not None and found.basis == "client_data"


async def test_ac2_embeddings_have_no_agent_and_are_refused(world: _World) -> None:
    with pytest.raises(DataBoundaryRefused) as raised:
        await enforce_boundary(_tenant(), "bedrock", "embed")
    assert raised.value.reason == "agent"


async def test_q5_clearing_a_firm_forgets_its_facts(world: _World) -> None:
    tenant = _tenant()
    engagement = uuid.uuid4()
    await enforce_boundary(tenant, "bedrock", PROMPT, agent_id=AGENT, engagement_id=engagement)
    world.opted_in = False
    await enforce_boundary(tenant, "bedrock", PROMPT, agent_id=AGENT, engagement_id=engagement)
    boundary.clear_cache(tenant.tenant_id)
    with pytest.raises(DataBoundaryRefused):
        await enforce_boundary(tenant, "bedrock", PROMPT, agent_id=AGENT, engagement_id=engagement)


async def test_ac2_a_real_firm_never_fails_over_to_direct(world: _World) -> None:
    """ADR-113: its calls try client-data routes only, so a Bedrock outage queues the call."""
    from abacus.ai_gateway import barred_routes

    assert await barred_routes(_tenant()) == frozenset({"direct"})
    world.synthetic = True
    assert await barred_routes(_tenant()) == frozenset()


async def test_ac6_an_excluded_engagement_refuses_every_route_and_firm(world: _World) -> None:
    """The partner's switch holds for synthetic firms and the fake route too."""
    world.excluded, world.synthetic = True, True
    for route in ("fake", "direct", "bedrock"):
        boundary.clear_cache()
        with pytest.raises(DataBoundaryRefused) as raised:
            await _call(route)
        assert raised.value.reason == "engagement"


async def test_dec324_tax_return_information_refuses_a_real_firm_and_unregistered_refuses(
    world: _World, monkeypatch: pytest.MonkeyPatch
) -> None:
    world.tax_return = True
    with pytest.raises(DataBoundaryRefused) as raised:
        await _call()
    assert raised.value.reason == "tax_return_information"
    world.tax_return = False
    monkeypatch.setattr(boundary, "_tax_return", None)
    with pytest.raises(DataBoundaryRefused) as unregistered:
        await _call()
    assert unregistered.value.reason == "tax_return_information"
    assert await enforce_boundary(_tenant(), "bedrock", PROMPT, agent_id=AGENT) is not None


async def test_dec324_a_synthetic_firms_tax_return_work_passes(world: _World) -> None:
    world.synthetic, world.tax_return = True, True
    assert await _call() == Basis("synthetic")
