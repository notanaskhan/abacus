"""P-10-T18 (TASK-6118; ADR-078): independent tests for P-10-T04, T05, T06 and T07.

Written from the rows, not the migrations. Row acceptance: "Tests pass and fail if a session item
can be updated or a rollup sums anything but stored integers." Covered: forced RLS, insert-only
session items and minute ledger (grants and triggers), the soft-delete guard on sessions, the
realtime prune refusing anyone but its own job, integer minutes footing 8,640 + 4,610 + 1,420 + 120
+ 130 = 14,920, and the status registry and glossary carrying every runtime state.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from pathlib import Path

import asyncpg
import pytest
import yaml

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

REPO = Path(__file__).resolve().parents[3]
TABLES = (
    "workbench_sessions",
    "session_items",
    "realtime_events",
    "agent_minute_ledger",
    "engagement_agent_budgets",
    "usage_month_rollups",
)
RUN_STATES = {
    "queued", "planning", "awaiting_plan_approval", "dispatched", "running", "needs_input",
    "blocked_on_decision", "waiting_on_inputs", "succeeded", "approved", "partially_approved",
    "rejected", "failed", "cancelled",
}  # fmt: skip


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=True) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


@pytest.mark.parametrize("table", TABLES)
def test_rls_is_forced(db: sc.Database, table: str) -> None:
    assert (
        _value(
            db,
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        is True
    )


@pytest.mark.parametrize(
    ("table", "trigger_function"),
    [
        ("session_items", "session_items_immutable"),
        ("agent_minute_ledger", "agent_minute_ledger_immutable"),
    ],
)
def test_insert_only_tables_refuse_update_and_delete(
    db: sc.Database, table: str, trigger_function: str
) -> None:
    for privilege in ("UPDATE", "DELETE"):
        assert (
            _value(db, "SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege)
            is False
        ), (table, privilege)
    triggers = _value(
        db,
        "SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
        "WHERE t.tgrelid = $1::regclass AND p.proname = $2 AND t.tgenabled <> 'D'",
        table,
        trigger_function,
    )
    assert isinstance(triggers, int) and triggers >= 1


def test_a_session_is_soft_deleted_never_removed(db: sc.Database) -> None:
    assert (
        _value(db, "SELECT has_table_privilege('abacus_app', 'workbench_sessions', 'DELETE')")
        is False
    )
    assert (
        _value(
            db,
            "SELECT count(*) FROM pg_trigger t JOIN pg_proc p ON p.oid = t.tgfoid "
            "WHERE t.tgrelid = 'workbench_sessions'::regclass "
            "AND p.proname = 'workbench_sessions_soft_delete'",
        )
        == 1
    )


@pytest.mark.parametrize(
    ("kind", "actor"),
    [
        ("human", "0b6f1c1e-5a7d-4c1f-9d2e-3f4a5b6c7d8e"),  # a fixed id: xdist collects alike
        ("system", "someone.else"),
        ("agent", "notifications.realtime_prune"),
    ],
)
def test_only_the_realtime_prune_deletes_realtime_events(
    db: sc.Database, kind: str, actor: str
) -> None:
    async def call() -> None:
        conn = await asyncpg.connect(db.superuser_dsn)
        try:
            async with conn.transaction():
                await conn.execute(
                    "SELECT set_config('app.tenant_id', $1, true), "
                    "set_config('app.actor_kind', $2, true), set_config('app.actor_id', $3, true)",
                    str(uuid.uuid4()),
                    kind,
                    actor,
                )
                await conn.execute("SELECT prune_realtime_events(100)")
        finally:
            await conn.close()

    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        asyncio.run(call())


def test_rollup_minutes_are_stored_integers_and_foot(db: sc.Database) -> None:
    kind = _value(
        db,
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_name = 'usage_month_rollups' AND column_name = 'minutes'",
    )
    assert kind in ("bigint", "integer")
    tenant = uuid.uuid4()

    async def load() -> object:
        seeder = Seeder(db.superuser_dsn)
        for capability, minutes in (
            ("evidence.screener", 8640),
            ("evidence.matcher", 4610),
            ("workpapers.section_drafter", 1420),
            ("notices.responder", 120),
            ("runtime.conformance", 130),
        ):
            await seeder.run(
                "INSERT INTO usage_month_rollups (tenant_id, usage_month, service_line, "
                "capability, minutes, cost_usd) VALUES ($1, '2027-12', 'audit', $2, $3, 0)",
                tenant,
                capability,
                minutes,
            )
        return await seeder.value(
            "SELECT sum(minutes) FROM usage_month_rollups WHERE tenant_id = $1", tenant
        )

    assert asyncio.run(load()) == 14920


def test_the_registry_carries_every_runtime_state() -> None:
    vocabulary = yaml.safe_load((REPO / "docs/product/status-vocabulary.yaml").read_text())
    objects = vocabulary["objects"]
    assert set(objects["agent_run"]["codes"]) == RUN_STATES
    for name in ("agent_run_step", "workbench_session", "agent_question"):
        codes = objects[name]["codes"]
        assert codes and all(c.get("label") for c in codes.values()), name


@pytest.mark.parametrize(
    "term",
    ["agent_run_step", "agent_plan", "agent_question", "run_event", "workbench_session"],
)
def test_the_glossary_names_the_runtime_terms(term: str) -> None:
    glossary = (REPO / "docs/product/glossary.md").read_text(encoding="utf-8")
    assert term in glossary
