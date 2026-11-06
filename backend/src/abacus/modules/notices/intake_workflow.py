"""`NoticeIntakeWorkflow` (N-04-T07; N-04 §4.5; ADR-090; DEC-2326). Interactive, identifiers only.

Awaits `text_ready` from the P-11 consumer. Ten minutes without it, the intake is `failed`
("Couldn't read this file — enter the fields"). A refusal by the OCR gate is final: `refused`
opens manual entry with the reason in words. Then one activity reads code's fields, matches the
client and the return, looks up the authorization, detects duplicates and marks the intake ready,
or manual entry when no form map covered the file. Started through `kernel.dispatch` from the
outbox, so Temporal being down delays the read and never fails the person's upload; a change lands
behind `workflow.patched(...)`.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.notices.intake_workflow_types import IntakeReadStep, NoticeIntakeInput

_RETRY = RetryPolicy(maximum_attempts=5)
_ACTIVITY_TIMEOUT = timedelta(minutes=2)
TEXT_TIMEOUT = timedelta(minutes=10)


@workflow.defn(name="notice_intake")
class NoticeIntakeWorkflow:
    def __init__(self) -> None:
        self._text_ready = False
        self._refusal: str | None = None

    @workflow.signal(name="text_ready")
    def text_ready(self) -> None:
        self._text_ready = True

    @workflow.signal(name="refused")
    def refused(self, reason: str) -> None:
        self._refusal = reason

    @workflow.run
    async def run(self, given: NoticeIntakeInput) -> str:
        # A file read before the intake existed publishes nothing more: ask first.
        step = IntakeReadStep(given.tenant_id, given.intake_id)
        status = await self._step("notice_intake.read_if_ready", step)
        if status != "extracting":
            return status
        try:
            await workflow.wait_condition(
                lambda: self._text_ready or self._refusal is not None, timeout=TEXT_TIMEOUT
            )
        except TimeoutError:
            return await self._step("notice_intake.mark_failed", step)
        return await self._step(
            "notice_intake.read", IntakeReadStep(given.tenant_id, given.intake_id, self._refusal)
        )

    async def _step(self, activity: str, step: IntakeReadStep) -> str:
        return await workflow.execute_activity(
            activity,
            step,
            result_type=str,
            start_to_close_timeout=_ACTIVITY_TIMEOUT,
            retry_policy=_RETRY,
        )
