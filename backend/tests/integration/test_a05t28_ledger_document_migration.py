"""A-05-T28 (TASK-3208; DEC-2208): migration 0659, a document-extracted snapshot's provenance."""

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


def test_ac_0659_goes_down_and_up_and_requires_provenance(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, "0658", down=True)
    assert not _value(
        private_db,
        "SELECT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = "
        "'ledger_snapshots' AND column_name = 'extraction_run_id')",
    )
    migrate(private_db.owner_url, "head")
    check = _value(
        private_db,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
        "WHERE conname = 'ledger_snapshots_document_provenance'",
    )
    assert isinstance(check, str) and "document_extraction" in check
    assert not _value(
        private_db,
        "SELECT has_column_privilege('abacus_app', 'ledger_snapshots', "
        "'source_evidence_version_id', 'UPDATE')",
    )
