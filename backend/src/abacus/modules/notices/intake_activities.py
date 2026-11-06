"""`NoticeIntakeWorkflow`'s activities (N-04-T07): identifiers in, the intake's status out."""

from __future__ import annotations

from uuid import UUID

from temporalio import activity

from abacus.modules.notices.intake_read import mark_failed, read_if_ready, read_intake
from abacus.modules.notices.intake_workflow_types import IntakeReadStep


@activity.defn(name="notice_intake.read_if_ready")
async def read_if_ready_activity(step: IntakeReadStep) -> str:
    return await read_if_ready(UUID(step.tenant_id), UUID(step.intake_id))


@activity.defn(name="notice_intake.read")
async def read_activity(step: IntakeReadStep) -> str:
    return await read_intake(UUID(step.tenant_id), UUID(step.intake_id), step.refusal)


@activity.defn(name="notice_intake.mark_failed")
async def mark_failed_activity(step: IntakeReadStep) -> str:
    return await mark_failed(UUID(step.tenant_id), UUID(step.intake_id))


ACTIVITIES = (read_if_ready_activity, read_activity, mark_failed_activity)
