"""A-05-T41 (TASK-3301; DEC-2301): migration 0667 `ebp_loans_accounts_expenses`.

Row acceptance: "Upgrade and downgrade pass on the seed, and SSNs in the balance and SDBA schedules
are sealed like the census." Also: forced RLS and no DELETE grant on every table; an offset is
reported on line 2e(1) and nowhere else; an expense names a Schedule H 2i line; an expense
exception
carries its issue.
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

TABLES = (
    "ebp_participant_loans",
    "ebp_loan_offsets",
    "ebp_participant_balances",
    "ebp_sdba_holdings",
    "ebp_plan_expenses",
    "ebp_erisa_budget_lines",
    "ebp_compliance_tests",
    "ebp_qualification_facts",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_ac_0667_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0666", down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        assert _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        ), table
        assert not _value(
            private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')"
        ), table


@pytest.mark.parametrize("table", ["ebp_participant_balances", "ebp_sdba_holdings"])
def test_ac_ssns_are_sealed_like_the_census(private_db: sc.Database, table: str) -> None:
    columns = cast(
        str,
        _value(
            private_db,
            "SELECT string_agg(column_name, ',') FROM information_schema.columns "
            "WHERE table_name = $1 AND column_name LIKE 'ssn%'",
            table,
        ),
    ).split(",")
    assert sorted(columns) == ["ssn_fp", "ssn_last4", "ssn_sealed"]
    assert _value(
        private_db,
        "SELECT data_type = 'bytea' FROM information_schema.columns "
        "WHERE table_name = $1 AND column_name = 'ssn_sealed'",
        table,
    )


async def _item(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    item = cast(
        uuid.UUID,
        await seed.value(
            "SELECT id FROM work_items WHERE engagement_id = $1 AND kind = 'assurance'", engagement
        ),
    )
    evidence_item = await seed.value(
        "INSERT INTO evidence_items (tenant_id, engagement_id, title, created_by_kind, "
        "created_by_id) VALUES ($1, $2, 'Keystone loan report.pdf', 'human', 'seed') "
        "RETURNING id",
        tenant,
        engagement,
    )
    version = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO evidence_versions (tenant_id, engagement_id, evidence_item_id, "
            "version_no, fingerprint, storage_key, storage_version_id, size_bytes, media_type, "
            "source, method) VALUES ($1, $2, $3, 1, repeat('d', 64), "
            "'tenants/' || $1::uuid::text || '/sha256/' || repeat('d', 64), 'v1', 10, "
            "'application/pdf', 'client_upload', 'uploaded') RETURNING id",
            tenant,
            engagement,
            evidence_item,
        ),
    )
    return {"tenant": tenant, "engagement": engagement, "item": item, "version": version}


def test_ac_an_offset_is_line_2e1_and_nothing_else(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _item(seed)
        scope = (ids["tenant"], ids["engagement"], ids["item"], ids["version"])
        loan = await seed.value(
            "INSERT INTO ebp_participant_loans (tenant_id, engagement_id, work_item_id, "
            "evidence_version_id, participant_key, loan_ref, status, ending_balance) "
            "VALUES ($1, $2, $3, $4, 'P-1', 'L-1', 'offset', 0) RETURNING id",
            *scope,
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(
                "INSERT INTO ebp_loan_offsets (tenant_id, engagement_id, work_item_id, "
                "evidence_version_id, loan_id, offset_on, amount, reported_line) VALUES "
                "($1, $2, $3, $4, $5, '2025-06-30', 4850, '2g')",
                *scope,
                loan,
            )

    asyncio.run(scenario())


def test_ac_an_expense_names_its_line_and_an_exception_its_issue(private_db: sc.Database) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _item(seed)
        scope = (ids["tenant"], ids["engagement"], ids["item"], ids["version"])
        insert = (
            "INSERT INTO ebp_plan_expenses (tenant_id, engagement_id, work_item_id, "
            "evidence_version_id, line_key, description, paid_from_plan, schedule_h_line, result) "
            "VALUES ($1, $2, $3, $4, 'mailing', 'Participant notice mailing', 1200, $5, $6)"
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(insert, *scope, "2e(1)", None)
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.run(insert, *scope, "2i(1)", "exception")

    asyncio.run(scenario())
