"""G-01-T04 against Postgres (G-01 AC1.1 to AC1.9, AC2.1 to AC2.4): ADM-01's sections read and
write live through the typed registry; a stale version answers 409; a partner reads and can't
write; a security admin gets no Plan & seats; a person without a settings role gets 404; the
display name has one home (the portal's branding row); At a glance survives a failing area."""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

import abacus.modules.organisations.api  # registers its At a glance row
import abacus.modules.portal.api  # registers the display name and footer accessors
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.errors import NotFound
from abacus.modules.identity import settings_registry
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.identity.settings_registry import (
    DisplayNameRequired,
    GlanceRow,
    StaleSection,
    UnknownSetting,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

assert abacus.modules.organisations.api and abacus.modules.portal.api


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


async def _person(
    seed: Seeder, tenant: uuid.UUID, *, firm_role: str | None, level: str | None = None
) -> AuthContext:
    user = uuid.UUID(
        str(
            await seed.value(
                "INSERT INTO users (idp_issuer, idp_subject, email, display_name) "
                "VALUES ('https://probe.test', $1, $2, 'Grace Holloway') RETURNING id",
                uuid.uuid4().hex,
                f"{uuid.uuid4().hex}@example.test",
            )
        )
    )
    await seed.run(
        "INSERT INTO memberships (tenant_id, user_id, firm_role, status, level) "
        "VALUES ($1, $2, $3, 'active', $4)",
        tenant,
        user,
        firm_role,
        level,
    )
    return AuthContext(
        tenant=TenantContext(tenant, "human", str(user)),
        user_id=user,
        membership_id=uuid.uuid4(),
        firm_role=firm_role,  # pyright: ignore[reportArgumentType] -- a seeded firm role code
        mfa_at=datetime.now(UTC) - timedelta(minutes=1),
    )


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def test_ac1_2_a_save_writes_each_key_once_and_audits_names_not_values(
    seed: Seeder,
) -> None:
    tenant = await seed.firm()
    grace = await _person(seed, tenant, firm_role="firm_admin")
    profile = await settings_registry.read_section(grace, "profile")
    assert profile.version == 1 and profile.allowed_actions == ["firm.manage_settings"]
    await settings_registry.save_section(
        grace,
        "profile",
        1,
        {
            "legal_name": "Brightwater Hale LLP",
            "time_zone": "America/New_York",
            "display_name": "Brightwater Hale",
        },
    )
    after = dict(
        (k.key, v) for k, v in (await settings_registry.read_section(grace, "profile")).values
    )
    assert after["legal_name"] == "Brightwater Hale LLP"
    assert after["time_zone"] == "America/New_York"
    assert after["display_name"] == "Brightwater Hale"
    # AC1.9: one home for the display name and the time zone.
    assert (
        await seed.value("SELECT display_name FROM portal_branding WHERE tenant_id = $1", tenant)
        == "Brightwater Hale"
    )
    assert await seed.value("SELECT time_zone FROM firms WHERE tenant_id = $1", tenant) == (
        "America/New_York"
    )
    assert (
        await seed.value(
            "SELECT count(*) FROM firm_settings WHERE tenant_id = $1 AND key IN "
            "('display_name', 'time_zone')",
            tenant,
        )
        == 0
    )
    events = await seed.rows(
        "SELECT after_ref::text AS ref FROM audit_events WHERE tenant_id = $1 "
        "AND action = 'firm_setting.updated'",
        tenant,
    )
    assert len(events) == 1
    assert "legal_name" in events[0]["ref"] and "Brightwater" not in events[0]["ref"]


async def test_ac1_3_and_1_4_required_name_unknown_keys_and_stale_versions(seed: Seeder) -> None:
    tenant = await seed.firm()
    grace = await _person(seed, tenant, firm_role="firm_admin")
    with pytest.raises(DisplayNameRequired):
        await settings_registry.save_section(grace, "profile", 1, {"display_name": "   "})
    with pytest.raises(UnknownSetting):
        await settings_registry.save_section(grace, "profile", 1, {"region": "eu"})  # AC1.5
    await settings_registry.save_section(grace, "defaults", 1, {"week_starts_on": "monday"})
    with pytest.raises(StaleSection):
        await settings_registry.save_section(grace, "defaults", 1, {"week_starts_on": "sunday"})


async def test_ac1_6_to_1_8_who_reads_and_who_writes(seed: Seeder) -> None:
    tenant = await seed.firm()
    daniel = await _person(seed, tenant, firm_role=None, level="partner")
    felix = await _person(seed, tenant, firm_role="security_admin")
    kevin = await _person(seed, tenant, firm_role=None, level="staff")

    read = await settings_registry.read_section(daniel, "profile")
    assert read.read_only_reason == "firm_admin_only" and read.allowed_actions == []
    with pytest.raises(Forbidden):
        await settings_registry.save_section(daniel, "profile", 1, {"legal_name": "X"})

    with pytest.raises(NotFound):  # AC1.7: absent, not hidden
        await settings_registry.read_section(felix, "plan")
    felix_view = await settings_registry.overview(felix)
    assert ("plan", False) in felix_view.sections

    with pytest.raises(NotFound):  # AC1.8: nothing to see, not "forbidden"
        await settings_registry.overview(kevin)


async def test_ac2_1_and_2_3_at_a_glance_rows_and_a_failing_area(seed: Seeder) -> None:
    tenant = await seed.firm()
    grace = await _person(seed, tenant, firm_role="firm_admin")

    async def slow(_ctx: AuthContext) -> GlanceRow | None:
        await asyncio.sleep(2)
        return GlanceRow("slow_probe", "ok")

    settings_registry.register_settings_area("slow_probe", 99, slow)
    try:
        view = await settings_registry.overview(grace)
    finally:
        settings_registry._AREAS.pop("slow_probe")  # pyright: ignore[reportPrivateUsage] -- test-only registration
    rows = {r.key: r for r in view.at_a_glance}
    assert rows["people"].facts["used"] >= 1 and rows["people"].href == "/settings/people"
    assert "offices" in rows["offices_teams"].facts
    assert rows["slow_probe"].unavailable and rows["slow_probe"].tone == "none"
