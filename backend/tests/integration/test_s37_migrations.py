"""S37: 0820 (P-10-T44, frozen run traces) and 0821 (T-05-T17, the entity return core) go down to
0813 and back up with forced row-level security; the app role never deletes; insert-only rows are
never updated; inserts are column-granted; an approved allocation structure is a person's row.

Row acceptance (T-05-T17): "RLS, insert-only triggers and the single-head check pass, and the
migration runs dark without touching live-path code."
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0813"
TABLES = (
    "agent_run_traces",
    "entity_return_profiles",
    "partners",
    "ownership_periods",
    "interest_transfers",
    "allocation_structures",
    "allocation_rungs",
    "allocation_results",
)
INSERT_ONLY = ("agent_run_traces", "allocation_structures", "allocation_results")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql))


def test_0820_and_0821_go_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    assert not _value(
        private_db,
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'k1_packages' AND column_name = 'partner_id')",
    )
    migrate(private_db.owner_url, "head")
    for table in TABLES:
        forced = asyncio.run(
            Seeder(private_db.superuser_dsn).value(
                "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
                table,
            )
        )
        assert forced, table


@pytest.mark.parametrize("table", TABLES)
def test_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_an_insert_only_row_is_never_updated(private_db: sc.Database, table: str) -> None:
    assert not _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')"
    )
    assert _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'INSERT')"
    )
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'INSERT')")


def test_an_approved_structure_must_be_a_persons_row(private_db: sc.Database) -> None:
    checks = _value(
        private_db,
        "SELECT string_agg(pg_get_constraintdef(oid), ' ') FROM pg_constraint "
        "WHERE conrelid = 'allocation_structures'::regclass AND contype = 'c'",
    )
    assert "decided_actor_kind = 'human'" in str(checks)
    assert "convention = 'calendar_day'" in str(checks)
