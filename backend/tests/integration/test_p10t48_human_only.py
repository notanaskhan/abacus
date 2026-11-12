"""P-10-T48 (TASK-7313; ADR-078 as amended; SPEC-647 AC-W2, AC-W7, AC-P6): the database layer of
the human-only decisions, independent of the services. A plan decision and a run sign-off are a
person's own rows (bound to the session's actor GUCs, the 0023 pattern), and the app role never
updates or deletes them; the matrix denies the agent every decision action."""

from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
import yaml

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

MATRIX = Path(__file__).resolve().parents[3] / "docs" / "architecture" / "permission-matrix"


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


# agent_plans carries no actor-kind CHECK (0681): its decision rows are a person's through the
# matrix (agent and system deny) and the route; recorded in TASK-7318 as a defence-in-depth gap.
@pytest.mark.parametrize(("table", "column"), [("run_sign_offs", "actor_kind")])
def test_a_decision_row_must_be_a_persons(db: sc.Database, table: str, column: str) -> None:
    checks = str(
        _value(
            db,
            "SELECT string_agg(pg_get_constraintdef(oid), ' ') FROM pg_constraint "
            "WHERE conrelid = $1::regclass AND contype = 'c'",
            table,
        )
    )
    assert f"{column} = 'human'" in checks
    assert "current_setting(" in checks  # bound to the session's actor (the 0023 pattern)


@pytest.mark.parametrize("table", ["agent_plans", "run_sign_offs"])
def test_the_app_role_never_rewrites_a_decision(db: sc.Database, table: str) -> None:
    assert not _value(db, "SELECT has_any_column_privilege('abacus_app', $1, 'UPDATE')", table)
    assert not _value(db, "SELECT has_table_privilege('abacus_app', $1, 'DELETE')", table)


def test_the_matrix_denies_the_agent_every_run_decision() -> None:
    raw = yaml.safe_load((MATRIX / "agents.yaml").read_text(encoding="utf-8"))
    actions = raw["actions"]
    for action in ("agent_run.approve_plan", "agent_run.answer", "agent_run.sign_off"):
        assert actions[action]["agent"] == "deny", action
        assert actions[action].get("system", "deny") == "deny", action
