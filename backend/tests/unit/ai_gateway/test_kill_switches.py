"""Q-01-T36 (P-66; Q-01 F8): the AI kill switches in the gateway. With `ai_pause` on for the
platform or the firm, the boundary refuses every route, the fake one too, before anything else
and before any provider call; `model_route_block` makes admission skip the route as an outage
would. The operator command checks its arguments before touching a database."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import BaseModel

import abacus.ai_gateway as gateway
from abacus.ai_gateway import Attribution, ContextBuilder, GatewayCall, boundary
from abacus.ai_gateway.boundary import DataBoundaryRefused, enforce_boundary
from abacus.kernel.db import TenantContext
from abacus_tools.platform_control import ControlChange, Refused


class _Tx:
    def __init__(self, audited: list[str]) -> None:
        self.audited = audited

    def record(self, action: str, **kwargs: object) -> None:
        self.audited.append(action)


@pytest.fixture
def audited(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    found: list[str] = []

    @asynccontextmanager
    async def fake_uow(tenant: object) -> AsyncGenerator[_Tx]:
        yield _Tx(found)

    monkeypatch.setattr(boundary, "uow", fake_uow)
    return found


def _paused_for(tenant: UUID | None, monkeypatch: pytest.MonkeyPatch) -> None:
    async def control_active(
        control: str, tenant_id: UUID | None = None, *, route: str | None = None
    ) -> bool:
        return control == "ai_pause" and (tenant is None or tenant_id == tenant)

    monkeypatch.setattr(boundary, "control_active", control_active)


@pytest.mark.parametrize("route", ["fake", "direct", "bedrock"])
async def test_ai_pause_refuses_every_route_first(
    route: str, audited: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    _paused_for(None, monkeypatch)
    tenant = TenantContext(uuid.uuid4(), "system", "test")
    with pytest.raises(DataBoundaryRefused) as refused:
        await enforce_boundary(tenant, route, "evidence.screen@v0")  # type: ignore[arg-type]
    assert refused.value.reason == "ai_paused"
    assert audited == ["ai.boundary_refused"]


async def test_ai_pause_for_one_firm_leaves_another_alone(
    audited: list[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    paused = uuid.uuid4()
    _paused_for(paused, monkeypatch)
    with pytest.raises(DataBoundaryRefused):
        await enforce_boundary(TenantContext(paused, "system", "test"), "fake", "p")
    assert (
        await enforce_boundary(TenantContext(uuid.uuid4(), "system", "test"), "fake", "p") is None
    )


def test_ai_paused_is_appended_to_the_audited_reasons() -> None:
    assert boundary.REASONS[-1] == "ai_paused"
    assert boundary.REASONS.index("tax_return_information") == 7  # earlier indices keep meaning


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
    )


def _real_only(route: str) -> bool:
    return route != "fake"


def _model(tier: str, route: str) -> str:
    return f"{route}-model"


async def test_a_blocked_route_is_skipped_at_admission(monkeypatch: pytest.MonkeyPatch) -> None:
    asked: list[str] = []

    async def admit(tenant: object, route: str, *args: object) -> tuple[bool, int]:
        asked.append(route)
        return True, 0

    async def eligible(*args: object) -> bool:
        return True

    async def control_active(
        control: str, tenant_id: UUID | None = None, *, route: str | None = None
    ) -> bool:
        return control == "model_route_block" and route == "bedrock"

    monkeypatch.setattr(gateway, "admit", admit)
    monkeypatch.setattr(gateway, "eligible", eligible)
    monkeypatch.setattr(gateway, "control_active", control_active)
    monkeypatch.setattr(gateway, "route_enabled", _real_only)
    monkeypatch.setattr(gateway, "model_id", _model)
    _, route, _ = await gateway._admitted(  # pyright: ignore[reportPrivateUsage] -- the gateway's own internals
        _call(), ("large",), 10, "evidence.screen@v0"
    )
    assert route == "direct" and "bedrock" not in asked


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (ControlChange("ai_pause", "firm", None, None, True, "ana", "x"), "--tenant"),
        (ControlChange("ai_pause", "platform", uuid.uuid4(), None, True, "ana", "x"), "--tenant"),
        (ControlChange("portal_sign_in", "platform", None, None, True, "ana", "x"), "per firm"),
        (ControlChange("model_route_block", "platform", None, None, True, "ana", "x"), "--route"),
        (ControlChange("read_only", "platform", None, "bedrock", True, "ana", "x"), "--route"),
        (ControlChange("read_only", "platform", None, None, True, "a@b.test", "x"), "handle"),
        (ControlChange("read_only", "platform", None, None, True, "ana", " "), "--reason"),
        (ControlChange("nothing", "platform", None, None, True, "ana", "x"), "--control"),
    ],
)
def test_the_operator_command_refuses_a_malformed_change(
    change: ControlChange, message: str
) -> None:
    with pytest.raises(Refused, match=message):
        change.checked()
