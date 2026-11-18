"""One firm's integration health probe (W-01-T13 rest; SPEC-659 AC-27 to AC-30): the activity
code `IntegrationHealthWorkflow`'s sweep runs per firm. It lives apart from the workflow module
so the workflow file never imports the clock (F-04.6): the probe's time is the system's, taken
here, outside workflow code."""

from __future__ import annotations

from typing import Final, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import system_now
from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.integrations.health import FAILURES_TO_ATTENTION, Probe, apply_probe

_ACTOR: Final = "integration-health:sweep"
_PROBE_OF: Final[dict[str, Probe]] = {
    "ok": "ok",
    "transient": "server_error",
    "unauthorised": "unauthorized",
    "invalid_grant": "unauthorized",
    "token_expired": "unauthorized",
}
_LIVE: Final = text(
    "SELECT id, catalog_key, mode FROM firm_integrations "
    "WHERE status IN ('connected', 'needs_attention') AND mode = 'token' ORDER BY id"
)


async def probe_tenant(tenant_id: UUID) -> int:
    """Every live token install of one firm; returns how many were probed."""
    from abacus.kernel._flags import INTEGRATIONS_HEALTH_MONITOR
    from abacus.kernel.flags import flag_enabled
    from abacus.modules.identity.api import is_synthetic_firm
    from abacus.modules.integrations.connect_ports import port_for
    from abacus.modules.integrations.secrets import open_secret

    tenant = TenantContext(tenant_id, "system", _ACTOR)
    # SPEC-659 AC-30: the monitor is silent for a firm with `integrations.health_monitor` off.
    if not await flag_enabled(tenant, INTEGRATIONS_HEALTH_MONITOR, fresh=True):
        return 0
    synthetic = await is_synthetic_firm(tenant)
    async with tenant_session(tenant) as session:
        installs = (await session.execute(_LIVE)).all()
    probed = 0
    from abacus.modules.integrations.kill_switch import paused_keys

    paused = await paused_keys(tenant_id, {str(k) for _, k, _ in installs})
    for install_id, key, mode in installs:
        if str(key) in paused:  # W-01-T07 rest (DEC-5433): no adapter call while paused
            continue
        port = port_for(str(key), cast("object", mode), synthetic=synthetic)  # type: ignore[arg-type] -- the stored mode code
        if port is None:
            continue
        secret = await open_secret(tenant, cast(UUID, install_id))
        failures = 0
        probe: Probe = "ok"
        for _ in range(FAILURES_TO_ATTENTION):
            probe = _PROBE_OF.get(str(await port.check_health(secret)), "server_error")
            if probe != "server_error":
                break
            failures += 1
        await apply_probe(
            tenant,
            cast(UUID, install_id),
            probe,
            failures=max(failures - 1, 0) if probe == "server_error" else 0,
            at=system_now(),
        )
        probed += 1
    return probed
