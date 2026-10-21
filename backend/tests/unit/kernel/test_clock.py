"""F-04-T02 (ADR-143): business time, frozen blocks, the tenant provider slot, system time that a
demo clock never moves, and the production refusal."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from abacus.kernel import clock
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext

TENANT = TenantContext(uuid.uuid4(), "system", "test")


@pytest.fixture(autouse=True)
def _clean(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(clock, "_tenant_clock", [])
    monkeypatch.delenv("ABACUS_DEMO_CLOCK", raising=False)
    settings.cache_clear()


async def test_t02_real_time_by_default() -> None:
    assert abs(await clock.now() - clock.system_now()) < timedelta(seconds=2)


async def test_t02_a_frozen_block_wins_and_is_scoped() -> None:
    at = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)
    with clock.frozen(at):
        assert await clock.now(TENANT) == at
        assert await clock.today(TENANT) == at.date()
    assert await clock.now() != at


async def test_t02_the_process_demo_clock_runs_from_its_anchor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ABACUS_DEMO_CLOCK", "demo")
    settings.cache_clear()
    business = await clock.now()
    assert clock.DEMO_INSTANT <= business < clock.DEMO_INSTANT + timedelta(days=2)
    assert clock.system_now().year >= 2026 and abs(clock.system_now() - business) > timedelta(0)


async def test_t02_the_tenant_provider_answers_for_its_firm_and_falls_back() -> None:
    demo = datetime(2026, 9, 14, 14, 41, tzinfo=UTC)

    async def provider(tenant: TenantContext) -> datetime | None:
        return demo if tenant == TENANT else None

    clock.register_tenant_clock(provider)
    assert await clock.now(TENANT) == demo
    other = TenantContext(uuid.uuid4(), "system", "test")
    assert abs(await clock.now(other) - clock.system_now()) < timedelta(seconds=2)
    with pytest.raises(ValueError, match="already"):
        clock.register_tenant_clock(provider)


def test_t02_production_refuses_a_demo_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    production = SimpleNamespace(environment="production", demo_clock="demo")
    monkeypatch.setattr(clock, "settings", lambda: production)
    with pytest.raises(clock.ClockMisconfigured):
        clock.check_startup()


def test_t02_a_naive_frozen_instant_is_refused() -> None:
    with pytest.raises(ValueError, match="time zone"), clock.frozen(datetime(2026, 9, 14)):
        pass
