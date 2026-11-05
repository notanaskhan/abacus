"""`NoticeResponseWorkflow` (N-04-T16; N-04 §4.5, US-3.4; ADR-090). Time-sensitive, long-running.

Alerts before the respond-by (-7 and -2 days; a CP3219A also -30 and -14), cancelled once the
response is sent; then the follow-up timer, and it finishes on the agency's reply. A correction of
the respond-by resets the timers by signal. Dates only, never amounts. Continues as new after each
alert, so a notice open for months keeps a short history. Started at Create notice through
`kernel.dispatch`; a change lands behind `workflow.patched(...)`.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from abacus.modules.notices.response_workflow_types import (
        AlertInput,
        FollowUpInput,
        NoticeResponseInput,
    )

_RETRY = RetryPolicy(maximum_attempts=5)
_ACTIVITY_TIMEOUT = timedelta(minutes=2)
ALERTS = (7, 2)
CP3219A_ALERTS = (30, 14, 7, 2)


def alert_days(notice_type_key: str) -> tuple[int, ...]:
    return CP3219A_ALERTS if notice_type_key == "cp3219a" else ALERTS


@workflow.defn(name="notice_response")
class NoticeResponseWorkflow:
    def __init__(self) -> None:
        self._respond_by: str | None = None
        self._follow_up_on: str | None = None
        self._replied = False
        self._changed = False

    @workflow.signal(name="respond_by_changed")
    def respond_by_changed(self, respond_by: str | None) -> None:
        self._respond_by = respond_by
        self._changed = True

    @workflow.signal(name="sent")
    def sent(self, follow_up_on: str) -> None:
        self._follow_up_on = follow_up_on
        self._changed = True

    @workflow.signal(name="agency_reply")
    def agency_reply(self) -> None:
        self._replied = True
        self._changed = True

    def _now(self) -> date:
        return workflow.now().date()

    async def _wait_until(self, day: date) -> bool:
        """True when `day` came; False when a signal changed the plan first."""
        target = datetime(day.year, day.month, day.day, tzinfo=workflow.now().tzinfo)
        seconds = (target - workflow.now()).total_seconds()
        if seconds <= 0:
            return True
        self._changed = False
        try:
            await workflow.wait_condition(
                lambda: self._changed, timeout=timedelta(seconds=seconds)
            )
        except TimeoutError:
            return True
        return False

    @workflow.run
    async def run(self, given: NoticeResponseInput) -> str:
        self._respond_by = self._respond_by or given.respond_by
        self._follow_up_on = self._follow_up_on or given.follow_up_on
        fired = set(given.fired)
        while not self._replied:
            if self._follow_up_on is not None:
                if await self._wait_until(date.fromisoformat(self._follow_up_on)):
                    if self._replied:
                        break
                    await workflow.execute_activity(
                        "notice_response.follow_up",
                        FollowUpInput(given.tenant_id, given.work_item_id, self._follow_up_on),
                        start_to_close_timeout=_ACTIVITY_TIMEOUT,
                        retry_policy=_RETRY,
                    )
                    await workflow.wait_condition(lambda: self._replied)
                continue
            due = self._next_alert(given.notice_type_key, fired)
            if due is None:
                self._changed = False
                await workflow.wait_condition(lambda: self._changed)
                continue
            days_left, on = due
            if not await self._wait_until(on):
                continue
            if self._follow_up_on is not None or self._replied:
                continue
            if self._respond_by is None:
                continue
            await workflow.execute_activity(
                "notice_response.alert",
                AlertInput(given.tenant_id, given.work_item_id, self._respond_by, days_left),
                start_to_close_timeout=_ACTIVITY_TIMEOUT,
                retry_policy=_RETRY,
            )
            fired.add(days_left)
            workflow.continue_as_new(
                NoticeResponseInput(
                    given.tenant_id, given.work_item_id, self._respond_by,
                    given.notice_type_key, self._follow_up_on, tuple(sorted(fired)),
                )
            )  # fmt: skip
        return "replied"

    def _next_alert(self, key: str, fired: set[int]) -> tuple[int, date] | None:
        if self._respond_by is None:
            return None
        respond_by = date.fromisoformat(self._respond_by)
        for days_left in alert_days(key):
            on = respond_by - timedelta(days=days_left)
            if days_left not in fired and on >= self._now():
                return days_left, on
        return None
