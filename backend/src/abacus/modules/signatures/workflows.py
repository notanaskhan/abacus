"""`EnvelopeWorkflow` v1 (N-02-T14; N-02 §3.5, §3.7, §4.6; ADR-090, ADR-149; DEC-74).

Orchestration only, activities by name, one run per envelope (`envelope:<tenant>:<envelope>`),
started after a person's send (N-02-T22) on the time-sensitive queue:

1. `signatures.envelope_send`: the provider creates and sends (idempotent on the envelope's
   key); returns the expiry and the reminder instants (weekdays 9:00 in the recipient's zone,
   from the cadence a person chose, never beyond the policy cap or after expiry).
2. Wait for a provider hint (signal `provider_hint`: a Connect call, a portal return or the
   status poll), the next reminder or the expiry, whichever comes first:
   - a hint runs `signatures.envelope_poll`, which reads the provider (the truth; a hint
     carries nothing) and records what changed;
   - a reminder instant runs `signatures.envelope_remind` (a human-approved template only);
   - the expiry runs `signatures.envelope_expire`.
3. On `completed`, `signatures.envelope_complete` builds one evidence package per signer with
   a SHA-256 manifest in the records bucket (COMPLIANCE), files the signed copy and emits
   `envelope.completed`.

No name, address, document or signature enters the history: only identifiers, codes and
instants. A change to what this schedules lands behind `workflow.patched(...)`; every history in
`tests/workflows/histories/envelope-v*.json` must keep replaying.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

_STEP_TIMEOUT = timedelta(seconds=60)
_COMPLETE_TIMEOUT = timedelta(minutes=5)
_RETRY = RetryPolicy(maximum_attempts=0, maximum_interval=timedelta(minutes=5))
_REMIND_RETRY = RetryPolicy(maximum_attempts=3)  # a missed reminder is never sent late twice
FINAL = frozenset({"completed", "declined", "expired", "voided"})


@dataclass(frozen=True)
class EnvelopeInput:
    tenant_id: str
    envelope_id: str


@dataclass(frozen=True)
class SendPlan:
    status: str  # the envelope's status after the send (`sent`, or why it did not go)
    expires_at: str  # ISO 8601, UTC
    reminders: list[str] = field(default_factory=list[str])  # ISO 8601 instants, UTC


@dataclass(frozen=True)
class ReminderDue:
    tenant_id: str
    envelope_id: str
    sequence: int  # 1 for the first reminder


def envelope_workflow_id(tenant_id: str, envelope_id: str) -> str:
    return f"envelope:{tenant_id}:{envelope_id}"


@workflow.defn(name="Envelope")
class EnvelopeWorkflow:
    def __init__(self) -> None:
        self._hints = 0

    @workflow.signal(name="provider_hint")
    def provider_hint(self) -> None:
        """Something may have changed at the provider: poll it."""
        self._hints += 1

    @workflow.run
    async def run(self, given: EnvelopeInput) -> str:
        plan = await workflow.execute_activity(
            "signatures.envelope_send",
            given,
            result_type=SendPlan,
            start_to_close_timeout=_STEP_TIMEOUT,
            retry_policy=_RETRY,
        )
        if plan.status != "sent":
            return plan.status
        expires = datetime.fromisoformat(plan.expires_at)
        pending = sorted(datetime.fromisoformat(r) for r in plan.reminders)
        sequence = 0
        status = plan.status
        while status not in FINAL:
            now = workflow.now()
            pending = [r for r in pending if r > now and r < expires]
            deadline = min([expires, *pending[:1]])
            seen = self._hints
            hinted = True
            try:
                await workflow.wait_condition(
                    lambda seen=seen: self._hints != seen,
                    timeout=max(deadline - now, timedelta(seconds=1)),
                )
            except TimeoutError:  # asyncio's, the same class since 3.11
                hinted = self._hints != seen
            if hinted:
                status = await workflow.execute_activity(
                    "signatures.envelope_poll",
                    given,
                    result_type=str,
                    start_to_close_timeout=_STEP_TIMEOUT,
                    retry_policy=_RETRY,
                )
                continue
            now = workflow.now()
            if now >= expires:
                status = await workflow.execute_activity(
                    "signatures.envelope_expire",
                    given,
                    result_type=str,
                    start_to_close_timeout=_STEP_TIMEOUT,
                    retry_policy=_RETRY,
                )
            elif pending and now >= pending[0]:
                pending.pop(0)
                sequence += 1
                await workflow.execute_activity(
                    "signatures.envelope_remind",
                    ReminderDue(given.tenant_id, given.envelope_id, sequence),
                    result_type=str,
                    start_to_close_timeout=_STEP_TIMEOUT,
                    retry_policy=_REMIND_RETRY,
                )
        if status == "completed":
            await workflow.execute_activity(
                "signatures.envelope_complete",
                given,
                result_type=str,
                start_to_close_timeout=_COMPLETE_TIMEOUT,
                retry_policy=_RETRY,
            )
        return status


STATUS_POLL_ID = "envelope_status_poll:platform"
_SWEEP_TIMEOUT = timedelta(minutes=4)


@workflow.defn(name="EnvelopeStatusPoll")
class EnvelopeStatusPollWorkflow:
    """N-02-T19 (ADR-152's fallback, poll-only): every 5 minutes, a hint to each open DocuSeal
    envelope's workflow, which reads the provider (the truth). Orchestration only."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "signatures.status_poll_sweep",
            result_type=int,
            start_to_close_timeout=_SWEEP_TIMEOUT,
            retry_policy=RetryPolicy(maximum_attempts=2),
        )
