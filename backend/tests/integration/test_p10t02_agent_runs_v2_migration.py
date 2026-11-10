"""P-10-T02 (TASK-5111; P-10 §4.2; SPEC-647): migration 0680 `agent_runs_v2`.

Row acceptance: "up/down/up passes, legacy screener and matcher writes of status still pass their
tests and set state, and an illegal state transition is refused by the trigger."
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator

import asyncpg
import pytest

from abacus_tools.quality import schema_check as sc
from abacus_tools.quality.schema_check import migrate, provisioned_database

from .agent_tests.support import Seeder

BEFORE = "0672"


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _run(seeder: Seeder) -> tuple[uuid.UUID, uuid.UUID]:
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
    return tenant_id, run_id


def _cells(seeder: Seeder, run_id: uuid.UUID) -> tuple[object, object, object]:
    rows = asyncio.run(
        seeder.rows("SELECT status, state, state_reason FROM agent_runs WHERE id = $1", run_id)
    )
    return rows[0]["status"], rows[0]["state"], rows[0]["state_reason"]


def test_a_legacy_status_write_sets_state(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, run_id = asyncio.run(_run(seeder))
    assert _cells(seeder, run_id)[:2] == ("running", "running")
    asyncio.run(
        seeder.run(
            "UPDATE agent_runs SET status = 'escalated', finished_at = now() WHERE id = $1", run_id
        )
    )
    assert _cells(seeder, run_id) == ("escalated", "needs_input", "escalated")


def test_a_v2_state_write_sets_status(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, run_id = asyncio.run(_run(seeder))
    asyncio.run(seeder.run("UPDATE agent_runs SET state = 'succeeded' WHERE id = $1", run_id))
    assert _cells(seeder, run_id)[:2] == ("completed", "succeeded")
    asyncio.run(seeder.run("UPDATE agent_runs SET state = 'approved' WHERE id = $1", run_id))
    assert _cells(seeder, run_id)[:2] == ("completed", "approved")


def test_cancelling_sets_what_status_constrains(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, run_id = asyncio.run(_run(seeder))
    asyncio.run(seeder.run("UPDATE agent_runs SET state = 'cancelled' WHERE id = $1", run_id))
    assert _cells(seeder, run_id)[:2] == ("failed", "cancelled")


@pytest.mark.parametrize(
    ("first", "illegal"),
    [("succeeded", "running"), ("failed", "running"), ("cancelled", "succeeded")],
)
def test_an_illegal_transition_is_refused(
    private_db: sc.Database, first: str, illegal: str
) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, run_id = asyncio.run(_run(seeder))
    asyncio.run(seeder.run("UPDATE agent_runs SET state = $2 WHERE id = $1", run_id, first))
    with pytest.raises(asyncpg.CheckViolationError, match="cannot move"):
        asyncio.run(seeder.run("UPDATE agent_runs SET state = $2 WHERE id = $1", run_id, illegal))


def test_down_then_up(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    migrate(private_db.owner_url, BEFORE, down=True)
    assert not asyncio.run(
        seeder.value("SELECT to_regclass('public.tenant_counters') IS NOT NULL")
    )
    migrate(private_db.owner_url, "head")
    assert asyncio.run(seeder.value("SELECT to_regclass('public.tenant_counters') IS NOT NULL"))
