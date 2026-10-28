"""The AI policy's effective version (G-02-T23; ADR-186; DEC-711). T24 adds the services and
routes; this is the read the identity slot needs.

The effective version is the newest `published` one whose `effective_from` has passed on the
firm's business clock. It governs a firm only with `ai_policy.v1` on; otherwise the firm's own
autonomy setting stands (the legacy route still writes it).
"""

from __future__ import annotations

import json
from typing import cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel import clock
from abacus.kernel._flags import AI_POLICY_V1
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.flags import flag_enabled

_EFFECTIVE = text(
    "SELECT sections FROM autonomy_policy_versions WHERE state = 'published' "
    "AND effective_from <= :now ORDER BY effective_from DESC, version_no DESC LIMIT 1"
)


async def effective_sections(tenant: TenantContext) -> dict[str, object] | None:
    now = await clock.now(tenant)
    async with tenant_session(tenant) as session:
        found = await session.scalar(_EFFECTIVE, {"now": now})
    if isinstance(found, str):  # a driver without a jsonb codec hands back text
        found = json.loads(found)
    return cast(dict[str, object], found) if isinstance(found, dict) else None


async def policy_autonomy_level(tenant_id: UUID) -> int | None:
    """The identity slot's provider: the effective policy's level, or None when it does not
    govern the firm."""
    tenant = TenantContext(tenant_id, "system", "agents:ai_policy")
    if not await flag_enabled(tenant, AI_POLICY_V1):
        return None
    sections = await effective_sections(tenant)
    if sections is None:
        return None
    level = cast(dict[str, object], sections.get("autonomy", {})).get("level")
    return level if isinstance(level, int) else None
