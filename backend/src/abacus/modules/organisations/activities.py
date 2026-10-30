"""The consent registry's activities and its Schedule (T-01-T16; DEC-1354)."""

from __future__ import annotations

from datetime import timedelta
from typing import Final
from uuid import UUID

from temporalio import activity

from abacus.kernel.dispatch import PlatformSchedule, dispatch
from abacus.kernel.logging import get_logger
from abacus.modules.identity.api import firm_tenant_ids
from abacus.modules.organisations.consent_registry import build_export, sweep
from abacus.modules.organisations.workflows import (
    SWEEP_ID,
    ConsentExportInput,
    ConsentExportWorkflow,
    ConsentLifecycleSweepWorkflow,
    export_workflow_id,
)

_log = get_logger(__name__)


@activity.defn(name="organisations.consent_export")
async def consent_export(request: ConsentExportInput) -> int:
    return await build_export(
        UUID(request.tenant_id), UUID(request.export_id), [UUID(i) for i in request.consent_ids]
    )


@activity.defn(name="organisations.consent_sweep")
async def consent_sweep() -> int:
    """Every firm, one at a time; one firm's failure never stops the others."""
    touched = 0
    for tenant_id in await firm_tenant_ids():
        try:
            found = await sweep(tenant_id)
            touched += found.expiring + found.expired + found.reconsent
        except Exception as exc:  # one firm's failure never stops the others
            _log.error("consent_sweep.failed", tenant_id=str(tenant_id), error=type(exc).__name__)
    return touched


async def start_consent_export(request: ConsentExportInput) -> None:
    await dispatch(
        ConsentExportWorkflow,
        request,
        id=export_workflow_id(request.tenant_id, request.export_id),
    )


ACTIVITIES: Final[tuple[object, ...]] = (consent_export, consent_sweep)
SCHEDULES: Final[tuple[PlatformSchedule, ...]] = (
    PlatformSchedule(
        id=SWEEP_ID,
        workflow=ConsentLifecycleSweepWorkflow,
        every=timedelta(days=1),
        note="T-01-T16: consents expiring in 30 days, expired, or signed under old terms",
        weekly=None,
    ),
)
