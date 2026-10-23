"""Q-02-T20 against Postgres (migration 0105; AC-23, AC-25): reading client content writes one
identifier-only row per subject, tenant B never reads tenant A's rows, no role updates or deletes
one, and partitions are created ahead of time through the reviewed definer. Writes run as the app
role."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from abacus.ai_gateway.context import ContextBuilder
from abacus.kernel.access import (
    AccessSubject,
    UnknownAccessKind,
    ensure_partitions,
    record_reads,
    register_access_kind,
)
from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

KIND = "probe_content.read"
register_access_kind(KIND, ["restricted"])


@pytest.fixture(autouse=True)
async def engines(migrated_db: MigratedDatabase) -> AsyncIterator[None]:
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()
    settings.cache_clear()


@pytest.fixture
def seed(migrated_db: MigratedDatabase) -> Seeder:
    return Seeder(migrated_db.superuser_dsn)


def _person(tenant: uuid.UUID) -> TenantContext:
    return TenantContext(tenant, "human", str(uuid.uuid4()))


async def test_ac23_one_identifier_only_row_per_subject(seed: Seeder) -> None:
    tenant = await seed.firm()
    ctx = _person(tenant)
    engagement, client = uuid.uuid4(), uuid.uuid4()
    versions = [uuid.uuid4(), uuid.uuid4()]
    written = await record_reads(
        ctx,
        KIND,
        [AccessSubject("evidence_version", v, client, engagement) for v in versions],
        flags=["pii_tin"],
    )
    assert written == 2
    rows = await seed.rows(
        "SELECT actor_kind, actor_id, kind, subject_type, subject_id, client_id, engagement_id, "
        "flags FROM access_events WHERE tenant_id = $1 ORDER BY id",
        tenant,
    )
    assert [r["subject_id"] for r in rows] == versions
    assert {(r["actor_kind"], str(r["actor_id"]), r["kind"]) for r in rows} == {
        ("human", ctx.actor_id, KIND)
    }
    assert {(r["client_id"], r["engagement_id"]) for r in rows} == {(client, engagement)}
    assert all(sorted(r["flags"]) == ["pii_tin", "restricted"] for r in rows)


async def test_ac23_an_unregistered_kind_or_flag_is_refused(seed: Seeder) -> None:
    ctx = _person(await seed.firm())
    subject = [AccessSubject("evidence_version", uuid.uuid4())]
    with pytest.raises(UnknownAccessKind):
        await record_reads(ctx, "nobody.registered", subject)
    with pytest.raises(ValueError, match="flags"):
        await record_reads(ctx, KIND, subject, flags=["ssn"])


async def test_ac25_tenant_b_never_reads_tenant_a_and_no_row_changes(seed: Seeder) -> None:
    a, b = await seed.firm(), await seed.firm()
    await record_reads(_person(a), KIND, [AccessSubject("evidence_version", uuid.uuid4())])
    async with tenant_session(TenantContext(b, "human", str(uuid.uuid4()))) as session:
        seen = (await session.execute(text("SELECT count(*) FROM access_events"))).scalar()
    assert seen == 0
    for statement in ("UPDATE access_events SET kind = 'x.y'", "DELETE FROM access_events"):
        with pytest.raises(DBAPIError, match="permission denied"):
            async with tenant_session(_person(a)) as session:
                await session.execute(text(statement))
    with pytest.raises(Exception, match="insert-only"):  # the trigger, for any role
        await seed.run("UPDATE access_events SET kind = 'x.y' WHERE tenant_id = $1", a)


async def test_q02t20_partitions_are_made_ahead_and_a_late_month_lands_in_default(
    seed: Seeder,
) -> None:
    names = await ensure_partitions(date(2027, 11, 15), months_ahead=2)
    assert names == ["access_events_2027_11", "access_events_2027_12", "access_events_2028_01"]
    assert await ensure_partitions(date(2027, 11, 1), months_ahead=0) == ["access_events_2027_11"]
    tenant = await seed.firm()
    await seed.run(
        "INSERT INTO access_events (tenant_id, occurred_at, actor_kind, kind, subject_type, "
        "subject_id) VALUES ($1, '2031-05-01', 'system', 'probe_content.read', 'probe', $2)",
        tenant,
        uuid.uuid4(),
    )
    where = await seed.value(
        "SELECT tableoid::regclass::text FROM access_events WHERE tenant_id = $1", tenant
    )
    assert where == "access_events_default"


async def test_q02t20_a_model_context_names_its_evidence_sources() -> None:
    first, second = uuid.uuid4(), uuid.uuid4()
    built = ContextBuilder().sources(first).sources(second, first).build()
    assert built.sources == (first, second)


async def test_q02t20_the_gateway_kind_is_registered() -> None:
    import abacus.ai_gateway as gateway

    assert gateway.call  # importing the gateway registers model_context.built

    ctx = TenantContext(uuid.uuid4(), "agent", "agent:probe")
    # Registered: refused only for having no subjects, never as unknown.
    assert await record_reads(ctx, "model_context.built", []) == 0
    with pytest.raises(UnknownAccessKind):
        await record_reads(ctx, "model_context.unknown", [])
