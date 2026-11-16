"""S45: 0885 to 0890 go down to 0884 and back up. 0885 (C-01-T11, `closes_v2` and
`requests_cas`), 0886 (T-07-T11, the `instrument_clause` citation kind), 0887 (A-08-T03, the
`confirmation_links` platform control), 0888 (A-08-T09, GL journal-entry fields), 0889 (A-09-T05,
`ledger_consolidation`) and 0890 (W-01-T04, `integrations_connect`). Every new table comes back
with forced row-level security, and the head is single (the migrations chain 0884 → 0890)."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0884"
NEW_TABLES = (
    "consolidations",
    "consolidation_entities",
    "consolidation_trial_balances",
    "consolidation_events",
    "integration_catalog_imports",
    "user_integrations",
    "integration_oauth_states",
    "integration_events",
    "integration_interest",
)
GLOBAL = frozenset({"integration_catalog_imports"})


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def test_0885_to_0890_go_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in NEW_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    assert _value(
        private_db,
        "SELECT NOT EXISTS (SELECT 1 FROM information_schema.columns "
        "WHERE table_name = 'gl_entries' AND column_name = 'posted_by')",
    )
    migrate(private_db.owner_url, "head")
    for table in NEW_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NOT NULL"), table
        if table in GLOBAL:
            continue
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table
    for table in ("connections", "firm_integrations"):  # 0890 lifts FORCE for its backfill only
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table


def test_the_head_is_0890(private_db: sc.Database) -> None:
    """The chain reaches 0890 and the database sits at the script head (S46 chains 0891 to 0901
    on it; a later sprint's head is still past 0890)."""
    scripts = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    )
    head = str(_value(private_db, "SELECT version_num FROM alembic_version"))
    assert head == scripts.get_current_head()
    assert "0890" in {r.revision for r in scripts.walk_revisions("base", head)}
