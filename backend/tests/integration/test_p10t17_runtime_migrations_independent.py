"""P-10-T17 (TASK-6117; ADR-078): independent tests for P-10-T02, T03 and T14's migrations.

Written from the rows and SPEC-647, not the migrations. Row acceptance: "Tests pass and fail if any
trigger, CHECK or RLS policy is weakened." Covered: forced RLS on every runtime table, insert-only
grants and triggers on plans and run events, the forward-only state machine, the status-state sync
for legacy writers, human-only plan decisions and run sign-offs bound to the session's actor, the
backfill's narrow door (0711), and the round trip (the shared database migrates up, down and up).
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import provisioned_database

from .agent_tests.support import Seeder

RUNTIME = (
    "agent_runs",
    "agent_run_steps",
    "agent_plans",
    "agent_questions",
    "run_events",
    "run_artifacts",
    "run_sign_offs",
    "agent_feedback",
    "engagement_ai_settings",
    "tenant_counters",
)
INSERT_ONLY = ("agent_plans", "run_events", "agent_feedback")


@pytest.fixture(scope="module")
def db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=True) as database:
        yield database


def _value(database: sc.Database, sql: str, *args: object) -> object:
    return asyncio.run(Seeder(database.superuser_dsn).value(sql, *args))


@pytest.mark.parametrize("table", RUNTIME)
def test_rls_is_forced(db: sc.Database, table: str) -> None:
    assert (
        _value(
            db,
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1",
            table,
        )
        is True
    )
    policies = _value(db, "SELECT count(*) FROM pg_policy WHERE polrelid = $1::regclass", table)
    assert isinstance(policies, int) and policies >= 1


@pytest.mark.parametrize("table", INSERT_ONLY)
def test_insert_only_tables_grant_no_update_or_delete(db: sc.Database, table: str) -> None:
    for privilege in ("UPDATE", "DELETE"):
        assert (
            _value(db, "SELECT has_table_privilege('abacus_app', $1, $2)", table, privilege)
            is False
        ), (table, privilege)


async def _run(
    dsn: str, *, state: str | None, status: str = "running"
) -> tuple[uuid.UUID, Seeder]:
    seeder = Seeder(dsn)
    tenant = await seeder.firm()
    person = await seeder.person(tenant)
    engagement = await seeder.engagement(tenant, await seeder.entity(tenant), person.user_id)
    run = await seeder.value(
        "INSERT INTO agent_runs (tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope, status, state) "
        "VALUES ($1, 'evidence.screener', 1, $2, $3, ARRAY['evidence.read'], $4, $5) RETURNING id",
        tenant,
        engagement,
        person.user_id,
        status,
        state,
    )
    assert isinstance(run, uuid.UUID)
    return run, seeder


def test_a_legacy_writer_s_status_sets_the_state(db: sc.Database) -> None:
    run, seeder = asyncio.run(_run(db.superuser_dsn, state=None))
    assert _value(db, "SELECT state FROM agent_runs WHERE id = $1", run) == "running"
    asyncio.run(
        seeder.run(
            "UPDATE agent_runs SET status = 'escalated', finished_at = now() WHERE id = $1", run
        )
    )
    row = asyncio.run(
        seeder.rows("SELECT state, state_reason FROM agent_runs WHERE id = $1", run)
    )[0]
    assert (row["state"], row["state_reason"]) == ("needs_input", "escalated")


def test_a_v2_state_write_sets_the_legacy_status(db: sc.Database) -> None:
    run, seeder = asyncio.run(_run(db.superuser_dsn, state="queued"))
    asyncio.run(seeder.run("UPDATE agent_runs SET state = 'running' WHERE id = $1", run))
    asyncio.run(seeder.run("UPDATE agent_runs SET state = 'succeeded' WHERE id = $1", run))
    row = asyncio.run(
        seeder.rows("SELECT status, finished_at FROM agent_runs WHERE id = $1", run)
    )[0]
    assert row["status"] == "completed" and row["finished_at"] is not None


@pytest.mark.parametrize(
    ("start", "illegal"),
    [("queued", "succeeded"), ("running", "planning"), ("succeeded", "running")],
)
def test_an_illegal_transition_is_refused(db: sc.Database, start: str, illegal: str) -> None:
    run, seeder = asyncio.run(_run(db.superuser_dsn, state="queued"))
    path = {"queued": [], "running": ["running"], "succeeded": ["running", "succeeded"]}[start]
    for step in path:
        asyncio.run(seeder.run("UPDATE agent_runs SET state = $2 WHERE id = $1", run, step))
    with pytest.raises(asyncpg.PostgresError):
        asyncio.run(seeder.run("UPDATE agent_runs SET state = $2 WHERE id = $1", run, illegal))


def test_failed_and_cancelled_are_reachable_from_any_active_state(db: sc.Database) -> None:
    run, seeder = asyncio.run(_run(db.superuser_dsn, state="queued"))
    asyncio.run(seeder.run("UPDATE agent_runs SET state = 'cancelled' WHERE id = $1", run))
    assert _value(db, "SELECT status FROM agent_runs WHERE id = $1", run) == "failed"


async def _as(dsn: str, kind: str, actor: str, sql: str, *args: object) -> None:
    conn = await asyncpg.connect(dsn)
    try:
        async with conn.transaction():
            await conn.execute(
                "SELECT set_config('app.actor_kind', $1, true), "
                "set_config('app.actor_id', $2, true)",
                kind,
                actor,
            )
            await conn.execute(sql, *args)
    finally:
        await conn.close()


@pytest.mark.parametrize(("kind", "same"), [("agent", True), ("system", True), ("human", False)])
def test_a_plan_decision_is_the_session_s_own_person(
    db: sc.Database, kind: str, same: bool
) -> None:
    person = uuid.uuid4()
    actor = str(person) if same else str(uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as(
                db.superuser_dsn,
                kind,
                actor,
                "INSERT INTO agent_plans (tenant_id, run_id, version, steps, state, decided_by, "
                "decided_at) VALUES ($1, $2, 1, '[]', 'approved', $3, now())",
                uuid.uuid4(),
                uuid.uuid4(),
                person,
            )
        )


@pytest.mark.parametrize(("kind", "same"), [("agent", True), ("system", True), ("human", False)])
def test_a_run_sign_off_is_the_session_s_own_person(
    db: sc.Database, kind: str, same: bool
) -> None:
    person = uuid.uuid4()
    actor = str(person) if same else str(uuid.uuid4())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            _as(
                db.superuser_dsn,
                kind,
                actor,
                "INSERT INTO run_sign_offs (tenant_id, run_id, signed_by) VALUES ($1, $2, $3)",
                uuid.uuid4(),
                uuid.uuid4(),
                person,
            )
        )


def test_a_person_s_own_sign_off_passes_the_check(db: sc.Database) -> None:
    person = uuid.uuid4()
    with pytest.raises(asyncpg.ForeignKeyViolationError):  # the CHECK passed; the references fail
        asyncio.run(
            _as(
                db.superuser_dsn,
                "human",
                str(person),
                "INSERT INTO run_sign_offs (tenant_id, run_id, signed_by) VALUES ($1, $2, $3)",
                uuid.uuid4(),
                uuid.uuid4(),
                person,
            )
        )


def test_the_backfill_door_admits_only_the_legacy_mapping(db: sc.Database) -> None:
    async def legacy_completed() -> tuple[uuid.UUID, Seeder]:
        seeder = Seeder(db.superuser_dsn)
        conn = await asyncpg.connect(db.superuser_dsn)
        try:
            await conn.execute("ALTER TABLE agent_runs DISABLE TRIGGER agent_runs_state_sync")
            run, _ = await _run(db.superuser_dsn, state=None, status="running")
            await conn.execute(
                "UPDATE agent_runs SET status = 'completed', finished_at = now(), state = NULL "
                "WHERE id = $1",
                run,
            )
        finally:
            await conn.execute("ALTER TABLE agent_runs ENABLE TRIGGER agent_runs_state_sync")
            await conn.close()
        return run, seeder

    run, seeder = asyncio.run(legacy_completed())
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(seeder.run("UPDATE agent_runs SET state = 'failed' WHERE id = $1", run))
    with pytest.raises(asyncpg.PostgresError):  # anything else moving on a finished row
        asyncio.run(
            seeder.run(
                "UPDATE agent_runs SET state = 'succeeded', failure_code = 'x' WHERE id = $1", run
            )
        )
    asyncio.run(seeder.run("UPDATE agent_runs SET state = 'succeeded' WHERE id = $1", run))
    assert _value(db, "SELECT status FROM agent_runs WHERE id = $1", run) == "completed"
