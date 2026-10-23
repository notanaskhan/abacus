"""Q-02-T17 against Postgres (migration 0097): "Inserting sign_off.recorded, report.released or
any listed action with actor_kind agent or policy raises at the database, and the generated list
matches the YAML." I-AGENT-NEVER at the data layer, independent of the permission matrix."""

from __future__ import annotations

import uuid

import asyncpg
import pytest

from abacus.kernel._human_only_actions import HUMAN_ONLY_ACTIONS
from abacus.kernel.db import TenantContext, configure_engine
from abacus.kernel.uow import Target, uow
from abacus_tools.codegen.human_only_actions import load

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
# The transaction acts for the row's person, as the unit of work sets it (0108, Q-02 AC-15).
AUDIT = (
    "WITH s AS (SELECT set_config('app.on_behalf_of', coalesce($6::uuid::text, ''), true) AS v) "
    "INSERT INTO audit_events (tenant_id, actor_kind, actor_id, action, target_type, target_id, "
    "on_behalf_of_user_id, policy_ref) "
    "SELECT $1::uuid, $2::text, $3::text, $4::text, 'probe', $5::text, $6::uuid, $7::text FROM s"
)


async def test_the_database_list_matches_the_yaml_and_the_generated_module(
    migrated_db: MigratedDatabase,
) -> None:
    found = await Seeder(migrated_db.superuser_dsn).value("SELECT abacus_human_only_actions()")
    assert sorted(found) == sorted(HUMAN_ONLY_ACTIONS) == list(load())  # type: ignore[arg-type]  # text[]


@pytest.mark.parametrize("action", sorted(HUMAN_ONLY_ACTIONS))
async def test_an_agent_or_policy_is_refused_every_listed_action(
    migrated_db: MigratedDatabase, action: str
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    person = uuid.uuid4()
    for actor, policy in ((("agent", "agent:probe:run"), None), (("policy", "policy:probe"), "p")):
        with pytest.raises(asyncpg.InsufficientPrivilegeError, match="human_only_action"):
            await seed.as_actor(
                tenant, actor, AUDIT, tenant, *actor, action, str(uuid.uuid4()), person, policy
            )
    human = ("human", str(person))
    await seed.as_actor(
        tenant, human, AUDIT, tenant, *human, action, str(uuid.uuid4()), None, None
    )


async def test_an_agent_may_still_write_its_own_actions(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    agent = ("agent", "agent:probe:run")
    await seed.as_actor(
        tenant,
        agent,
        AUDIT,
        tenant,
        *agent,
        "risk.recorded",
        str(uuid.uuid4()),
        uuid.uuid4(),
        None,
    )


async def test_the_app_role_writes_audit_rows_through_the_guard(
    migrated_db: MigratedDatabase,
) -> None:
    """The trigger runs as the inserting role: the app must be able to evaluate it (0098)."""
    configure_engine(migrated_db.app_url)
    tenant = await Seeder(migrated_db.superuser_dsn).firm()
    async with uow(TenantContext(tenant, "human", str(uuid.uuid4()))) as tx:
        tx.record("sign_off.recorded", target=Target("probe", uuid.uuid4()))
    agent = TenantContext(tenant, "agent", "agent:probe:run", uuid.uuid4())
    with pytest.raises(Exception, match="human_only_action"):
        async with uow(agent) as tx:
            tx.record("sign_off.recorded", target=Target("probe", uuid.uuid4()))
