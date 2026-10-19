"""Fieldwork activities (SPEC-037; TASK-077)."""

from __future__ import annotations

from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.modules.fieldwork.selecting import fail_selection, run_selection
from abacus.modules.fieldwork.workflow_types import ProcedureSelectInput


@activity.defn(name="procedure.select")
async def select_activity(input: ProcedureSelectInput) -> str:
    try:
        return await run_selection(
            UUID(input.tenant_id), UUID(input.procedure_id), UUID(input.requested_by)
        )
    except Exception as exc:  # only the class name crosses to Temporal (security S3)
        name = type(exc).__name__
        raise ApplicationError(name, type=name) from None


@activity.defn(name="procedure.fail")
async def fail_activity(input: ProcedureSelectInput) -> None:
    await fail_selection(UUID(input.tenant_id), UUID(input.procedure_id))


ACTIVITIES = (select_activity, fail_activity)
