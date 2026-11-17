"""The JE scoring activities (A-08-T12): identifiers in, a status word out."""

from __future__ import annotations

import time
from uuid import UUID

from temporalio import activity
from temporalio.exceptions import ApplicationError

from abacus.kernel.logging import get_logger
from abacus.modules.sampling.je_scoring_types import JeScoringInput
from abacus.modules.sampling.je_tests import fail_scoring, run_scoring

_log = get_logger(__name__)


@activity.defn(name="je_scoring.run")
async def run_activity(input: JeScoringInput) -> str:
    started = time.monotonic()
    try:
        status = await run_scoring(
            UUID(input.tenant_id), UUID(input.je_test_id), input.score_version
        )
    except Exception as exc:  # only the class name crosses to Temporal (security S3)
        name = type(exc).__name__
        raise ApplicationError(name, type=name) from None
    # A-08-T38 (DEC-5404): the JE scoring duration alarm reads this line (milliseconds only).
    _log.info("je_scoring.completed", duration_ms=int((time.monotonic() - started) * 1000))
    return status


@activity.defn(name="je_scoring.fail")
async def fail_activity(input: JeScoringInput) -> None:
    await fail_scoring(UUID(input.tenant_id), UUID(input.je_test_id))


ACTIVITIES = (run_activity, fail_activity)
