"""The sample draw's activities (A-03-T10; A-03 §4.4): identifiers in, a status word out."""

from __future__ import annotations

from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.modules.sampling.draw import fail_draw, run_draw
from abacus.modules.sampling.draw_types import SampleDrawInput


@activity.defn(name="sample_draw.run")
async def run_activity(input: SampleDrawInput) -> str:
    try:
        return await run_draw(UUID(input.tenant_id), UUID(input.version_id))
    except Exception as exc:  # only the class name crosses to Temporal (security S3)
        name = type(exc).__name__
        raise ApplicationError(name, type=name) from None


@activity.defn(name="sample_draw.fail")
async def fail_activity(input: SampleDrawInput) -> None:
    await fail_draw(UUID(input.tenant_id), UUID(input.version_id))


ACTIVITIES = (run_activity, fail_activity)
