"""Q-01-T19 against Postgres (ADR-157, migration 0086): "The app role reads controls only through
the definer, cannot set synthetic or region, and schema_check passes up, down and up" (the
integration fixtures migrate up, down and up). Operators set controls and provision firms as
`abacus_ops`, which holds no table privileges. The definers are called as the superuser here;
who may call them is checked through the catalogue."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
GLOBAL = ("platform_controls", "platform_control_changes", "firm_provisioning_requests")


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


async def _may_execute(seed: Seeder, role: str, function: str) -> bool:
    return bool(
        await seed.value("SELECT has_function_privilege($1, $2, 'EXECUTE')", role, function)
    )


STATE = "platform_control_state()"
SET = "set_platform_control(text, text, uuid, text, boolean, text, text, text)"
PROVISION = "provision_firm(text, boolean, text, text, text, text)"


@pytest.mark.parametrize("table", GLOBAL)
async def test_the_app_and_operators_have_no_privilege_on_the_global_tables(
    seed: Seeder, table: str
) -> None:
    for role in ("abacus_app", "abacus_ops"):
        for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE"):
            granted = await seed.value(
                "SELECT has_table_privilege($1, $2, $3)", role, table, privilege
            )
            assert granted is False, (role, table, privilege)


async def test_the_app_reads_controls_only_through_the_definer(seed: Seeder) -> None:
    assert await _may_execute(seed, "abacus_app", STATE)
    assert not await _may_execute(seed, "abacus_app", SET)
    assert not await _may_execute(seed, "abacus_app", PROVISION)
    assert await _may_execute(seed, "abacus_ops", SET)
    assert await _may_execute(seed, "abacus_ops", PROVISION)
    assert not await _may_execute(seed, "abacus_ops", STATE)


@pytest.mark.parametrize("column", ["synthetic", "region"])
async def test_the_app_cannot_set_synthetic_or_region(seed: Seeder, column: str) -> None:
    for privilege in ("INSERT", "UPDATE"):
        granted = await seed.value(
            "SELECT has_column_privilege('abacus_app', 'firms', $1, $2)", column, privilege
        )
        assert granted is False, (column, privilege)
    key_columns = await seed.value(
        "SELECT has_column_privilege('abacus_app', 'firms', 'kms_key_status', 'UPDATE')"
    )
    assert key_columns is True


async def test_operators_provision_a_firm_once_and_only_in_the_us(seed: Seeder) -> None:
    key = f"probe-{uuid.uuid4().hex}"
    call = "SELECT provision_firm($1, true, $2, 'America/Chicago', $3, 'probe-op')"
    first = await seed.value(call, "Canary & Co", "us", key)
    again = await seed.value(call, "Canary & Co", "us", key)
    assert first == again
    row = await seed.rows("SELECT name, synthetic, region FROM firms WHERE tenant_id = $1", first)
    assert (row[0]["name"], row[0]["synthetic"], row[0]["region"]) == ("Canary & Co", True, "us")
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.value(call, "Elsewhere", "eu", f"probe-{uuid.uuid4().hex}")


async def test_a_firm_control_is_versioned_logged_and_audited_in_that_firm(seed: Seeder) -> None:
    key = f"probe-{uuid.uuid4().hex}"
    tenant = await seed.value(
        "SELECT provision_firm('Probe', true, 'us', 'America/Chicago', $1, 'op')", key
    )
    set_control = (
        "SELECT set_platform_control('email_pause', 'firm', $1, NULL, $2, 'probe', 'ana', NULL)"
    )
    assert await seed.value(set_control, tenant, True) == 1
    assert await seed.value(set_control, tenant, False) == 2
    changes = await seed.value(
        "SELECT count(*) FROM platform_control_changes WHERE tenant_id = $1", tenant
    )
    assert changes == 2
    audit = await seed.rows(
        "SELECT actor_kind, actor_id, action FROM audit_events WHERE tenant_id = $1", tenant
    )
    assert {(r["actor_kind"], r["actor_id"], r["action"]) for r in audit} == {
        ("system", "operator:ana", "platform_control.changed")
    }
    active = await seed.rows("SELECT * FROM platform_control_state()")
    assert not [r for r in active if r["tenant_id"] == tenant]  # switched off again
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("DELETE FROM platform_control_changes WHERE tenant_id = $1", tenant)
