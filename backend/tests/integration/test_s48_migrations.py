"""S48: 0940 to 0947 go down to 0933 and back up. 0940 (A-08-T21, audit analytics), 0941
(A-08-T22, the SSARS inquiry program), 0942 (A-08-T13, MUS reasons), 0943 (A-08-T24, fieldwork
run rows), 0944 (A-09-T27, the instructions send), 0945 (A-09-T28, a deliverable gone late), 0946
(A-09-T30, the group work item) and 0947 (G-04-T10, the operator's EXECUTE grants). Every new table
comes back with forced row-level security, the operator role holds the console writers again, and
the head is single (the migrations chain 0933 → 0947)."""

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

BEFORE = "0933"
NEW_TABLES = (
    "analytics_sets",
    "analytics_lines",
    "analytics_explanations",
    "analytics_expectations",
    "prior_year_figures",
    "analytics_questions",
    "ssars_inquiry_programs",
    "fieldwork_run_rows",
    "component_instruction_sends",
)
OPS_WRITER = "status_incident_post(text, text, text, text, text)"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


def _ops_may_run(database: sc.Database) -> object:
    return _value(
        database, f"SELECT has_function_privilege('abacus_ops', '{OPS_WRITER}', 'EXECUTE')"
    )


def test_0940_to_0947_go_down_and_up_with_forced_rls(private_db: sc.Database) -> None:
    migrate(private_db.owner_url, BEFORE, down=True)
    for table in NEW_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NULL"), table
    assert _ops_may_run(private_db) is False
    migrate(private_db.owner_url, "head")
    for table in NEW_TABLES:
        assert _value(private_db, f"SELECT to_regclass('{table}') IS NOT NULL"), table
        forced = _value(
            private_db,
            "SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        assert forced, table
    assert _ops_may_run(private_db) is True
    # The API's role never holds a console writer (ADR-156).
    assert (
        _value(
            private_db, f"SELECT has_function_privilege('abacus_app', '{OPS_WRITER}', 'EXECUTE')"
        )
        is False
    )


def test_the_head_reaches_0947(private_db: sc.Database) -> None:
    scripts = ScriptDirectory.from_config(
        Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    )
    head = str(_value(private_db, "SELECT version_num FROM alembic_version"))
    assert head == scripts.get_current_head()
    assert "0947" in {r.revision for r in scripts.walk_revisions("base", head)}
