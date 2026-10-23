"""P-04-T15 against Postgres: a preparer never signs L2 or L3 on their own target (R-SO-3,
`not_preparer_of_target`), through `review.api.record_sign_off` with the target's facts; another
reviewer may. The matrix denies, and the service answers 409 `preparer_cannot_review`."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import uow
from abacus.modules.identity.api import AuthContext, engagement_resource
from abacus.modules.review.api import PreparerCannotReview, content_hash, record_sign_off

from .agent_tests.support import Person, Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
DIGEST = content_hash({"cells": {"C14": {"raw": "2310", "tickmarks": []}}, "citations": []})


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


def _ctx(who: Person) -> AuthContext:
    return AuthContext(
        TenantContext(who.tenant_id, "human", str(who.user_id)),
        who.user_id,
        uuid.uuid4(),
        None,
        datetime.now(UTC),
    )


async def test_rso3_the_preparer_is_refused_l2_and_l3_and_another_reviewer_signs(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    marcus = await seed.person(tenant)
    hannah = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), marcus.user_id)
    await seed.member(engagement, marcus, "manager")
    await seed.member(engagement, hannah, "engagement_partner")
    target = uuid.uuid4()

    async def sign(who: Person, level: int) -> None:
        ctx = _ctx(who)
        resource = await engagement_resource(ctx.tenant, engagement)
        async with uow(ctx.tenant) as tx:
            await record_sign_off(
                tx, ctx, resource, engagement, "probe_paper", target, level, DIGEST
            )

    await sign(marcus, 1)
    for level in (2, 3):
        with pytest.raises(PreparerCannotReview):
            await sign(marcus, level)
    await sign(hannah, 2)
    await sign(hannah, 3)
    rows = await seed.rows(
        "SELECT level, signed_by FROM sign_offs WHERE target_id = $1 ORDER BY level", target
    )
    assert [(r["level"], r["signed_by"]) for r in rows] == [
        (1, marcus.user_id),
        (2, hannah.user_id),
        (3, hannah.user_id),
    ]
