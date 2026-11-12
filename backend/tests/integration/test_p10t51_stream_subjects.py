"""P-10-T51 (TASK-7428): the stream subjects load on the synthetic firm only, staffed on the
scenario's engagement with the local sign-in subjects, once."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest

from abacus_tools.fakes.identity import ISSUER
from abacus_tools.loadtest import stream_subjects as ss
from abacus_tools.quality.schema_check import Database, provisioned_database
from abacus_tools.synthetic.scenarios.brightwater_hale.loader import TENANT, LoadRefused

from .agent_tests.support import Seeder

pytestmark = pytest.mark.asyncio


@pytest.fixture(scope="module")
def fresh() -> Iterator[Database]:
    """Its own database: the synthetic firm's tenant id is fixed."""
    with provisioned_database(roundtrip=False) as database:
        yield database


async def _engagement(seed: Seeder, *, synthetic: bool) -> uuid.UUID:
    await seed.run(
        "INSERT INTO firms (tenant_id, name, synthetic) VALUES ($1, 'Brightwater Hale', $2) "
        "ON CONFLICT (tenant_id) DO UPDATE SET synthetic = $2",
        TENANT,
        synthetic,
    )
    owner = await seed.person(TENANT)
    entity = await seed.entity(TENANT)
    return await seed.engagement(TENANT, entity, owner.user_id)


async def test_the_subjects_load_once_staffed_on_the_engagement(fresh: Database) -> None:
    seed = Seeder(fresh.superuser_dsn)
    engagement = await _engagement(seed, synthetic=True)
    first = await ss.load(fresh.superuser_dsn, engagement, count=8)
    second = await ss.load(fresh.superuser_dsn, engagement, count=8)
    assert (first.written, first.skipped, second.written, second.skipped) == (8, 0, 0, 8)
    users = await seed.rows(
        "SELECT u.idp_issuer, u.idp_subject FROM users u JOIN engagement_members m "
        "ON m.user_id = u.id WHERE m.engagement_id = $1 AND u.idp_subject LIKE 'loadtest-%' "
        "ORDER BY u.idp_subject",
        engagement,
    )
    assert [(u["idp_issuer"], u["idp_subject"]) for u in users] == [
        (ISSUER, ss.subject(ss.PREFIX, k)) for k in range(8)
    ]
    audited = await seed.value(
        "SELECT count(*) FROM audit_events WHERE tenant_id = $1 AND actor_id = $2",
        TENANT,
        ss.LOADER,
    )
    assert audited == 8


async def test_a_firm_that_is_not_synthetic_is_refused(fresh: Database) -> None:
    seed = Seeder(fresh.superuser_dsn)
    engagement = await _engagement(seed, synthetic=False)
    with pytest.raises(LoadRefused, match="synthetic firm"):
        await ss.load(fresh.superuser_dsn, engagement, count=1)
    await _engagement(seed, synthetic=True)


async def test_an_engagement_of_another_firm_is_refused(fresh: Database) -> None:
    seed = Seeder(fresh.superuser_dsn)
    await _engagement(seed, synthetic=True)
    other = await seed.firm()
    owner = await seed.person(other)
    elsewhere = await seed.engagement(other, await seed.entity(other), owner.user_id)
    with pytest.raises(LoadRefused, match="not the synthetic firm"):
        await ss.load(fresh.superuser_dsn, elsewhere, count=1)
