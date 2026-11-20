"""Ephemeral writes (F-08-T13; TASK-8845; chapter 03 §7.1; ADR P-15; DEC-5844): the one documented
exception to "every state change goes through the unit of work and writes an audit event".

Presence heartbeats say who is looking at what for 45 seconds; auditing them would flood the trail
with no evidential value, and the outbox would replay stale "is here" facts. So a write to a table
listed in `EPHEMERAL_TABLES` (UNLOGGED, tenant-scoped, forced RLS) runs here: one statement on the
tenant's own connection, committed, never audited and never emitted. Any other table is refused,
so the exception cannot widen without a reviewed change to this list.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final

from sqlalchemy import text

from abacus.kernel.db import TenantContext
from abacus.kernel.db.session import tenant_connection

EPHEMERAL_TABLES: Final = frozenset({"presence_heartbeats"})
_TARGET: Final = re.compile(r"^\s*(?:INSERT\s+INTO|UPDATE|DELETE\s+FROM)\s+([a-z_]+)\b", re.I)


class NotEphemeral(ValueError):
    """The statement writes a table that is not ephemeral."""


async def ephemeral_write(
    ctx: TenantContext, statement: str, params: Mapping[str, object]
) -> None:
    found = _TARGET.match(statement)
    if found is None or found.group(1).lower() not in EPHEMERAL_TABLES:
        raise NotEphemeral(statement[:60])
    async with tenant_connection(ctx) as conn:
        await conn.execute(text(statement), dict(params))
        await conn.commit()


__all__ = ["EPHEMERAL_TABLES", "NotEphemeral", "ephemeral_write"]
