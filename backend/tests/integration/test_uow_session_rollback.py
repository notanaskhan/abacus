"""AC-4: a session rollback inside the unit of work never leaves a partial write.

Kept in its own file because `session.rollback()` is exactly what UOW-001 bans elsewhere.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated, ClassVar, Protocol

import pytest
from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext, configure_engine, dispose_engine, tenant_session
from abacus.kernel.uow import DomainEvent, Target, uow


class Migrated(Protocol):
    app_url: str


class RolledBack(DomainEvent):
    event_type: ClassVar[str] = "probe.rolled_back"
    probe_id: Annotated[uuid.UUID, classified("internal")]


@pytest.fixture(autouse=True)
async def engine_for_this_loop(migrated_db: Migrated) -> AsyncIterator[None]:
    configure_engine(migrated_db.app_url)
    yield
    await dispose_engine()


async def _counts(ctx: TenantContext) -> tuple[int, int]:
    async with tenant_session(ctx) as session:
        audit = (await session.execute(text("SELECT count(*) FROM audit_events"))).scalar_one()
        outbox = (await session.execute(text("SELECT count(*) FROM outbox"))).scalar_one()
    return audit, outbox


async def test_ac4_a_session_rollback_inside_the_block_never_leaves_a_partial_write() -> None:
    ctx = TenantContext(tenant_id=uuid.uuid4(), actor_kind="human", actor_id="u-1")
    completed = True
    try:
        async with uow(ctx) as tx:
            await tx.session.execute(text("SELECT 1"))
            await tx.session.rollback()
            tx.record("probe.created", target=Target("probe", "1"))
            tx.emit(RolledBack(probe_id=uuid.uuid4()))
    except Exception:  # either outcome is allowed; the state is asserted below
        completed = False
    # inert rollback: audit event and outbox row both committed; otherwise nothing at all
    assert await _counts(ctx) == ((1, 1) if completed else (0, 0))
