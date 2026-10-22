"""F-04-T06 and T07 against Postgres (ADR-143): `abacus_now()` moves only a synthetic firm
(F-04.3), business defaults follow it, `audit_events.effective_at` is written by its default
alone (F-04.5), and the demo clock is a synthetic firm's, set through the service and audited."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, configure_engine, tenant_session
from abacus.modules.identity import firm_settings
from abacus.modules.identity.api import AuthContext, DemoClockRefused, clock_view, set_demo_clock

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
ANCHOR = datetime(2026, 9, 14, 14, 24, tzinfo=UTC)  # Mon 14 Sep 2026, 9:24 AM CDT


class _Firm:
    def __init__(self, seed: Seeder, *, synthetic: bool) -> None:
        self.seed = seed
        self.synthetic = synthetic
        self.tenant = uuid.uuid4()
        self.admin = uuid.uuid4()

    async def make(self) -> _Firm:
        await self.seed.run(
            "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Probe', $2)",
            self.tenant,
            self.synthetic,
        )
        self.admin = uuid.UUID(
            str(
                await self.seed.value(
                    "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                    "VALUES ('https://probe.test', $1, $2, 'Probe') RETURNING id",
                    uuid.uuid4().hex,
                    f"{uuid.uuid4().hex}@example.test",
                )
            )
        )
        await self.seed.run(
            "INSERT INTO memberships (tenant_id, user_id, firm_role, status) "
            "VALUES ($1, $2, 'firm_admin', 'active')",
            self.tenant,
            self.admin,
        )
        return self

    @property
    def tenant_ctx(self) -> TenantContext:
        return TenantContext(self.tenant, "human", str(self.admin))

    @property
    def person(self) -> AuthContext:
        return AuthContext(
            self.tenant_ctx, self.admin, uuid.uuid4(), "firm_admin", datetime.now(UTC)
        )

    async def abacus_now(self, business: datetime | None) -> datetime:
        """`abacus_now()` in a tenant transaction; with `business`, the clock stands there, so
        `_begin_tenant` sets `app.now` to it."""
        if business is None:
            return await self._select_now()
        with clock.frozen(business):
            return await self._select_now()

    async def _select_now(self) -> datetime:
        async with tenant_session(self.tenant_ctx) as session:
            return (await session.execute(text("SELECT abacus_now()"))).scalar_one()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    firm_settings.forget_demo_clocks()
    return Seeder(migrated_db.superuser_dsn)


async def test_f04_3_a_real_firm_ignores_app_now(seed: Seeder) -> None:
    real = await _Firm(seed, synthetic=False).make()
    at = await real.abacus_now(ANCHOR)
    assert abs(at - datetime.now(UTC)) < timedelta(minutes=1)


async def test_a_synthetic_firm_follows_app_now(seed: Seeder) -> None:
    demo = await _Firm(seed, synthetic=True).make()
    assert await demo.abacus_now(ANCHOR) == ANCHOR
    unset = await demo.abacus_now(None)
    assert abs(unset - datetime.now(UTC)) < timedelta(minutes=1)


async def test_f04_5_effective_at_is_written_by_its_default_alone(seed: Seeder) -> None:
    for privilege in ("INSERT", "UPDATE"):
        granted = await seed.value(
            "SELECT has_column_privilege('abacus_app', 'audit_events', 'effective_at', $1)",
            privilege,
        )
        assert granted is False, privilege
    default = await seed.value(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_name = 'audit_events' AND column_name = 'effective_at'"
    )
    assert default == "abacus_now()"
    occurred = await seed.value(
        "SELECT column_default FROM information_schema.columns "
        "WHERE table_name = 'audit_events' AND column_name = 'occurred_at'"
    )
    assert occurred == "clock_timestamp()"  # system truth, unchanged


async def test_a_demo_clock_row_is_refused_for_a_real_firm(seed: Seeder) -> None:
    import asyncpg

    real = await _Firm(seed, synthetic=False).make()
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO firm_demo_clocks (tenant_id, mode, anchor_at, set_by) "
            "VALUES ($1, 'frozen', $2, 'probe')",
            real.tenant,
            ANCHOR,
        )


async def test_t07_the_service_sets_a_synthetic_firms_clock_and_inserts_follow(
    seed: Seeder,
) -> None:
    demo = await _Firm(seed, synthetic=True).make()
    view = await set_demo_clock(demo.person, "frozen", ANCHOR)
    assert (view.server_now, view.clock_mode) == (ANCHOR, "frozen")
    assert (await clock_view(demo.tenant_ctx)).server_now == ANCHOR
    stamped = await demo.abacus_now(None)
    assert stamped == ANCHOR  # `_begin_tenant` set `app.now` from the tenant clock
    actions = await seed.rows(
        "SELECT action, effective_at, occurred_at FROM audit_events WHERE tenant_id = $1",
        demo.tenant,
    )
    assert [r["action"] for r in actions] == ["firm.demo_clock_changed"]

    offset = await set_demo_clock(demo.person, "offset", ANCHOR)
    assert offset.clock_mode == "offset"
    assert ANCHOR <= offset.server_now < ANCHOR + timedelta(minutes=1)
    reset = await set_demo_clock(demo.person, None)
    assert reset.clock_mode == "real"
    assert abs(reset.server_now - clock.system_now()) < timedelta(minutes=1)


async def test_t07_a_real_firm_cannot_have_a_demo_clock(seed: Seeder) -> None:
    real = await _Firm(seed, synthetic=False).make()
    with pytest.raises(DemoClockRefused):
        await set_demo_clock(real.person, "frozen", ANCHOR)
    assert (await clock_view(real.tenant_ctx)).clock_mode == "real"


async def test_t07_production_refuses_the_demo_clock(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    demo = await _Firm(seed, synthetic=True).make()
    real_settings = firm_settings.settings()

    class _Production:
        environment = "production"

        def __getattr__(self, name: str) -> object:
            return getattr(real_settings, name)

    monkeypatch.setattr(firm_settings, "settings", lambda: _Production())
    with pytest.raises(DemoClockRefused):
        await set_demo_clock(demo.person, "frozen", ANCHOR)
