"""Q-02-T20, T21 code gaps (TASK-919, TASK-920): the Schedules' activities against Postgres.

- `audit_trail.ensure_partitions` creates this month's and the next two months' partitions.
- `audit_trail.seal_checkpoints` seals each firm's settled events (the settle window is shortened
  here) and seals nothing more on a second pass.
- `audit_trail.verify_chains` passes on an unaltered chain and, once one audit row is altered,
  fails as a non-retryable `AuditChainMismatch` naming the firm and the checkpoint; a firm that
  cannot be read does not stop the others, and fails the run as `AuditChainVerifyFailed`.
- `evidence.anchor_chains` anchors each firm, and one firm's failure does not stop the others.

Each activity is called directly with the firm list narrowed to this test's firms, since the
session's database holds other tests' firms (some with chains altered on purpose).
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import datetime
from functools import partial

import pytest
from temporalio.exceptions import ApplicationError

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine
from abacus.kernel.uow import Target, uow
from abacus.kernel.uow.chain import seal_checkpoint
from abacus.modules.audit_trail import jobs
from abacus.modules.evidence import anchor_job

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


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


def _only(monkeypatch: pytest.MonkeyPatch, module: object, *firms: uuid.UUID) -> None:
    async def firm_tenant_ids() -> list[uuid.UUID]:
        return list(firms)

    monkeypatch.setattr(module, "firm_tenant_ids", firm_tenant_ids)


async def _events(tenant: uuid.UUID, n: int) -> None:
    for _ in range(n):
        async with uow(TenantContext(tenant, "system", "probe")) as tx:
            tx.record("probe.recorded", target=Target("probe", uuid.uuid4()))


async def test_the_partition_job_ensures_three_months(seed: Seeder) -> None:
    assert await jobs.ensure_partitions_activity() == 3
    assert await jobs.ensure_partitions_activity() == 3  # repeat-safe


async def test_the_checkpoint_and_verify_jobs_seal_verify_and_report_a_tampered_row(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    tenant = await seed.firm()
    _only(monkeypatch, jobs, tenant)
    monkeypatch.setattr(jobs, "seal_checkpoint", partial(seal_checkpoint, settle_seconds=0))
    await _events(tenant, 4)
    assert await jobs.seal_checkpoints_activity() == 1
    assert await jobs.seal_checkpoints_activity() == 0  # nothing new
    assert await jobs.verify_chains_activity() == 1

    await seed.run("ALTER TABLE audit_events DISABLE TRIGGER USER")
    try:
        await seed.as_actor(
            tenant,
            ("system", "probe"),
            "UPDATE audit_events SET target_type = 'altered' WHERE seq = "
            "(SELECT min(seq) FROM audit_events WHERE tenant_id = $1)",
            tenant,
        )
    finally:
        await seed.run("ALTER TABLE audit_events ENABLE TRIGGER USER")
    with pytest.raises(ApplicationError) as failed:
        await jobs.verify_chains_activity()
    assert failed.value.type == "AuditChainMismatch"
    assert failed.value.non_retryable
    assert failed.value.details == ({str(tenant): [1]},)


async def test_the_verify_job_checks_every_firm_when_one_cannot_be_read(
    seed: Seeder, monkeypatch: pytest.MonkeyPatch
) -> None:
    good, broken = await seed.firm(), uuid.uuid4()
    _only(monkeypatch, jobs, broken, good)
    seen: list[uuid.UUID] = []
    real = jobs.verify_chain

    async def verify_chain(tenant: uuid.UUID) -> list[int]:
        if tenant == broken:
            raise RuntimeError("connection reset")
        seen.append(tenant)
        return await real(tenant)

    monkeypatch.setattr(jobs, "verify_chain", verify_chain)
    with pytest.raises(ApplicationError) as failed:
        await jobs.verify_chains_activity()
    assert seen == [good]  # the firm after the broken one was still verified
    assert failed.value.type == "AuditChainVerifyFailed"
    assert not failed.value.non_retryable
    assert failed.value.details == ([str(broken)],)


async def test_the_anchor_job_anchors_each_firm_and_survives_one_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    good, bad = uuid.uuid4(), uuid.uuid4()
    _only(monkeypatch, anchor_job, bad, good)
    seen: list[tuple[uuid.UUID, datetime]] = []

    async def anchor_chain(tenant: uuid.UUID, retain_until: datetime) -> object:
        if tenant == bad:
            raise RuntimeError("records bucket unavailable")
        seen.append((tenant, retain_until))
        return object()

    monkeypatch.setattr(anchor_job, "anchor_chain", anchor_chain)
    assert await anchor_job.anchor_chains_activity() == 1
    assert [t for t, _ in seen] == [good]
    assert (seen[0][1] - datetime.now(seen[0][1].tzinfo)).days >= 7 * 365
