"""Which engagement or client owns the rows an audit event can point at (SPEC-304; DEC-121;
DEC-2264). A notice is on its engagement. An intake is on its client once matched; until then it
has no owner and its events stay hidden from the explorer (fail closed)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

ENGAGEMENT_KINDS: Final = frozenset({"notice"})
CLIENT_KINDS: Final = frozenset({"notice_intake"})


async def notice_engagements(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text("SELECT work_item_id, engagement_id FROM notices WHERE work_item_id = ANY(:ids)"),
            {"ids": list(ids)},
        )
        return {found: owned for found, owned in rows}


async def intake_clients(
    tenant: TenantContext, kind: str, ids: Sequence[UUID]
) -> dict[UUID, UUID]:
    del kind
    async with tenant_session(tenant) as session:
        rows = await session.execute(
            text(
                "SELECT id, client_id FROM notice_intakes "
                "WHERE id = ANY(:ids) AND client_id IS NOT NULL"
            ),
            {"ids": list(ids)},
        )
        return {found: owned for found, owned in rows}
