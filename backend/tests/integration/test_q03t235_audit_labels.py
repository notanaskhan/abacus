"""Q-03-T235 (TASK-6738; DEC-3304) on Postgres: the label index names an engagement and a client
by their owners' labelers, a working paper by its code and title, and a target type nobody names
by its noun; no row shows an identifier, and the explorer reads the same."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import cast

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.audit_trail.api import index_labels

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


async def test_ac_named_targets_read_by_name_and_the_rest_by_their_noun(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    user = (await seed.person(tenant)).user_id  # a member, as engagements.created_by needs
    entity = await seed.entity(tenant)
    engagement = await seed.engagement(tenant, entity, user)
    client = cast(
        uuid.UUID, await seed.value("SELECT client_id FROM engagements WHERE id = $1", engagement)
    )
    name = cast(str, await seed.value("SELECT name FROM engagements WHERE id = $1", engagement))
    ctx = TenantContext(tenant, "human", str(user))
    unnamed = uuid.uuid4()
    async with uow(ctx) as tx:
        scope = Scope(engagement_id=engagement)
        tx.record("engagement.updated", target=Target("engagement", engagement), scope=scope)
        tx.record("client.updated", target=Target("client", client), after=Ref(version=1))
        tx.record("eqr.concurred", target=Target("eqr_review", unnamed), scope=scope)
    await index_labels(tenant)
    rows = await seed.rows(
        "SELECT e.target_type, e.target_id, l.target_label FROM audit_event_labels l "
        "JOIN audit_events e ON e.tenant_id = l.tenant_id AND e.seq = l.seq "
        "WHERE l.tenant_id = $1 ORDER BY l.seq",
        tenant,
    )
    by_type = {str(r["target_type"]): str(r["target_label"]) for r in rows}
    assert by_type["engagement"] == name
    assert by_type["client"] == "Seeded client"
    assert by_type["eqr_review"] == "EQR review"
    for r in rows:
        assert str(r["target_id"]) not in str(r["target_label"])
