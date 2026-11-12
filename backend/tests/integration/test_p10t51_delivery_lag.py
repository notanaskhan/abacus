"""P-10-T51 (TASK-7422; DEC-4412): the stream's read carries each row's age on the database
clock (`lag_ms`), which the API logs as `realtime.delivered` and the SLO-06 alarm reads."""

from __future__ import annotations

import uuid

import pytest

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import OutboxEvent
from abacus.modules.notifications import realtime as live
from abacus.modules.notifications.realtime import on_outbox_event

from .conftest import MigratedDatabase
from .test_t01t25_engine_export import engines as engines  # the autouse fixture
from .test_t01t25_engine_export import feld_return

pytestmark = pytest.mark.asyncio


async def test_a_tail_read_carries_each_rows_age_in_milliseconds(
    migrated_db: MigratedDatabase,
) -> None:
    feld = await feld_return(migrated_db)
    topic = f"engagement:{feld.engagement}"
    await on_outbox_event(
        OutboxEvent(
            uuid.uuid4(),
            feld.tenant,
            "issue.status_changed",
            {
                "issue_id": str(uuid.uuid4()),
                "engagement_id": str(feld.engagement),
                "status": "open",
            },
        )
    )
    system = TenantContext(feld.tenant, "system", "test:p10t51")
    read = live._AFTER  # pyright: ignore[reportPrivateUsage]  # the stream's own read
    async with tenant_session(system) as session:
        rows = (await session.execute(read, {"topics": [topic], "after": 0, "limit": 10})).all()
    assert rows, "the invalidation wrote a realtime_events row"
    lag = rows[-1].lag_ms
    assert isinstance(lag, int) and 0 <= lag < 60_000
