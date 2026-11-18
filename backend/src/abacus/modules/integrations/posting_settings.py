"""An engagement's W1 posting switch, read for its consumers (C-02-T12; DEC-5621): whether any
of the engagement's connections has `posting_enabled` on (0951 `connection_engagement_settings`,
owned here). Unknown or absent reads off (fail closed)."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session


async def posting_enabled_for(tenant: TenantContext, engagement_id: UUID) -> bool:
    async with tenant_session(tenant) as session:
        found = (
            await session.execute(
                text(
                    "SELECT 1 FROM connection_engagement_settings "
                    "WHERE engagement_id = :e AND posting_enabled LIMIT 1"
                ),
                {"e": engagement_id},
            )
        ).first()
    return found is not None
