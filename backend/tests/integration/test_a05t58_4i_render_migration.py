"""A-05-T58 remainder (S31; TASK-6233; DEC-2828): migrations 0744 and 0745.

0744 stores the facts Schedule H line 4i's column (c) reads (a holding's description, a loan's
interest rate); 0745 lets C11 keep the code-composed `ebp_supplemental_schedule` kind.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


@pytest.mark.parametrize(
    ("table", "column"),
    [("ebp_trust_report_lines", "description"), ("ebp_participant_loans", "interest_rate")],
)
def test_the_app_role_may_insert_the_fact(
    private_db: sc.Database, table: str, column: str
) -> None:
    assert (
        _value(
            private_db,
            "SELECT has_column_privilege('abacus_app', $1, $2, 'INSERT')",
            table,
            column,
        )
        is True
    )


@pytest.mark.parametrize(
    ("table", "check"),
    [
        ("generated_documents", "generated_documents_kind_check"),
        ("report_templates", "report_templates_family_check"),
    ],
)
def test_the_kind_lists_name_the_supplemental_schedule(
    private_db: sc.Database, table: str, check: str
) -> None:
    definition = _value(
        private_db,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = $1 AND conrelid = $2::regclass",
        check,
        table,
    )
    assert "ebp_supplemental_schedule" in str(definition)
    assert "fs_package" in str(definition)


def test_down_then_up(private_db: sc.Database) -> None:
    exists = (
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'ebp_participant_loans' AND column_name = 'interest_rate'"
    )
    migrate(private_db.owner_url, "0743", down=True)
    assert _value(private_db, exists) == 0
    migrate(private_db.owner_url, "head")
    assert _value(private_db, exists) == 1
