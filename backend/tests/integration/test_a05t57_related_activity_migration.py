"""A-05-T57 close (S31; TASK-6232; DEC-2827): migration 0743 `related_party_activity`.

A related party carries the year's transactions and its disclosure as a person recorded them; a
note link needs the note's words, and the app role may write the three columns and no others.
"""

from __future__ import annotations

import asyncio
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

COLUMNS = ("transactions", "disclosure", "disclosure_note")


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


@pytest.mark.parametrize("column", COLUMNS)
def test_the_app_role_may_insert_and_update_the_column(
    private_db: sc.Database, column: str
) -> None:
    for privilege in ("INSERT", "UPDATE"):
        assert (
            _value(
                private_db,
                "SELECT has_column_privilege('abacus_app', 'related_parties', $1, $2)",
                column,
                privilege,
            )
            is True
        )


def test_a_note_link_needs_the_disclosure(private_db: sc.Database) -> None:
    assert (
        _value(
            private_db,
            "SELECT count(*) FROM pg_constraint WHERE conname = 'related_parties_disclosure_note' "
            "AND conrelid = 'related_parties'::regclass",
        )
        == 1
    )


def test_transactions_default_to_none(private_db: sc.Database) -> None:
    assert (
        _value(
            private_db,
            "SELECT column_default FROM information_schema.columns "
            "WHERE table_name = 'related_parties' AND column_name = 'transactions'",
        )
        == "'[]'::jsonb"
    )


def test_down_then_up(private_db: sc.Database) -> None:
    exists = (
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'related_parties' AND column_name = 'disclosure_note'"
    )
    migrate(private_db.owner_url, "0742", down=True)
    assert _value(private_db, exists) == 0
    migrate(private_db.owner_url, "head")
    assert _value(private_db, exists) == 1
