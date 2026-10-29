# ac-test-author: ayushkbhatia
"""Q-04-T013 (TASK-1734; ADR-078 independent; Q-04-T006, DEC-715): the audit-trail metric reads,
c06, from the plan and the contract, not Q-04-T006's tests.

Acceptance (the task row): "Tests prove the allowlist, tenant isolation of the reads and a failing
go-live item for each chapter 06 section 8.3 category." This file: the allowlist and tenant
isolation; the go-live categories are `tests/unit/tools/test_q04t013_go_live_independent.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest

from abacus.kernel.config import settings
from abacus.kernel.db import (
    TenantContext,
    configure_engine,
    configure_relay_engine,
    dispose_engine,
)
from abacus.kernel.uow import Target, uow
from abacus.modules.audit_trail.api import (
    METRIC_ACTIONS,
    MetricActionRefused,
    Window,
    event_counts,
    first_to_last_durations,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase

# Actions the metric reads must never open, though the audit log holds them.
FORBIDDEN = (
    "sign_off.recorded",
    "evidence_version.read",
    "tin.revealed",
    "signer.ip_revealed",
    "access.changed",
    "",
    "request_item.%",
)


@pytest.fixture(autouse=True)
async def engines(
    migrated_db: MigratedDatabase, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[None]:
    monkeypatch.setenv("ABACUS_IDENTITY_DATABASE_URL", migrated_db.identity_url)
    settings.cache_clear()
    await dispose_engine()
    configure_engine(migrated_db.app_url)
    configure_relay_engine(migrated_db.relay_url)
    yield
    await dispose_engine()
    settings.cache_clear()


def _window() -> Window:
    now = datetime.now(UTC)
    return Window(now - timedelta(hours=1), now + timedelta(hours=1))


async def _event(tenant: TenantContext, action: str, target: uuid.UUID) -> None:
    async with uow(tenant) as tx:
        tx.record(action, target=Target("request_item", target))


@pytest.mark.parametrize("action", FORBIDDEN)
async def test_ac_an_action_off_the_allowlist_is_refused(
    migrated_db: MigratedDatabase, action: str
) -> None:
    tenant = TenantContext(await Seeder(migrated_db.superuser_dsn).firm(), "system", "q04t013")
    assert action not in METRIC_ACTIONS
    with pytest.raises(MetricActionRefused):
        await event_counts(tenant, ["request_item.sent", action], _window())
    with pytest.raises(MetricActionRefused):
        await first_to_last_durations(tenant, "request_item.sent", action, _window())


async def test_ac_each_firm_reads_only_its_own_events(migrated_db: MigratedDatabase) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    a = TenantContext(await seed.firm(), "system", "q04t013")
    b = TenantContext(await seed.firm(), "system", "q04t013")
    shared = uuid.uuid4()  # the same target id in both firms
    for _ in range(3):
        await _event(a, "request_item.sent", shared)
    await _event(a, "request_item.uploaded", shared)
    await _event(b, "request_item.sent", shared)
    actions = ["request_item.sent", "request_item.uploaded"]
    assert (await event_counts(a, actions, _window())).get("request_item.sent") == 3
    counted_b = await event_counts(b, actions, _window())
    assert counted_b.get("request_item.sent") == 1
    assert counted_b.get("request_item.uploaded", 0) == 0
    assert (
        await first_to_last_durations(b, "request_item.sent", "request_item.uploaded", _window())
        == []
    )
    durations = await first_to_last_durations(
        a, "request_item.sent", "request_item.uploaded", _window()
    )
    assert [d.target_id for d in durations] == [str(shared)]


async def test_reads_return_identifiers_counts_and_durations_only(
    migrated_db: MigratedDatabase,
) -> None:
    tenant = TenantContext(await Seeder(migrated_db.superuser_dsn).firm(), "system", "q04t013")
    target = uuid.uuid4()
    await _event(tenant, "request_item.sent", target)
    await _event(tenant, "request_item.uploaded", target)
    durations = await first_to_last_durations(
        tenant, "request_item.sent", "request_item.uploaded", _window()
    )
    assert set(vars(durations[0])) == {"target_type", "target_id", "seconds"}
    assert durations[0].seconds >= 0
