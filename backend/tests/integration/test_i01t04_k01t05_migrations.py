"""I-01-T04 and K-01-T05 (TASK-1425, TASK-1427): migrations 0223 and 0224 go down and up.

"Up/down/up passes" (I-01-T04 acceptance): from 0220, a gate projected before 0223 gains its
`subkind` from the subject type it was projected under; down to 0220 drops the snoozes,
reassignments and programs tables and the new columns; up again yields a schema that passes the
schema check (forced RLS, grants, insert-only and immutable tables, no unreviewed definer).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0220"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _revision(database: sc.Database) -> str:
    seed = Seeder(database.superuser_dsn)
    return str(asyncio.run(seed.value("SELECT version_num FROM alembic_version")))


def test_ac_0223_and_0224_go_down_and_up_and_backfill_subkind(private_db: sc.Database) -> None:
    seed = Seeder(private_db.superuser_dsn)
    head = _revision(private_db)
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in ("human_gate_snoozes", "human_gate_reassignments", "programs", "program_steps"):
        assert asyncio.run(seed.value(f"SELECT to_regclass('{table}') IS NULL")), table

    tenant = asyncio.run(seed.firm())
    gate = uuid.uuid4()
    asyncio.run(
        seed.run(
            "INSERT INTO human_gates (id, tenant_id, kind, subject_ref, source_event_id) "
            "VALUES ($1, $2, 'decision', "
            "jsonb_build_object('type', 'acceptance_decision_due', 'id', gen_random_uuid()), $3)",
            gate,
            tenant,
            uuid.uuid4(),
        )
    )
    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == head
    row = asyncio.run(
        seed.rows("SELECT subkind, blocked, office_id FROM human_gates WHERE id = $1", gate)
    )[0]
    assert (row["subkind"], row["blocked"], row["office_id"]) == (
        "acceptance_decision_due",
        False,
        None,
    )

    migrate(private_db.owner_url, BEFORE, down=True)
    assert (
        asyncio.run(
            seed.value(
                "SELECT count(*) FROM information_schema.columns "
                "WHERE table_name = 'human_gates' AND column_name = 'subkind'"
            )
        )
        == 0
    )
    migrate(private_db.owner_url, "head")
    assert _revision(private_db) == head
    assert sc.check(private_db.owner_url, private_db.app_url) == []
