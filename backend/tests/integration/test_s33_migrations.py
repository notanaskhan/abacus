"""S33 end pass: 0760 (P-05-T04, collaboration v2) and 0761 (T-04-T10, the individual return
workspace) go down to 0751 and back up with forced row-level security; the app role never deletes
and never updates an insert-only row; inserts are column-granted."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0751"
COLLABORATION = (
    "comment_threads",
    "comment_thread_events",
    "thread_comments",
    "thread_comment_mentions",
    "thread_comment_redactions",
    "comment_thread_reads",
    "todos",
    "todo_checklist_items",
)
WORKSPACE = (
    "return_worksheets",
    "return_worksheet_sections",
    "return_fields",
    "document_approvals",
    "k1_activities",
    "k1_treatments",
    "k1_treatment_events",
    "residency_determinations",
    "residency_facts",
)
TABLES = COLLABORATION + WORKSPACE
INSERT_ONLY = (
    "comment_thread_events",
    "thread_comments",
    "thread_comment_mentions",
    "thread_comment_redactions",
    "document_approvals",
    "k1_treatment_events",
    "residency_facts",
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql))


def test_0760_and_0761_go_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
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


# P-05 §4.2: a to-do's checklist is a mutable sub-list (at most 8 items), every change audited by
# the service, so its items keep DELETE; every other new table refuses it.
MUTABLE_LIST = "todo_checklist_items"


@pytest.mark.parametrize("table", [t for t in TABLES if t != MUTABLE_LIST])
def test_the_app_role_never_deletes(private_db: sc.Database, table: str) -> None:
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'DELETE')")


def test_checklist_items_are_the_one_deletable_list(private_db: sc.Database) -> None:
    assert _value(
        private_db, f"SELECT has_table_privilege('abacus_app', '{MUTABLE_LIST}', 'DELETE')"
    )


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_an_insert_only_row_is_never_updated(private_db: sc.Database, table: str) -> None:
    assert not _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'UPDATE')"
    )
    assert _value(
        private_db, f"SELECT has_any_column_privilege('abacus_app', '{table}', 'INSERT')"
    )
    assert not _value(private_db, f"SELECT has_table_privilege('abacus_app', '{table}', 'INSERT')")
