"""The synthetic firm's close states (C-01-T44; TASK-8700; DEC-5700).

CLS-01's August portfolio reads 3 Not started, 11 In progress, 5 In review and 3 Delivered at E0.
A real close reaches In review only with every plan account reconciled and Delivered only through
C-02's guarded release; the Brightwater Hale seed has neither the runs nor the deliveries for the
twenty-one closes beside Copperleaf's, so their status is set here, once, on the synthetic firm
only. Every other firm answers 404, and a close already moved is left as it is (False).
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid, NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.closes.events import CloseStatusChanged
from abacus.modules.identity.api import is_synthetic_firm

SEEDABLE: Final = frozenset({"in_progress", "in_review", "approved", "delivered"})

_SET = text(
    "UPDATE closes SET status = :status, row_version = row_version + 1 "
    "WHERE work_item_id = :id AND status = 'not_started' RETURNING work_item_id"
)


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "scenario:cas")


async def seed_synthetic_close_status(tenant_id: UUID, close_id: UUID, status: str) -> bool:
    """Not started → `status` on the synthetic firm's close; False when it has moved already."""
    if status not in SEEDABLE:
        raise DomainInvalid("close_status", facts={"status": status})
    tenant = _system(tenant_id)
    if not await is_synthetic_firm(tenant):
        raise NotFound("close")
    async with uow(tenant) as tx:
        if await tx.session.scalar(_SET, {"id": close_id, "status": status}) is None:
            return False
        tx.record("close.status_changed", target=Target("close", close_id))
        tx.emit(CloseStatusChanged(close_id=close_id, from_status="not_started", to_status=status))
    return True


__all__ = ["SEEDABLE", "seed_synthetic_close_status"]
