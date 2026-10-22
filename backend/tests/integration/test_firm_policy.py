"""F-03-T24 against Postgres: firm policy overrides hold only `deny` and are never edited, firm
setting values hold registered keys only, and `firm_policy` reads one firm's rows (migration
0081; DEC-127)."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from abacus.kernel.db import TenantContext, configure_engine
from abacus.modules.identity.repository import firm_policy

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio

_OVERRIDE = (
    "INSERT INTO firm_policy_overrides (tenant_id, action, role, decision, reason, set_by) "
    "VALUES ($1, 'request_item.create', $2, 'deny', 'probe', $3)"
)
_ALLOW_OVERRIDE = (
    "INSERT INTO firm_policy_overrides (tenant_id, action, role, decision, reason, set_by) "
    "VALUES ($1, 'request_item.create', $2, 'allow', 'probe', $3)"
)


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    configure_engine(migrated_db.app_url)  # a fresh pool on this test's event loop
    return Seeder(migrated_db.superuser_dsn)


async def _firm(seed: Seeder) -> uuid.UUID:
    tenant = uuid.uuid4()
    await seed.run("INSERT INTO firms (tenant_id, name) VALUES ($1, 'Probe')", tenant)
    return tenant


async def test_an_override_is_deny_or_nothing(seed: Seeder) -> None:
    tenant = await _firm(seed)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            _ALLOW_OVERRIDE,
            tenant,
            "staff",
            uuid.uuid4(),
        )


async def test_only_registered_settings_have_values(seed: Seeder) -> None:
    tenant = await _firm(seed)
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.run(
            "INSERT INTO firm_setting_values (tenant_id, key, value, set_by) "
            "VALUES ($1, 'anything_goes', true, $2)",
            tenant,
            uuid.uuid4(),
        )


async def test_firm_policy_reads_this_firm_only(seed: Seeder) -> None:
    mine, theirs = await _firm(seed), await _firm(seed)
    for tenant, role in ((mine, "manager"), (theirs, "senior")):
        await seed.run(
            _OVERRIDE,
            tenant,
            role,
            uuid.uuid4(),
        )
    await seed.run(
        "INSERT INTO firm_setting_values (tenant_id, key, value, set_by) VALUES "
        "($1, 'seniors_can_accept', true, $3), ($1, 'seniors_can_create', false, $3), "
        "($2, 'seniors_can_publish', true, $3)",
        mine,
        theirs,
        uuid.uuid4(),
    )
    policy = await firm_policy(TenantContext(mine, "human", "probe"))
    assert policy.overrides == {("request_item.create", "manager"): "deny"}
    assert policy.settings_on == frozenset({"seniors_can_accept"})
