"""P-10-T03 (TASK-5112; P-10 §4.2; SPEC-647): migration 0681 `agent_runtime`.

Row acceptance: "RLS is forced on every table, insert-only triggers refuse UPDATE and DELETE on
plans and run_events, and an agent-context plan decision or run sign-off is refused by the
database."
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Person, Seeder

BEFORE = "0680"
TABLES = (
    "agent_plans",
    "agent_run_steps",
    "agent_questions",
    "run_events",
    "run_artifacts",
    "run_sign_offs",
    "agent_feedback",
    "engagement_ai_settings",
)
PLAN = (
    "INSERT INTO agent_plans (tenant_id, run_id, version, steps, state, decided_by, decided_at) "
    "VALUES ($1, $2, 2, '[]', 'approved', $3, now())"
)
SIGN_OFF = "INSERT INTO run_sign_offs (tenant_id, run_id, signed_by) VALUES ($1, $2, $3)"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _run(seeder: Seeder) -> tuple[Person, uuid.UUID]:
    tenant_id = await seeder.firm()
    who = await seeder.person(tenant_id)
    entity_id = await seeder.entity(tenant_id)
    engagement_id = await seeder.engagement(tenant_id, entity_id, who.user_id)
    run_id = uuid.uuid4()
    await seeder.run(
        "INSERT INTO agent_runs (id, tenant_id, agent_id, spec_version, engagement_id, "
        "initiator_user_id, task_scope) VALUES ($1, $2, 'evidence.matcher', 1, $3, $4, '{}')",
        run_id,
        tenant_id,
        engagement_id,
        who.user_id,
    )
    return who, run_id


@pytest.mark.parametrize("table", TABLES)
def test_rls_is_forced(private_db: sc.Database, table: str) -> None:
    forced = asyncio.run(
        Seeder(private_db.superuser_dsn).value(
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1", table
        )
    )
    assert forced is True


@pytest.mark.parametrize("sql", ["UPDATE agent_plans SET version = 9", "DELETE FROM agent_plans"])
def test_plans_are_insert_only(private_db: sc.Database, sql: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, run_id = asyncio.run(_run(seeder))
    asyncio.run(
        seeder.run(
            "INSERT INTO agent_plans (tenant_id, run_id, version, steps, state) "
            "VALUES ($1, $2, 1, $3, 'proposed')",
            who.tenant_id,
            run_id,
            json.dumps([]),
        )
    )
    with pytest.raises(asyncpg.CheckViolationError, match="insert-only"):
        asyncio.run(seeder.run(f"{sql} WHERE run_id = $1", run_id))


@pytest.mark.parametrize("sql", ["UPDATE run_events SET type = 'x'", "DELETE FROM run_events"])
def test_run_events_are_insert_only(private_db: sc.Database, sql: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, run_id = asyncio.run(_run(seeder))
    asyncio.run(
        seeder.run(
            "INSERT INTO run_events (tenant_id, run_id, run_seq, type) "
            "VALUES ($1, $2, 1, 'run.state')",
            who.tenant_id,
            run_id,
        )
    )
    with pytest.raises(asyncpg.CheckViolationError, match="insert-only"):
        asyncio.run(seeder.run(f"{sql} WHERE run_id = $1", run_id))


@pytest.mark.parametrize("insert", [PLAN, SIGN_OFF])
def test_an_agent_decision_is_refused(private_db: sc.Database, insert: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, run_id = asyncio.run(_run(seeder))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seeder.as_actor(
                who.tenant_id,
                ("agent", str(who.user_id)),
                insert,
                who.tenant_id,
                run_id,
                who.user_id,
            )
        )


@pytest.mark.parametrize("insert", [PLAN, SIGN_OFF])
def test_a_persons_decision_passes(private_db: sc.Database, insert: str) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, run_id = asyncio.run(_run(seeder))
    asyncio.run(
        seeder.as_actor(
            who.tenant_id,
            ("human", str(who.user_id)),
            insert,
            who.tenant_id,
            run_id,
            who.user_id,
        )
    )


def test_someone_elses_name_on_a_sign_off_is_refused(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    who, run_id = asyncio.run(_run(seeder))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seeder.as_actor(
                who.tenant_id,
                ("human", str(uuid.uuid4())),
                SIGN_OFF,
                who.tenant_id,
                run_id,
                who.user_id,
            )
        )


def test_down_then_up(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    assert not asyncio.run(seeder.value("SELECT to_regclass('public.agent_plans') IS NOT NULL"))
    migrate(private_db.owner_url, "head")
    assert asyncio.run(seeder.value("SELECT to_regclass('public.agent_plans') IS NOT NULL"))
