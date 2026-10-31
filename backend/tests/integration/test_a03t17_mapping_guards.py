"""A-03-T17 (TASK-2815; DEC-1864): the database half of the independent AC suite for the ledger
mapping and grouping work: the human-only CHECK on a published grouping-set version, the freeze
triggers that refuse an edit to a published version, and forced row-level security on every
mapping table. Each assertion names the guard, so removing one fails here.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

MAPPING_TABLES = (
    "grouping_sets",
    "grouping_set_versions",
    "mapping_sets",
    "mapping_set_edits",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_the_human_only_check_on_publish(private_db: sc.Database) -> None:
    """`published_actor_kind = 'human'` (0079): the agent or the system never publishes."""
    found = _value(
        private_db,
        "SELECT count(*) FROM pg_constraint c JOIN pg_class t ON t.oid = c.conrelid "
        "WHERE t.relname = 'grouping_set_versions' AND c.contype = 'c' "
        "AND pg_get_constraintdef(c.oid) LIKE $1",
        "%published_actor_kind%human%",
    )
    assert found == 1


@pytest.mark.parametrize("trigger", ["grouping_set_version_frozen", "grouping_set_version_guard"])
def test_the_freeze_triggers(private_db: sc.Database, trigger: str) -> None:
    found = _value(
        private_db,
        "SELECT count(*) FROM pg_trigger g JOIN pg_class t ON t.oid = g.tgrelid "
        "WHERE t.relname = 'grouping_set_versions' AND g.tgname = $1 AND NOT g.tgisinternal",
        trigger,
    )
    assert found == 1, trigger


@pytest.mark.parametrize("table", MAPPING_TABLES)
def test_forced_rls_on_every_mapping_table(private_db: sc.Database, table: str) -> None:
    assert _value(
        private_db,
        "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
        table,
    ), table
