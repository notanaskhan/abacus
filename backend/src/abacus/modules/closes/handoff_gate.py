"""T-06-T20 (DEC-5631): C12's `close_lock` hand-off gate, owned by closes. A CAS close is a
hand-off source only once it is Locked (the December close's final state); any other state, or
an unknown close, refuses (fail closed)."""

from __future__ import annotations

from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.closes.repository import close_row
from abacus.modules.ledger.api import tb_handoff


async def close_locked(tenant: TenantContext, close_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        row = await close_row(session, close_id)
    return row is not None and row.status == "locked"


def register() -> None:
    tb_handoff.register_handoff_gate("close_lock", close_locked)
