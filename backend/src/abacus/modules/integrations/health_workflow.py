"""`IntegrationHealthWorkflow` (W-01-T13 rest; W-01 §3 F4; SPEC-659 AC-27, AC-28; DEC-5333; red).

A platform Schedule every 15 minutes over every firm's connected and needs-attention firm
installs. Each install's Connect port answers `check_health` (read only, its own declared host);
a transient answer is retried in the same tick up to `FAILURES_TO_ATTENTION` times, so "three
server errors or timeouts in a row" needs no stored count. The outcome goes through `apply_probe`
(the rule, one unit of work only when something changes, the outbox event the firm admins'
`connection_needs_reauth` notification follows). No install whose port is not registered here is
probed (fail-closed); one firm's or install's failure never stops the rest.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final, cast
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel.clock import system_now
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.dispatch import PlatformSchedule
    from abacus.kernel.logging import get_logger
    from abacus.modules.integrations.health import FAILURES_TO_ATTENTION, Probe, apply_probe

_log = get_logger(__name__)
SWEEP_ID: Final = "integration_health:platform"
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


@activity.defn(name="integrations.health_sweep")
async def health_sweep_activity() -> int:
    from abacus.modules.identity.api import firm_tenant_ids

    probed = 0
    for tenant_id in await firm_tenant_ids():
        try:
            probed += await probe_tenant(tenant_id)
        except Exception as exc:  # one firm's failure is logged; the sweep goes on
            _log.error(
                "integration.health_sweep_failed",
                tenant_id=str(tenant_id),
                error=type(exc).__name__,
            )
    return probed


@workflow.defn(name="IntegrationHealthWorkflow")
class IntegrationHealthWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "integrations.health_sweep",
            result_type=int,
            start_to_close_timeout=timedelta(minutes=14),
            retry_policy=RetryPolicy(maximum_attempts=1),  # the next tick is the retry
        )


WORKFLOWS: Final[dict[type, str]] = {IntegrationHealthWorkflow: "batch"}
ACTIVITIES: Final[tuple[object, ...]] = (health_sweep_activity,)
SCHEDULES: Final[tuple[PlatformSchedule, ...]] = (
    PlatformSchedule(
        id=SWEEP_ID,
        workflow=IntegrationHealthWorkflow,
        every=timedelta(minutes=15),
        note="W-01-T13: probe every live firm token install; a refused token is Needs reauth",
    ),
)
