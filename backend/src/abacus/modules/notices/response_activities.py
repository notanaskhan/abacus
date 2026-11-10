"""`NoticeResponseWorkflow`'s activities (N-04-T16): identifiers in, events out."""

from __future__ import annotations

from temporalio import activity

from abacus.modules.notices.response_workflow_types import AlertInput, FollowUpInput
from abacus.modules.notices.sending import send_alert, send_follow_up


@activity.defn(name="notice_response.alert")
async def alert_activity(given: AlertInput) -> None:
    await send_alert(given)


@activity.defn(name="notice_response.follow_up")
async def follow_up_activity(given: FollowUpInput) -> None:
    await send_follow_up(given)


ACTIVITIES = (alert_activity, follow_up_activity)
