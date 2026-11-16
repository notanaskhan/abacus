"""The JE scoring activities (A-08-T12): identifiers in, a status word out."""

from __future__ import annotations

from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.modules.sampling.je_scoring_types import JeScoringInput
from abacus.modules.sampling.je_tests import fail_scoring, run_scoring


@activity.defn(name="je_scoring.run")
async def run_activity(input: JeScoringInput) -> str:
    try:
        return await run_scoring(
            UUID(input.tenant_id), UUID(input.je_test_id), input.score_version
        )
    except Exception as exc:  # only the class name crosses to Temporal (security S3)
        name = type(exc).__name__
        raise ApplicationError(name, type=name) from None


@activity.defn(name="je_scoring.fail")
async def fail_activity(input: JeScoringInput) -> None:
    await fail_scoring(UUID(input.tenant_id), UUID(input.je_test_id))


ACTIVITIES = (run_activity, fail_activity)
