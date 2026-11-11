"""T-04-T31 (TASK-6819; DEC-3413): migration 0812, an issue's runs, fix proposals, explanations.

Each table is insert-only (its trigger named and exercised), forced RLS, and bound to the
transaction's actor: a run row is a person's, a fix proposal and an explanation the agent's.
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

TABLES = ("issue_runs", "issue_fix_proposals", "issue_explanations")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_the_migration_goes_down_and_up(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0811", down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    migrate(private_db.owner_url, "head")


@pytest.mark.parametrize("table", TABLES)
def test_each_table_is_forced_rls_and_insert_only(private_db: sc.Database, table: str) -> None:
    assert _value(
        private_db,
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
        table,
    )
    assert _value(
        private_db,
        "SELECT count(*) = 2 FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid "
        "JOIN pg_proc p ON p.oid = t.tgfoid WHERE c.relname = $1 AND NOT t.tgisinternal "
        "AND p.proname = 'review_rows_immutable'",
        table,
    )
    for privilege in ("UPDATE", "DELETE", "TRUNCATE"):
        assert not _value(
            private_db, f"SELECT has_table_privilege('abacus_app', '{table}', '{privilege}')"
        ), (table, privilege)


async def _issue(seed: Seeder) -> dict[str, uuid.UUID]:
    tenant = await seed.firm()
    person = await seed.person(tenant)
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, person.user_id)
    issue = cast(
        uuid.UUID,
        await seed.value(
            "INSERT INTO issues (tenant_id, engagement_id, record_ref, kind, priority, "
            "title_sealed, status) VALUES ($1, $2, jsonb_build_object('type', 'tax_return', "
            "'id', gen_random_uuid()::text), 'missing_information', 'medium', '\\x00', 'open') "
            "RETURNING id",
            tenant,
            engagement,
        ),
    )
    return {"tenant": tenant, "person": person.user_id, "issue": issue}


def test_a_run_row_is_a_persons_and_its_proposal_and_explanation_the_agents(
    private_db: sc.Database,
) -> None:
    async def scenario() -> None:
        seed = Seeder(private_db.superuser_dsn)
        ids = await _issue(seed)
        run = uuid.uuid4()
        human = ("human", str(ids["person"]))
        agent = ("agent", str(run))
        row = (
            "INSERT INTO issue_runs (tenant_id, issue_id, agent_run_id, purpose) "
            "VALUES ($1, $2, $3, $4)"
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(ids["tenant"], agent, row, ids["tenant"], ids["issue"], run, "fix")
        await seed.as_actor(ids["tenant"], human, row, ids["tenant"], ids["issue"], run, "fix")
        fix = (
            "INSERT INTO issue_fix_proposals (tenant_id, issue_id, agent_run_id, proposal_id) "
            "VALUES ($1, $2, $3, $4)"
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(
                ids["tenant"], human, fix, ids["tenant"], ids["issue"], run, uuid.uuid4()
            )
        proposal = uuid.uuid4()
        await seed.as_actor(ids["tenant"], agent, fix, ids["tenant"], ids["issue"], run, proposal)
        with pytest.raises(asyncpg.UniqueViolationError):  # one proposal per run
            await seed.as_actor(
                ids["tenant"], agent, fix, ids["tenant"], ids["issue"], run, uuid.uuid4()
            )
        explained = (
            "INSERT INTO issue_explanations (tenant_id, issue_id, agent_run_id, text_sealed, "
            "citation_ids) VALUES ($1, $2, $3, '\\x00', ARRAY[gen_random_uuid()])"
        )
        with pytest.raises(asyncpg.CheckViolationError):
            await seed.as_actor(ids["tenant"], human, explained, ids["tenant"], ids["issue"], run)
        await seed.as_actor(ids["tenant"], agent, explained, ids["tenant"], ids["issue"], run)
        with pytest.raises(asyncpg.ForeignKeyViolationError):  # only a run a person started
            await seed.as_actor(
                ids["tenant"], agent, explained, ids["tenant"], ids["issue"], uuid.uuid4()
            )
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await seed.run("UPDATE issue_fix_proposals SET proposal_id = $1", uuid.uuid4())

    asyncio.run(scenario())
