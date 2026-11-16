"""Agent dependency on integrations (W-01-T14; W-01 §3 F5; WB-11; DEC-5320; red).

- **Admission** (`admission_failure`, pure): a capability that requires integrations is admitted
  only when each one is connected for the firm: `needs_reauth` fails the run at admission with
  `integration_reauth_required`, `needs_attention` with `integration_unhealthy`, anything else
  (not installed, paused, disconnected, connecting) with `integration_not_connected`. The first
  failing integration in the spec's order names the code.
- **The failed run's link** (`record_run_failed`): the admission failure writes one `run_failed`
  integration event naming the run, so the install's expiry event reads "1 scheduled run failed"
  (`failed_runs_since`).
- **Dependents** (`register_dependents_provider`): the agents module tells integrations which
  capabilities require a key (WB-11's "Agents using it"); integrations imports no agent code.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping, Sequence
from datetime import datetime
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.uow import Target, uow

Failure = Literal[
    "integration_reauth_required", "integration_unhealthy", "integration_not_connected"
]
DependentsProvider = Callable[[str], Awaitable[Sequence[str]]]
_PROVIDERS: list[DependentsProvider] = []


def admission_failure(
    required: Sequence[str], statuses: Mapping[str, str]
) -> tuple[str, Failure] | None:
    """(the integration, the code) of the first required integration not connected, or None."""
    for key in required:
        status = statuses.get(key)
        if status == "connected":
            continue
        if status == "needs_reauth":
            return key, "integration_reauth_required"
        if status == "needs_attention":
            return key, "integration_unhealthy"
        return key, "integration_not_connected"
    return None


def register_dependents_provider(provider: DependentsProvider) -> None:
    if provider not in _PROVIDERS:
        _PROVIDERS.append(provider)


async def dependents_of(catalog_key: str) -> list[str]:
    """The capabilities that require the integration (from every registered provider)."""
    out: list[str] = []
    for provider in _PROVIDERS:
        out.extend(await provider(catalog_key))
    return sorted(set(out))


_STATUSES: Final = text(
    "SELECT catalog_key, status FROM firm_integrations WHERE catalog_key = ANY(:keys)"
)
_RUN_FAILED: Final = text(
    "INSERT INTO integration_events (tenant_id, install_kind, install_id, catalog_key, kind, at, "
    "run_id, code) SELECT :t, 'firm', id, catalog_key, 'run_failed', :at, :run, :code "
    "FROM firm_integrations WHERE catalog_key = :k"
)
_FAILED_SINCE: Final = text(
    "SELECT count(*) FROM integration_events WHERE catalog_key = :k AND kind = 'run_failed' "
    "AND at >= :since"
)


async def statuses(tenant: TenantContext, keys: Sequence[str]) -> dict[str, str]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_STATUSES, {"keys": list(keys)})).all()
    return {str(k): str(s) for k, s in rows}


async def admit(tenant: TenantContext, required: Sequence[str]) -> tuple[str, Failure] | None:
    """The admission check against the firm's installs (the run's precondition)."""
    if not required:
        return None
    return admission_failure(required, await statuses(tenant, required))


async def record_run_failed(
    tenant: TenantContext, catalog_key: str, run_id: UUID, code: Failure, at: datetime
) -> None:
    async with uow(tenant) as tx:
        await tx.session.execute(
            _RUN_FAILED,
            {"t": tenant.tenant_id, "at": at, "run": run_id, "code": code, "k": catalog_key},
        )
        tx.record("integration.run_failed", target=Target("agent_run", run_id))


async def failed_runs_since(tenant: TenantContext, catalog_key: str, since: datetime) -> int:
    async with tenant_session(tenant) as session:
        return int(await session.scalar(_FAILED_SINCE, {"k": catalog_key, "since": since}) or 0)
