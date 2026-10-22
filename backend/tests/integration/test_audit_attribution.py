"""Q-02-T16 against Postgres (migration 0096): "Every new agent audit row names the person it
acted for, a policy row without policy_ref is refused." The unit of work writes the scope and the
person an agent or the platform acts for."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from abacus.kernel.db import TenantContext, configure_engine
from abacus.kernel.uow import Scope, Target, uow

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
AUDIT = (
    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, target_id, "
    "on_behalf_of_user_id, policy_ref) VALUES ($1, $2, $3, 'probe.recorded', 'probe', $4, $5, $6)"
)


async def test_an_agent_row_without_its_person_is_refused(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    agent = ("agent", "agent:probe:run")
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.as_actor(tenant, agent, AUDIT, tenant, *agent, str(uuid.uuid4()), None, None)
    await seed.as_actor(
        tenant, agent, AUDIT, tenant, *agent, str(uuid.uuid4()), uuid.uuid4(), None
    )


async def test_a_policy_row_needs_its_policy(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    policy = ("policy", "policy:probe")
    with pytest.raises(asyncpg.CheckViolationError):
        await seed.as_actor(tenant, policy, AUDIT, tenant, *policy, str(uuid.uuid4()), None, None)
    await seed.as_actor(
        tenant, policy, AUDIT, tenant, *policy, str(uuid.uuid4()), None, "policy:thresholds:v1"
    )


async def test_the_unit_of_work_writes_scope_and_person(migrated_db: MigratedDatabase) -> None:
    configure_engine(migrated_db.app_url)
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    person, engagement, work_item = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    ctx = TenantContext(tenant, "agent", "agent:probe:run", person)
    async with uow(ctx) as tx:
        tx.record(
            "probe.recorded",
            target=Target("probe", uuid.uuid4()),
            scope=Scope(engagement_id=engagement, work_item_id=work_item),
        )
    rows = await seed.rows(
        "SELECT engagement_id, work_item_id, on_behalf_of_user_id FROM audit_events "
        "WHERE tenant_id = $1 AND action = 'probe.recorded'",
        tenant,
    )
    assert [tuple(r) for r in rows] == [(engagement, work_item, person)]
