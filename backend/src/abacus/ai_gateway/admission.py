"""Admission control for model calls (ADR-072; SPEC-003 AC-9 to AC-12; TASK-018 design §6, D4).
PROTECTED.

Every model call is admitted against its model's token bucket (requests and tokens per minute,
migration 0014) before it is sent. Priority comes from reserves: a work class may only take
capacity while more than its reserve remains (interactive and time-sensitive 0%, background 25%,
batch 50%), and a deferrable agent uses the next class's reserve, so essential work goes first
(D4). Refused, the call raises `NotAdmitted` with a reason and when to ask again; the workflow
waits (durably) and asks again. A provider's rate-limit response blocks the model for the time it
asked for, and is never retried here (AC-12). If the bucket can't be reached, nothing is admitted.

Like the work slot ledger, the bucket is operational, not domain state: each call commits on its
own, with no audit event (founder decision 2026-10-07, TASK-018). UOW-001/UOW-002 exempt this file.
"""

from __future__ import annotations

from typing import Final

from sqlalchemy import text

from abacus.kernel.config import settings
from abacus.kernel.db import TenantContext, tenant_connection
from abacus.kernel.logging import get_logger
from abacus.kernel.metrics import meter
from abacus.kernel.work_class import WorkClass

ADMISSION: Final = "abacus.admission"
# A deferrable agent waits behind essential work of its class: it takes the next class's reserve.
_NEXT: Final[dict[WorkClass, WorkClass]] = {
    "interactive": "time_sensitive",
    "time_sensitive": "background",
    "background": "batch",
    "batch": "batch",
}
_UNREACHABLE_RETRY_SECONDS = 30
_log = get_logger(__name__)
_admissions = meter(__name__).create_counter(
    ADMISSION, description="Model call admissions by class and outcome (admitted or refused)"
)


class NotAdmitted(Exception):
    """No capacity for this call now: `reason` is `provider_capacity` or `deferred`, and
    `retry_after` how many seconds until it is worth asking again."""

    def __init__(self, reason: str, retry_after: int) -> None:
        super().__init__(reason)
        self.reason = reason
        self.retry_after = retry_after


class CallTooLarge(ValueError):
    """The call needs more tokens than its class may ever take from the model's bucket: it would
    wait until `capacity_timeout`, so it fails now instead (TASK-018c review)."""


def reserve_pct(work_class: WorkClass, essential: bool) -> int:
    return (
        settings()
        .work_classes[work_class if essential else _NEXT[work_class]]
        .admission_reserve_pct
    )


def refusal_reason(work_class: WorkClass) -> str:
    """Background and batch work refused under pressure is deferred (ADR-072's first steps);
    interactive and time-sensitive work waits for the provider."""
    return "deferred" if work_class in ("background", "batch") else "provider_capacity"


async def admit(
    tenant: TenantContext,
    route: str,
    model: str,
    work_class: WorkClass,
    essential: bool,
    tokens: int,
) -> tuple[bool, int]:
    """Take one request and `tokens` from the model's bucket: (admitted, retry_after seconds).
    Fails closed: an unknown model or an unreachable bucket admits nothing."""
    s = settings()
    limits = s.provider_limits.get(model)
    if limits is None:
        _log.warning("admission.unconfigured", model=model)
        _record(route, model, work_class, "refused", "unconfigured")
        return False, _UNREACHABLE_RETRY_SECONDS
    reserve = reserve_pct(work_class, essential)
    if tokens > limits.tpm * (100 - reserve) // 100:
        raise CallTooLarge(f"{model}: {tokens} tokens can never fit above a {reserve}% reserve")
    try:
        async with tenant_connection(tenant) as conn:
            row = (
                await conn.execute(
                    text(
                        "SELECT admitted, retry_after_seconds FROM capacity_admit("
                        ":provider, :model, :rpm, :tpm, :reserve_pct, :tokens)"
                    ),
                    {
                        "provider": route,
                        "model": model,
                        "rpm": limits.rpm,
                        "tpm": limits.tpm,
                        "reserve_pct": reserve,
                        "tokens": max(1, tokens),
                    },
                )
            ).one()
            await conn.commit()
    except Exception as exc:
        _log.warning("admission.unavailable", model=model, error=exc)
        _record(route, model, work_class, "refused", "unavailable")
        return False, _UNREACHABLE_RETRY_SECONDS
    admitted, retry_after = bool(row[0]), int(row[1])
    _record(
        route, model, work_class, "admitted" if admitted else "refused", refusal_reason(work_class)
    )
    if not admitted:
        _log.info("admission.refused", model=model, work_class=work_class, retry_after=retry_after)
    return admitted, retry_after


async def block(tenant: TenantContext, route: str, model: str, seconds: int) -> None:
    """A route rate-limited `model` or is out (SPEC-010 Q3): admit nothing for it on that route
    for `seconds` (SPEC-003 AC-12)."""
    seconds = max(1, min(seconds, 3600))
    _log.warning("provider.blocked", route=route, model=model, seconds=seconds)
    async with tenant_connection(tenant) as conn:
        await conn.execute(
            text("SELECT capacity_block(:provider, :model, :seconds)"),
            {"provider": route, "model": model, "seconds": seconds},
        )
        await conn.commit()


def _record(route: str, model: str, work_class: WorkClass, outcome: str, reason: str) -> None:
    _admissions.add(
        1,
        {
            "provider": route,
            "model": model,
            "work_class": work_class,
            "outcome": outcome,
            "reason": reason if outcome != "admitted" else "",
        },
    )
