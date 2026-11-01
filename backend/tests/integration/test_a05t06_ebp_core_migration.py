"""A-05-T06 (TASK-2812; DEC-1861): migration 0610 `ebp_core`.

Row acceptance: "Upgrade and downgrade pass on the synthetic seed, a walled user reads zero rows,
and a conflict or check row cannot be updated or deleted." Down to 0580 removes the five tables
and up again restores them with forced row-level security; the app role may not update or delete
a provider check or a provision conflict, nor delete any EBP row; the schema check passes. A
walled user's zero rows is the service's `visible()` (as for every engagement table), tested with
the EBP-01 service (A-05-T08).
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0580"
TABLES = (
    "ebp_plans",
    "ebp_service_providers",
    "ebp_provider_checks",
    "ebp_provisions",
    "ebp_provision_conflicts",
)
INSERT_ONLY = ("ebp_provider_checks", "ebp_provision_conflicts")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql))


def test_ac_0610_goes_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
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
def test_ac_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_ac_a_check_or_conflict_row_is_never_updated(private_db: sc.Database, table: str) -> None:
    assert not _value(
        private_db,
        f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')",
    )
    # Inserts are column-granted (`insert_columns`): the role writes only the listed columns.
    assert _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'INSERT')"
    )
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'INSERT')")
