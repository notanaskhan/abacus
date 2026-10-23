"""P-04-T14 against Postgres: the computed staleness query (ADR-160; DEC-215).

"A sign-off reads stale exactly when the target hash differs." No sign-off row is ever updated:
staleness is each target's newest sign-off per level compared with the target's current hash.
Sign-offs are seeded as the superuser under a person's actor, as the human-only CHECK requires.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest

from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.modules.review.api import content_hash, stale_of, states_of
from abacus.modules.review.repository import sign_offs_of

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

pytestmark = pytest.mark.asyncio
SIGN = (
    "INSERT INTO sign_offs (tenant_id, engagement_id, target_type, target_id, level, "
    "content_hash, signed_by, created_at) "
    "VALUES ($1, $2, 'workpaper', $3, $4, $5, $6, $7::text::timestamptz)"
)
V1 = content_hash({"cells": {"C14": {"raw": "2190", "tickmarks": []}}, "citations": []})
V2 = content_hash({"cells": {"C14": {"raw": "2310", "tickmarks": []}}, "citations": []})


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


async def test_a_sign_off_reads_stale_exactly_when_the_target_hash_differs(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    tenant = await seed.firm()
    kevin = await seed.person(tenant)
    samuel = await seed.person(tenant)
    engagement = await seed.engagement(tenant, await seed.entity(tenant), kevin.user_id)
    paper, untouched = uuid.uuid4(), uuid.uuid4()

    async def sign(who: uuid.UUID, target: uuid.UUID, level: int, digest: str, at: str) -> None:
        await seed.as_actor(
            tenant, ("human", str(who)), SIGN, tenant, engagement, target, level, digest, who, at
        )

    await sign(kevin.user_id, paper, 1, V1, "2026-09-08T10:00:00Z")
    await sign(samuel.user_id, paper, 2, V1, "2026-09-11T10:00:00Z")
    await sign(kevin.user_id, paper, 1, V2, "2026-09-12T10:00:00Z")  # re-signed after the change
    await sign(kevin.user_id, untouched, 1, V1, "2026-09-08T11:00:00Z")
    me = TenantContext(tenant, "human", str(kevin.user_id))

    on_v2 = await stale_of(me, "workpaper", {paper: V2, untouched: V1})
    assert [(s.target_id, s.level, s.signed_by, s.signed_hash) for s in on_v2] == [
        (paper, 2, samuel.user_id, V1)
    ]
    assert on_v2[0].current_hash == V2

    on_v1 = await stale_of(me, "workpaper", {paper: V1})
    assert [(s.level, s.signed_hash) for s in on_v1] == [(1, V2)]

    assert await stale_of(me, "workpaper", {uuid.uuid4(): V1}) == []
    assert await stale_of(me, "workpaper", {}) == []
    assert await stale_of(me, "trial_balance", {paper: V2}) == []  # another type's targets

    # The ladder read agrees with the query, level by level.
    async with tenant_session(me) as session:
        rows = await sign_offs_of(session, "workpaper", [paper])
    for current, stale in ((V2, {2}), (V1, {1})):
        ladder = states_of([r for r in rows if r.target_id == paper], current)
        assert {s.level for s in ladder if s.stale} == stale
        assert {s.level for s in await stale_of(me, "workpaper", {paper: current})} == stale
    assert await seed.value("SELECT count(*) FROM sign_offs WHERE tenant_id = $1", tenant) == 4
