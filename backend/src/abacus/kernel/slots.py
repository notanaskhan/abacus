"""Work slots: per-firm and per-engagement caps with fair hand-out (ADR-071; SPEC-003 AC-6 to
AC-8, AC-13, AC-14; TASK-018 design §4 and D3). PROTECTED.

    decision = await acquire(tenant, holder, engagement_id, "interactive")
    if decision.granted: ...            # run; `renew` from each activity; `release` at the end

A workflow holds one slot of its class while it runs. The ledger is platform-owned and reached
only through the database functions of migration 0013, which take the tenant from the session
(`tenant_session` sets it) and answer only for the caller: granted, or why not (`firm_cap`,
`engagement_cap`, `class_capacity`) and an estimated start (None when there's no recent
throughput). Limits come from `settings().work_classes`. Waiting is the workflow's (durable
timers), never an activity's.

The ledger is operational, not domain state: each call commits on its own, with no audit event
(SPEC-003 §14; founder decision 2026-10-07). A run's visible change (queued, and running again)
is the module's, through the unit of work and audited (UOW-001 and UOW-002 exempt this file only).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from sqlalchemy import text
from temporalio import activity

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_connection
from abacus.kernel.dispatch import work_class_of_queue
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.work_class import WorkClass

# A slot outlives its holder's crash by at most this; every activity renews it.
LEASE_SECONDS: Final = 15 * 60
SLOT_DECISIONS: Final = "abacus.slots.decisions"
_log = get_logger(__name__)
_decisions = meter(__name__).create_counter(
    SLOT_DECISIONS, description="Work slot requests by class and outcome (granted or waiting)"
)


@dataclass(frozen=True)
class SlotDecision:
    granted: bool
    reason: str | None
    estimated_start_at: datetime | None


async def acquire(
    tenant: TenantContext, holder: str, engagement_id: UUID | None, work_class: WorkClass
) -> SlotDecision:
    limits = settings().work_classes[work_class]
    async with tenant_connection(tenant) as conn:
        row = (
            await conn.execute(
                text(
                    "SELECT granted, reason, estimated_start_at FROM work_slot_acquire("
                    ":holder, :engagement_id, :work_class, :firm_cap, :engagement_cap, "
                    ":class_capacity, :lease_seconds)"
                ),
                {
                    "holder": holder,
                    "engagement_id": engagement_id,
                    "work_class": work_class,
                    "firm_cap": limits.firm_cap,
                    "engagement_cap": limits.engagement_cap,
                    "class_capacity": limits.class_capacity,
                    "lease_seconds": LEASE_SECONDS,
                },
            )
        ).one()
        await conn.commit()
    decision = SlotDecision(bool(row[0]), row[1], row[2])
    outcome = "granted" if decision.granted else "waiting"
    _decisions.add(
        1, {"work_class": work_class, "outcome": outcome, "reason": decision.reason or ""}
    )
    if decision.granted:
        _log.info("slot.acquired", tenant_id=tenant.tenant_id, work_class=work_class)
    else:
        _log.info(
            "slot.waiting",
            tenant_id=tenant.tenant_id,
            work_class=work_class,
            reason=decision.reason,
        )
    return decision


async def renew(tenant: TenantContext, holder: str) -> bool:
    """Extend the holder's lease; False if it holds no slot (never granted, or reclaimed)."""
    async with tenant_connection(tenant) as conn:
        renewed = await conn.scalar(
            text("SELECT work_slot_renew(:holder, :lease_seconds)"),
            {"holder": holder, "lease_seconds": LEASE_SECONDS},
        )
        await conn.commit()
    return bool(renewed)


async def release(tenant_id: UUID, holder: str) -> None:
    """Free the holder's slot and forget it as a waiter (idempotent). Works for a run that has
    already ended, so it needs only the firm."""
    tenant = TenantContext(tenant_id, "system", "work-slots")
    async with tenant_connection(tenant) as conn:
        await conn.execute(text("SELECT work_slot_release(:holder)"), {"holder": holder})
        await conn.commit()


# --- inside an activity ------------------------------------------------------------------------


def current_holder() -> str:
    """The running workflow execution: one slot per workflow run."""
    info = activity.info()
    return f"{info.workflow_id}:{info.workflow_run_id}"


def current_class() -> WorkClass | None:
    """The work class of the queue this activity runs on (its workflow's); None on the legacy
    queue, whose workflows take no slot."""
    return work_class_of_queue(activity.info().task_queue)
