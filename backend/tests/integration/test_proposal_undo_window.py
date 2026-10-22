"""P-04-T05 against Postgres (migration 0095; DEC-24, ADR-161): an Undo more than 10 seconds
after its decision is refused by trigger, as is a second Undo; decisions are human-only and
insert-only for every role."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
T0 = "2026-09-14T09:41:00-05:00"
DECIDE = (
    "INSERT INTO suggestion_decisions (id, tenant_id, suggestion_id, decision, decided_by, "
    "undoes_decision_id) VALUES ($1, $2, $3, $4, $5, $6)"
)


async def _setup(seed: Seeder) -> tuple[uuid.UUID, uuid.UUID, tuple[str, str], uuid.UUID]:
    tenant = await seed.firm()
    await seed.run("UPDATE firms SET synthetic = true WHERE tenant_id = $1", tenant)
    suggestion = uuid.uuid4()
    await seed.as_actor(
        tenant,
        ("agent", "agent:probe"),
        "INSERT INTO suggestions (id, tenant_id, target_type, target_id, field_key, "
        "proposed_value, agent_run_id) VALUES ($1, $2, 'workpaper', $3, 'C14', "
        '\'{"t": "decimal", "v": "2310"}\', $4)',
        suggestion,
        tenant,
        uuid.uuid4(),
        uuid.uuid4(),
        at=T0,
    )
    person = uuid.uuid4()
    return tenant, suggestion, ("human", str(person)), person


async def _decide(
    seed: Seeder,
    tenant: uuid.UUID,
    suggestion: uuid.UUID,
    who: tuple[str, str],
    by: uuid.UUID,
    decision: str,
    undoes: uuid.UUID | None,
    at: str,
) -> uuid.UUID:
    made = uuid.uuid4()
    await seed.as_actor(tenant, who, DECIDE, made, tenant, suggestion, decision, by, undoes, at=at)
    return made


async def test_undo_within_ten_seconds_once_and_never_after(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, suggestion, hannah, by = await _setup(seed)
    adopted = await _decide(seed, tenant, suggestion, hannah, by, "adopted", None, T0)
    await _decide(
        seed, tenant, suggestion, hannah, by, "undone", adopted, "2026-09-14T09:41:07-05:00"
    )
    with pytest.raises(asyncpg.CheckViolationError, match="undo_window_closed"):  # twice
        await _decide(
            seed, tenant, suggestion, hannah, by, "undone", adopted, "2026-09-14T09:41:08-05:00"
        )
    late = await _decide(seed, tenant, suggestion, hannah, by, "dismissed", None, T0)
    with pytest.raises(asyncpg.CheckViolationError, match="undo_window_closed"):
        await _decide(
            seed, tenant, suggestion, hannah, by, "undone", late, "2026-09-14T09:41:11-05:00"
        )


async def test_decisions_are_human_only_and_insert_only(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant, suggestion, hannah, by = await _setup(seed)
    with pytest.raises(asyncpg.CheckViolationError):
        await _decide(seed, tenant, suggestion, ("agent", "agent:probe"), by, "adopted", None, T0)
    await _decide(seed, tenant, suggestion, hannah, by, "adopted", None, T0)
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("UPDATE suggestion_decisions SET decision = 'dismissed'")
    with pytest.raises(asyncpg.InsufficientPrivilegeError):
        await seed.run("DELETE FROM suggestion_decisions")
