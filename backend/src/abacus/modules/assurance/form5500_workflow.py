"""`Form5500TieOut` (A-05-T54; A-05 §4.5; ADR-090): ties a draft Form 5500 when it arrives.

Started by `ebp.form5500.draft_received` (the draft that fulfils Summit's request), with the id
`form5500_tieout:<draft>`. Orchestration only: the activity `ebp.form5500_tieout` computes in the
firm's own session and returns counts, so no amount or name enters the history. Code only: no
model call (the mode `ebp_form5500` reads the form's fields separately, A-05-T55).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

TIEOUT_ID_PREFIX = "form5500_tieout:"


@dataclass(frozen=True)
class TieOutInput:
    tenant_id: str
    draft_id: str


@dataclass(frozen=True)
class TieOutCounts:
    ties: int
    reconciling: int
    inconsistent: int
    part_iv_inconsistent: int


@workflow.defn(name="Form5500TieOut")
class Form5500TieOutWorkflow:
    @workflow.run
    async def run(self, params: TieOutInput) -> TieOutCounts:
        return await workflow.execute_activity(
            "ebp.form5500_tieout",
            args=[params.tenant_id, params.draft_id],
            result_type=TieOutCounts,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
