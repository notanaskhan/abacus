"""P-10-T22 (TASK-6301; SPEC-647 AC-R7; DEC-3001): migration 0750 `agent_tool_calls`, C17's
idempotency key.

The key `(run_id, step_seq, attempt)` is unique per tenant, row-level security is forced, and a
row moves `claimed` -> `done` once: a done call is never rewritten or deleted, and only a claim
(an effect that failed before it committed) can be released.
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

SHA = "a" * 64
CLAIM = (
    "INSERT INTO agent_tool_calls (tenant_id, run_id, step_seq, attempt, tool_name, args_hash) "
    "VALUES ($1, $2, 1, 1, 'evidence.search', $3) RETURNING id"
)


@pytest.fixture(scope="module")
def private_db() -> Iterator[sc.Database]:
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _claimed(seeder: Seeder) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
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
    call_id = await seeder.value(CLAIM, tenant_id, run_id, SHA)
    assert isinstance(call_id, uuid.UUID)
    return tenant_id, run_id, call_id


def test_ac_r7_rls_is_forced(private_db: sc.Database) -> None:
    forced = asyncio.run(
        Seeder(private_db.superuser_dsn).value(
            "SELECT relforcerowsecurity AND relrowsecurity FROM pg_class WHERE relname = $1",
            "agent_tool_calls",
        )
    )
    assert forced is True


def test_ac_r7_one_row_per_key(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    tenant_id, run_id, _ = asyncio.run(_claimed(seeder))
    with pytest.raises(asyncpg.UniqueViolationError):
        asyncio.run(seeder.value(CLAIM, tenant_id, run_id, SHA))


def test_ac_r7_a_claim_moves_to_done_once(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, _, call_id = asyncio.run(_claimed(seeder))
    done = (
        "UPDATE agent_tool_calls SET state = 'done', result = '{\"id\": 1}', "
        "completed_at = now() WHERE id = $1"
    )
    asyncio.run(seeder.run(done, call_id))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(seeder.run(done, call_id))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(seeder.run("DELETE FROM agent_tool_calls WHERE id = $1", call_id))


def test_ac_r7_a_claim_keeps_its_arguments(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, _, call_id = asyncio.run(_claimed(seeder))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seeder.run(
                "UPDATE agent_tool_calls SET state = 'done', result = '{}', completed_at = now(), "
                "args_hash = $2 WHERE id = $1",
                call_id,
                "b" * 64,
            )
        )


def test_ac_r7_a_failed_claim_is_released(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    tenant_id, run_id, call_id = asyncio.run(_claimed(seeder))
    asyncio.run(seeder.run("DELETE FROM agent_tool_calls WHERE id = $1", call_id))
    assert asyncio.run(seeder.value(CLAIM, tenant_id, run_id, SHA)) is not None


def test_ac_r7_done_needs_a_result(private_db: sc.Database) -> None:
    seeder = Seeder(private_db.superuser_dsn)
    _, _, call_id = asyncio.run(_claimed(seeder))
    with pytest.raises(asyncpg.CheckViolationError):
        asyncio.run(
            seeder.run(
                "UPDATE agent_tool_calls SET state = 'done', completed_at = now() WHERE id = $1",
                call_id,
            )
        )
