"""G-04-T10 (AC-54; DEC-5417): the firm's installed integrations for SHL-05's status, from W-01's
own install health. An install the health monitor moved to Needs reauth, Needs attention or
Paused reads `needs_attention`; a connected one `operational`. Keys only, never a detail."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.integrations.connect_catalog import firm_installs

_ATTENTION: Final = frozenset({"needs_attention", "needs_reauth", "paused"})


async def firm_health(tenant: TenantContext) -> Mapping[str, str]:
    async with tenant_session(tenant) as session:
        installs = await firm_installs(session)
    return {
        key: "needs_attention" if install.status in _ATTENTION else "operational"
        for key, install in installs.items()
    }


def register() -> None:
    from abacus.modules.platform.api import register_firm_health

    register_firm_health(firm_health)
