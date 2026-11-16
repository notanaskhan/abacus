"""`ConfirmationFollowUpWorkflow` (A-08-T18; A-08 §3 F4; SPEC-657 AC-6.6; DEC-5324; red).

A daily sweep over every firm's sent confirmations. It never acts: a second request is a
person's send and alternative procedures a person's record (`confirmations_lifecycle`). When
`follow_up_step` says one is due, the sweep prompts the person who sent the confirmation once
(a `second_request_due` or `no_response_due` event on the confirmation, and the team
notification `confirmation_second_request_due` or `confirmation_expired_no_response`). A
confirmation answered meanwhile is never prompted. One firm's failure never stops the rest.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Final, cast
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

# The workflow sandbox loads this module; its activities' imports pass through (as A-07's sweep).
with workflow.unsafe.imports_passed_through():
    from sqlalchemy import text

    from abacus.kernel.clock import now as clock_now
    from abacus.kernel.db import TenantContext, tenant_session
    from abacus.kernel.dispatch import PlatformSchedule
    from abacus.kernel.logging import get_logger
    from abacus.kernel.uow import Target, uow
    from abacus.modules.assurance.confirmations_lifecycle import follow_up_step
    from abacus.modules.assurance.events import (
        ConfirmationNoResponse,
        ConfirmationSecondRequestDue,
    )

_log = get_logger(__name__)
SWEEP_ID: Final = "confirmation_follow_up:platform"
_ACTOR: Final = "confirmation-follow-up:sweep"
_PROMPT: Final = {
    "second_request": "second_request_due",
    "alternative_procedures": "no_response_due",
}
_SENT: Final = text(
    "SELECT c.id, c.engagement_id, c.status FROM confirmations c WHERE c.status = 'sent'"
)
_EVENTS: Final = text(
    "SELECT kind, at, actor_kind, actor_id FROM confirmation_events WHERE confirmation_id = :c "
    "ORDER BY at"
)
_PROMPTED: Final = text(
    "INSERT INTO confirmation_events (tenant_id, confirmation_id, kind, actor_kind, actor_id) "
    "VALUES (:t, :c, :k, 'system', :a)"
)


def prompt_due(events: list[tuple[str, datetime]], status: str, now: datetime) -> str | None:
    """The prompt to record now, or None: the due step's prompt, unless already recorded since
    the send or second request it follows."""
    step = follow_up_step(events, status, now)
    if step is None:
        return None
    prompt = _PROMPT[step]
    after = (step == "second_request" and "sent") or "second_request"
    last = max((at for k, at in events if k == after), default=None)
    if any(k == prompt and (last is None or at >= last) for k, at in events):
        return None
    return prompt


async def sweep_tenant(tenant_id: UUID, now: datetime | None = None) -> int:
    tenant = TenantContext(tenant_id, "system", _ACTOR)
    at = now or await clock_now(tenant)
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_SENT)).all()
    prompted = 0
    for confirmation, engagement, status in rows:
        async with tenant_session(tenant) as session:
            found = (await session.execute(_EVENTS, {"c": confirmation})).all()
        events = [(str(k), cast(datetime, a)) for k, a, _, _ in found]
        prompt = prompt_due(events, str(status), at)
        senders = [str(i) for k, _, ak, i in found if k == "sent" and ak == "human"]
        if prompt is None or not senders:
            continue
        sender = UUID(senders[-1])
        async with uow(tenant) as tx:
            await tx.session.execute(
                _PROMPTED, {"t": tenant_id, "c": confirmation, "k": prompt, "a": _ACTOR}
            )
            event = (
                ConfirmationSecondRequestDue
                if prompt == "second_request_due"
                else (ConfirmationNoResponse)
            )
            tx.emit(event(confirmation_id=confirmation, engagement_id=engagement, user_id=sender))
            tx.record(f"confirmation.{prompt}", target=Target("confirmation", confirmation))
        prompted += 1
    return prompted


@activity.defn(name="assurance.confirmations.follow_up_sweep")
async def follow_up_sweep_activity() -> int:
    from abacus.modules.identity.api import firm_tenant_ids

    prompted = 0
    for tenant_id in await firm_tenant_ids():
        try:
            prompted += await sweep_tenant(tenant_id)
        except Exception as exc:  # one firm's failure is logged; the sweep goes on
            _log.error(
                "confirmation.follow_up_failed", tenant_id=str(tenant_id), error=type(exc).__name__
            )
    return prompted


_RETRY = RetryPolicy(maximum_attempts=3, initial_interval=timedelta(seconds=30))


@workflow.defn(name="ConfirmationFollowUpWorkflow")
class ConfirmationFollowUpWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "assurance.confirmations.follow_up_sweep",
            result_type=int,
            start_to_close_timeout=timedelta(hours=1),
            retry_policy=_RETRY,
        )


WORKFLOWS: Final[dict[type, str]] = {ConfirmationFollowUpWorkflow: "batch"}
ACTIVITIES: Final[tuple[object, ...]] = (follow_up_sweep_activity,)
SCHEDULES: Final[tuple[PlatformSchedule, ...]] = (
    PlatformSchedule(
        id=SWEEP_ID,
        workflow=ConfirmationFollowUpWorkflow,
        every=timedelta(days=1),
        note="A-08-T18: prompt each sent confirmation's sender when a follow-up step is due",
    ),
)
