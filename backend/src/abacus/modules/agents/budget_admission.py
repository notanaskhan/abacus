"""The over-limit admission hook (G-04-T08; SPEC-680 AC-37; chapter 05 §5.6.5; DEC-5420; red).

With `platform.plan_usage` on and the firm's At 100% set to "Pause scheduled agents only", a run
whose `trigger_kind` is `schedule` is refused at admission once this usage month's minutes are at
or over the included minutes: `admission_refusal` answers `budget_100pct` and the caller records
no run minutes (no ledger row). Every other trigger (manual, session, `agent_trigger`,
`engagement_trigger`, `agent_column`, `event_policy`, `retry`, `test`) starts; a running run and
an open Workbench session are never stopped. Firm admins get one `usage.scheduled_paused` notice
per usage month (`announce_pause`, deduplicated on a tenant counter); the next usage month
resumes by itself because the month's minutes start again. "Keep agents running" refuses nothing.
The USD safety layer (`ai_gateway/budgets.py`) is separate and unchanged.
"""

from __future__ import annotations

from typing import Annotated, ClassVar, Final

from sqlalchemy import text

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.uow import DomainEvent, Ref, Target, uow

BUDGET_100PCT: Final = "budget_100pct"
PAUSABLE: Final = frozenset({"schedule"})
_I = classified("internal")


class ScheduledRunsPaused(DomainEvent):
    """C16 `usage_scheduled_paused` (firm admins, in-app), once per usage month."""

    event_type: ClassVar[str] = "usage.scheduled_paused"

    usage_month: Annotated[str, _I]


def refusal(trigger_kind: str, *, pause_scheduled: bool, at_or_over: bool) -> str | None:
    """The state reason a run is refused with at admission, or None when it starts."""
    if trigger_kind in PAUSABLE and pause_scheduled and at_or_over:
        return BUDGET_100PCT
    return None


async def admission_refusal(tenant: TenantContext, trigger_kind: str) -> str | None:
    """Ask the platform's policy only for a run that could be paused."""
    if trigger_kind not in PAUSABLE:
        return None
    from abacus.modules.platform.api import over_limit_policy

    policy = await over_limit_policy(tenant)
    found = refusal(
        trigger_kind, pause_scheduled=policy.pause_scheduled, at_or_over=policy.at_or_over
    )
    if found is not None:
        await announce_pause(tenant, policy.usage_month)
    return found


async def announce_pause(tenant: TenantContext, usage_month: str) -> bool:
    """One notice per usage month: the first refusal claims the month's counter."""
    async with uow(TenantContext(tenant.tenant_id, "system", "budget_admission")) as tx:
        first = await tx.session.scalar(
            text(
                "INSERT INTO tenant_counters (tenant_id, name, value) VALUES (:t, :n, 1) "
                "ON CONFLICT (tenant_id, name) DO NOTHING RETURNING value"
            ),
            {"t": tenant.tenant_id, "n": f"usage_scheduled_paused:{usage_month}"},
        )
        if first is None:
            return False
        tx.record(
            "usage.scheduled_run_paused",
            target=Target("firm", tenant.tenant_id),
            after=Ref(usage_month=usage_month),
        )
        tx.emit(ScheduledRunsPaused(usage_month=usage_month))
    return True


__all__ = ["BUDGET_100PCT", "admission_refusal", "announce_pause", "refusal"]
