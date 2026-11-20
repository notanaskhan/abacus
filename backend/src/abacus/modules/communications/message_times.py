"""When a message was created (S52 end pass; C-02-T24): the closing-date conflict's "asked on"
reads the client mail's own time here instead of the audit trail (OWN-001)."""

from __future__ import annotations

from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


async def message_created_at(tenant: TenantContext, message_id: UUID) -> datetime | None:
    async with tenant_session(tenant) as session:
        found = await session.scalar(
            text("SELECT created_at FROM messages WHERE id = :m"), {"m": message_id}
        )
    return cast(datetime | None, found)
