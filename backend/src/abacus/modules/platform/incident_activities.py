"""`IncidentPropagation`'s activities (Q-02-T33; RB-27). Identifiers and Accrued's facts in, the
firm's entry out. Repeat-safe; errors cross as their class name only. A firm that doesn't exist,
or that already has the incident with other facts, is not retried.

- `platform.propagate_incident` (v1 runs, still in flight after the v2 deploy): the entry's
  reference.
- `platform.propagate_incident_v2`: the reference and whether it was written or identical.
- `platform.finish_incident_propagation` (v2): the run's end, recorded for staff.
"""

from __future__ import annotations

from collections.abc import Awaitable

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.modules.platform.incidents import (
    FirmNotFound,
    IncidentFactsChanged,
    finish_propagation,
    propagate_into,
)
from abacus.modules.platform.workflow_types import (
    IncidentPropagationOutcome,
    IncidentPropagationStep,
    IncidentStepResult,
)

_NOT_RETRIED = (FirmNotFound, IncidentFactsChanged)


async def _crossed[T](work: Awaitable[T]) -> T:
    try:
        return await work
    except _NOT_RETRIED as exc:
        name = type(exc).__name__
        raise ApplicationError(name, type=name, non_retryable=True) from None
    except Exception as exc:
        name = type(exc).__name__
        raise ApplicationError(name, type=name) from None


@activity.defn(name="platform.propagate_incident")
async def propagate_incident_activity(step: IncidentPropagationStep) -> str:
    return (await _crossed(propagate_into(step))).ref


@activity.defn(name="platform.propagate_incident_v2")
async def propagate_incident_v2_activity(step: IncidentPropagationStep) -> IncidentStepResult:
    return await _crossed(propagate_into(step))


@activity.defn(name="platform.finish_incident_propagation")
async def finish_incident_propagation_activity(outcome: IncidentPropagationOutcome) -> None:
    await _crossed(finish_propagation(outcome))


INCIDENT_ACTIVITIES = (
    propagate_incident_activity,
    propagate_incident_v2_activity,
    finish_incident_propagation_activity,
)
