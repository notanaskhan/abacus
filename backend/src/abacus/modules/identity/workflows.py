"""`AccessEndSweep` (G-01-T13; ADR-017, ADR-090): one access-end pass per run, on the Schedule
`access_end:platform` (overlap SKIP, so two workers never sweep at once). Orchestration only: the
activity `identity.sweep_access_ends` does the work inside each firm's own session, so no name,
date or identifier of a person enters the workflow history. A change here lands behind a
`workflow.patched(...)` id so the recorded v1 history keeps replaying."""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

ACCESS_END_ID = "access_end:platform"
_SWEEP_TIMEOUT = timedelta(minutes=10)
_SWEEP_RETRY = RetryPolicy(maximum_attempts=3)  # a failed pass is retried by the next hour's run


@workflow.defn(name="AccessEndSweep")
class AccessEndSweepWorkflow:
    """Ends the access of members whose end date passed in their firm's time zone, and tells
    firm admins seven days ahead (AC4.5)."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "identity.sweep_access_ends",
            result_type=int,
            start_to_close_timeout=_SWEEP_TIMEOUT,
            retry_policy=_SWEEP_RETRY,
        )


AUTH_SESSION_PURGE_ID = "auth_session_purge:platform"
_PURGE_TIMEOUT = timedelta(minutes=5)
_PURGE_RETRY = RetryPolicy(maximum_attempts=3)  # a failed pass is retried by the next day's run


@workflow.defn(name="AuthSessionPurge")
class AuthSessionPurgeWorkflow:
    """G-02-T14 (P-01 hand-off): deletes staff sessions that ended more than a year ago, daily,
    on the Schedule `auth_session_purge:platform` (overlap SKIP). Orchestration only: the
    activity `identity.purge_auth_sessions` returns a count, so no session or person enters the
    history."""

    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            "identity.purge_auth_sessions",
            result_type=int,
            start_to_close_timeout=_PURGE_TIMEOUT,
            retry_policy=_PURGE_RETRY,
        )
