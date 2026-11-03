"""N-04-T08 (TASK-3205; DEC-2205): migration 0656, envelope document page ranges.

Down to 0655 removes the two columns; up restores them with the both-or-neither rule.
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


def _has(database: sc.Database, column: str) -> bool:
    return bool(
        _value(
            database,
            "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = "
            "'envelope_documents' AND column_name = $1)",
            column,
        )
    )


def test_ac1_0656_goes_down_and_up(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0655", down=True)
    assert not _has(private_db, "page_from")
    migrate(private_db.owner_url, "head")
    assert _has(private_db, "page_from") and _has(private_db, "page_to")


def test_ac1_a_range_is_both_or_neither_and_in_order(private_db: sc.Database) -> None:
    check = _value(
        private_db,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'envelope_documents_page_range'",
    )
    assert isinstance(check, str)
    assert "page_from <= page_to" in check
    assert "page_to <= page_count" in check
