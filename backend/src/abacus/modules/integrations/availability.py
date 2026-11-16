"""The availability fan-out (W-01-T07; SPEC-659 AC-33).

After a catalogue import makes keys available (newly published as available, or coming soon to
available), the operator's command calls `notify_available` for every firm. Inside that firm's
own unit of work (`integration_interest` forces row-level security, so no cross-firm read) the
rows of people who asked about those keys and have not been told are marked (`notified_at`) and
one `integration.available` event is emitted per person and key: a second run tells nobody twice.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import select, update

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.integrations.events import IntegrationAvailable
from abacus.modules.integrations.models import IntegrationInterest

ACTOR: Final = "integrations:availability"


async def notify_available(tenant_id: UUID, keys: Sequence[str]) -> int:
    """Mark and announce each person in the firm who asked about one of `keys` and has not been
    told; the number told."""
    if not keys:
        return 0
    tenant = TenantContext(tenant_id, "system", ACTOR)
    wanted = sorted(set(keys))
    async with tenant_session(tenant) as session:  # most firms asked about nothing: no write
        due = await session.scalar(
            select(IntegrationInterest.catalog_key)
            .where(
                IntegrationInterest.catalog_key.in_(wanted),
                IntegrationInterest.notified_at.is_(None),
            )
            .limit(1)
        )
    if due is None:
        return 0
    async with uow(tenant) as tx:
        marked = (
            await tx.session.execute(
                update(IntegrationInterest)
                .where(
                    IntegrationInterest.catalog_key.in_(wanted),
                    IntegrationInterest.notified_at.is_(None),
                )
                .values(notified_at=system_now())
                .returning(IntegrationInterest.user_id, IntegrationInterest.catalog_key)
            )
        ).all()
        for user_id, key in marked:
            tx.emit(IntegrationAvailable(user_id=user_id, catalog_key=key))
        tx.record(
            "integration.availability_notified",
            target=Target("firm", tenant_id),
            after=Ref(told=len(marked)),
        )
    return len(marked)
