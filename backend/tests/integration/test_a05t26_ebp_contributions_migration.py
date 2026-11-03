"""A-05-T26 (TASK-3207; DEC-2207): migration 0658 `ebp_contributions`.

Row acceptance: "A second late_remittance row for the same payroll is refused and an agent
cannot write a correction event." Down to 0657 removes the three tables; up restores them with
forced RLS; the events are insert-only for every role.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from typing import cast

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

TABLES = ("ebp_payrolls", "ebp_late_remittances", "ebp_late_remittance_events")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_ac_0658_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0657", down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        ), table


@pytest.mark.parametrize("table", TABLES)
def test_ac_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


async def _late(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    client = await seed.value("SELECT client_id FROM client_entities WHERE id = $1", entity)
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'", engagement
        )
        or await seed.value(
            "INSERT INTO work_items (tenant_id, engagement_id, client_id, client_entity_id, "
            "kind, name, created_by) VALUES ($1, $2, $3, $4, 'assurance', 'Plan 2025', $5) "
            "RETURNING id",
            tenant,
            engagement,
            client,
            entity,
            person.user_id,
        ),
    )
    payroll = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO ebp_payrolls (tenant_id, engagement_id, work_item_id, pay_date, "
            "deferrals_pretax, deposit_date) VALUES ($1, $2, $3, '2025-12-26', 8400.00, "
            "'2026-01-09') RETURNING id",
            tenant,
            engagement,
            item,
        ),
    )
    late = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO ebp_late_remittances (tenant_id, engagement_id, work_item_id, "
            "payroll_id, principal, due_on, deposited_on, business_days_late) VALUES ($1, $2, "
            "$3, $4, 8400.00, '2026-01-02', '2026-01-09', 5) RETURNING id",
            tenant,
            engagement,
            item,
            payroll,
        ),
    )
    return {
        "tenant": tenant,
        "engagement": engagement,
        "item": item,
        "payroll": payroll,
        "late": late,
        "person": person.user_id,
    }


def test_ac_a_second_late_remittance_for_the_same_payroll_is_refused(
    private_db: sc.Database,
) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _late(seed)
        with pytest.raises(asyncpg.UniqueViolationError):
            await seed.run(
                "INSERT INTO ebp_late_remittances (tenant_id, engagement_id, work_item_id, "
                "payroll_id, principal, due_on, business_days_late) VALUES ($1, $2, $3, $4, "
                "1.00, '2026-01-02', 1)",
                ids["tenant"],
                ids["engagement"],
                ids["item"],
                ids["payroll"],
            )

    asyncio.run(scenario())


def test_ac_an_agent_cannot_write_a_correction_event(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _late(seed)
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO ebp_late_remittance_events (tenant_id, engagement_id, work_item_id, "
                "late_remittance_id, event, actor_kind) VALUES ($1, $2, $3, $4, "
                "'correction_recorded', 'agent')",
                ids["tenant"],
                ids["engagement"],
                ids["item"],
                ids["late"],
            )
        found = await seed.value(
            "INSERT INTO ebp_late_remittance_events (tenant_id, engagement_id, work_item_id, "
            "late_remittance_id, event, actor_kind, actor_user_id) VALUES ($1, $2, $3, $4, "
            "'correction_recorded', 'human', $5) RETURNING id",
            ids["tenant"],
            ids["engagement"],
            ids["item"],
            ids["late"],
            ids["person"],
        )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run(
                "UPDATE ebp_late_remittance_events SET event = 'reverted' WHERE id = $1", found
            )

    asyncio.run(scenario())
