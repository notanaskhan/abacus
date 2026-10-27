"""Q-04-T006 (TASK-1620; DEC-715): the pilot metric reads over the audit trail.

"Both reads return counts and durations only, refuse an action outside the allowlist and see one
tenant's rows under forced RLS" (Q-04-T006 acceptance).
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
    MetricActionRefused,
    Window,
    event_counts,
    first_to_last_durations,
)

from .agent_tests.support import Seeder
from .conftest import MigratedDatabase


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


async def _record(tenant: TenantContext, action: str, target: uuid.UUID) -> None:
    async with uow(tenant) as tx:
        tx.record(action, target=Target("request_item", target))


def _window() -> Window:
    now = datetime.now(UTC)
    return Window(now - timedelta(hours=1), now + timedelta(hours=1))


async def test_ac_counts_and_durations_only_for_the_firms_own_rows(
    migrated_db: MigratedDatabase,
) -> None:
    seed = Seeder(migrated_db.superuser_dsn)
    ours, theirs = await seed.firm(), await seed.firm()
    mine = TenantContext(ours, "system", "q04t006")
    other = TenantContext(theirs, "system", "q04t006")
    item = uuid.uuid4()
    await _record(mine, "request_item.sent", item)
    await _record(mine, "request_item.uploaded", item)
    await _record(mine, "request_item.uploaded", item)
    await _record(other, "request_item.sent", uuid.uuid4())

    counts = await event_counts(mine, ["request_item.sent", "request_item.uploaded"], _window())
    assert counts == {"request_item.sent": 1, "request_item.uploaded": 2}
    durations = await first_to_last_durations(
        mine, "request_item.sent", "request_item.uploaded", _window()
    )
    assert [(d.target_type, d.target_id) for d in durations] == [("request_item", str(item))]
    assert durations[0].seconds >= 0
    assert (await event_counts(other, ["request_item.uploaded"], _window())) == {
        "request_item.uploaded": 0
    }


async def test_ac_an_action_outside_the_allowlist_is_refused(
    migrated_db: MigratedDatabase,
) -> None:
    tenant = TenantContext(uuid.uuid4(), "system", "q04t006")
    with pytest.raises(MetricActionRefused):
        await event_counts(tenant, ["tin.revealed"], _window())
    with pytest.raises(MetricActionRefused):
        await first_to_last_durations(tenant, "request_item.sent", "pii.revealed", _window())
