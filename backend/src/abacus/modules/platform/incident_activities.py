"""`IncidentPropagation`'s activity (Q-02-T33; RB-27). Identifiers and Accrued's facts in, the
firm's entry reference out. Repeat-safe; errors cross as their class name only. A firm that
doesn't exist is not retried."""

from __future__ import annotations

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.modules.platform.incidents import FirmNotFound, propagate_into
from abacus.modules.platform.workflow_types import IncidentPropagationStep


@activity.defn(name="platform.propagate_incident")
async def propagate_incident_activity(step: IncidentPropagationStep) -> str:
    try:
        return await propagate_into(step)
    except FirmNotFound:
        raise ApplicationError("FirmNotFound", type="FirmNotFound", non_retryable=True) from None
    except Exception as exc:
        name = type(exc).__name__
        raise ApplicationError(name, type=name) from None


INCIDENT_ACTIVITIES = (propagate_incident_activity,)
