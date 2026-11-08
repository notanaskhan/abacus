"""`AgentRunBackfill` (P-10-T14; SPEC-647 §4.4; ADR-090): gives every pre-v2 agent run in one firm
its v2 state, run number and session link, a throttled batch at a time.

Started once per firm by the deploy pipeline after 8 pm CT, with the id
`agent_run_backfill:<tenant>` (`abacus_tools.agent_run_backfill`); a second start with the same id
is refused by Temporal. Orchestration only: the activity `agents.backfill_run_batch` does the work
in the firm's own session and returns counts, so no run, person or content enters the history.

Resumable by construction: a batch picks only rows whose `state` is still NULL, so a run that was
cancelled, failed or interrupted is started again and carries on where it stopped. The history is
kept short with continue-as-new every `_BATCHES_PER_RUN` batches. Histories:
`agent-run-backfill-v1-completed.json` and `agent-run-backfill-v1-resumed.json`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

BACKFILL_ID_PREFIX = "agent_run_backfill:"
_BATCH_TIMEOUT = timedelta(minutes=2)
_BATCH_RETRY = RetryPolicy(maximum_attempts=5, initial_interval=timedelta(seconds=5))
_BATCHES_PER_RUN = 200


@dataclass(frozen=True)
class BackfillInput:
    tenant_id: str
    batch_size: int = 500
    pause_seconds: float = 2.0  # throttle: the live specialists share this database
    done_so_far: int = 0


@dataclass(frozen=True)
class BackfillBatch:
    """One batch's counts: rows given a state, and whether any NULL-state row is left."""

    updated: int
    remaining: bool


@workflow.defn(name="AgentRunBackfill")
class AgentRunBackfillWorkflow:
    @workflow.run
    async def run(self, params: BackfillInput) -> int:
        done = params.done_so_far
        for _ in range(_BATCHES_PER_RUN):
            batch = await workflow.execute_activity(
                "agents.backfill_run_batch",
                args=[params.tenant_id, params.batch_size],
                result_type=BackfillBatch,
                start_to_close_timeout=_BATCH_TIMEOUT,
                retry_policy=_BATCH_RETRY,
            )
            done += batch.updated
            if not batch.remaining:
                return done
            await workflow.sleep(timedelta(seconds=params.pause_seconds))
        workflow.continue_as_new(
            BackfillInput(params.tenant_id, params.batch_size, params.pause_seconds, done)
        )
