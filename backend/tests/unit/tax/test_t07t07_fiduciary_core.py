"""T-07-T07 (TASK-8021; T-07 §4.2 M1; SPEC-656 AC-15.5; DEC-5010): `fiduciary_core` (0883).

Row acceptance: "The single-head check passes, RLS isolates two tenants on every new table, the
human-only CHECK rejects an agent-recorded election, and insert-only tables have no UPDATE
grant." The database halves (RLS, the CHECK firing, the grants) run in the security and
migration suites at the end pass (`tests/security/test_tenant_isolation.py` lists the tables);
this file holds the registry and the migration text to the same rules."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

from abacus.modules.tax import registry

MIGRATION = Path(__file__).parents[3] / "migrations" / "versions" / "0883_fiduciary_core.py"
UPDATABLE = {"trust_profiles", "instrument_interpretations"}


def _migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location("m0883", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_ac15_5_it_chains_on_0882() -> None:
    module = _migration()
    assert module.revision == "0883"
    assert module.down_revision == "0882"


def test_every_new_table_is_registered_and_only_two_take_updates() -> None:
    tables = set(_migration().TABLES)
    assert len(tables) == 16
    assert tables <= registry.TABLES
    assert tables - UPDATABLE <= registry.INSERT_ONLY
    assert not (UPDATABLE & registry.INSERT_ONLY)
    for table in tables:
        assert table in registry.INSERT_COLUMNS, table
    for table in tables - UPDATABLE:
        assert table not in registry.UPDATE_COLUMNS, table


def test_the_interpretation_updates_only_its_lifecycle() -> None:
    assert registry.UPDATE_COLUMNS["instrument_interpretations"] == {
        "status",
        "scenario",
        "read_run_id",
        "version_no",
        "content_hash",
        "locked_at",
        "reopen_reason_sealed",
        "superseded_at",
        "row_version",
    }


def test_ac15_5_the_election_is_human_only_by_check() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "actor_kind text NOT NULL DEFAULT 'human' CHECK (actor_kind = 'human')" in text
    assert "paid_on <= window_end" in text


def test_ac3_1_governed_keys_need_a_clause_and_human_changes_a_reason() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    assert "cardinality(citation_ids) >= 1" in text
    assert "NOT (set_by_kind = 'human' AND seq > 1) OR reason_sealed IS NOT NULL" in text
    assert "'interpretation_locked'" in text


def test_no_clause_text_is_stored() -> None:
    text = MIGRATION.read_text(encoding="utf-8")
    start = text.index("CREATE TABLE instrument_clauses")
    clauses = text[start : text.index('"""', start)]
    assert "text_sha256" in clauses
    assert " text text" not in clauses and "clause_text" not in clauses
