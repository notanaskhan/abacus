"""ReleaseWorkflow (A-07-T30; A-07 §4.5; DEC-3107): `release:<tenant>:<work item>:<grant>`,
class `time_sensitive`, started only through `kernel.dispatch` (DISPATCH-001) after the EP's
decision commits.

1. `assurance.release.consume_and_render`: the single gate consumes the grant; G5-G7 and the
   also-required list are re-evaluated (unchanged since the dialog, or `content_changed`); C11
   inserts the final version (no watermark, the firm signature) under the consumed grant.
2. `assurance.release.final_render`: waits for the render job (retried while queued or running;
   a failed job ends the run).
3. `assurance.release.record`: the one unit of work for G8 (`release.record_in_app_release`).
4. On any refusal or failure, `assurance.release.fail` voids the grant and records the reason;
   nothing else is written, so a render failure records nothing (row acceptance).

Activities prove their context from the database (the grant, the report rows), never from the
input alone. The workflow is deterministic: it branches only on activity results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from typing import Final
from uuid import UUID

from temporalio import activity, workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError

with workflow.unsafe.imports_passed_through():
    from abacus.kernel.errors import DomainConflict
    from abacus.modules.assurance import release as rel

_TIMEOUT: Final = timedelta(seconds=60)
_STEP_RETRY: Final = RetryPolicy(maximum_attempts=3, non_retryable_error_types=["ReleaseRefused"])
# The render job usually finishes in seconds; give it two minutes, polling every 2 s.
_RENDER_RETRY: Final = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=1.0,
    maximum_interval=timedelta(seconds=2),
    maximum_attempts=60,
    non_retryable_error_types=["RenderFailed"],
)


@dataclass(frozen=True)
class RenderedFinal:
    final_version_id: str
    evidence_version_id: str
    render_hash: str
    page_count: int


def _refused(error: DomainConflict) -> ApplicationError:
    reason = str(error.facts.get("reason", error.code)) if error.facts else error.code
    return ApplicationError(reason, type="ReleaseRefused", non_retryable=True)


@activity.defn(name="assurance.release.consume_and_render")
async def consume_and_render_activity(request: rel.ReleaseRequest) -> int:
    try:
        return await rel.consume_and_render(request)
    except DomainConflict as refused:
        raise _refused(refused) from None


@activity.defn(name="assurance.release.final_render")
async def final_render_activity(request: rel.ReleaseRequest, version_no: int) -> RenderedFinal:
    outcome = await rel.final_render(request, version_no)
    if outcome.status == "failed":
        raise ApplicationError(
            outcome.failure_code or "render_failed", type="RenderFailed", non_retryable=True
        )
    if (
        outcome.status != "succeeded"
        or outcome.version_id is None
        or outcome.evidence_version_id is None
        or outcome.render_hash is None
        or outcome.page_count is None
    ):
        raise ApplicationError("render_pending", type="RenderPending")  # retried
    return RenderedFinal(
        str(outcome.version_id),
        str(outcome.evidence_version_id),
        outcome.render_hash,
        outcome.page_count,
    )


@activity.defn(name="assurance.release.record")
async def record_activity(request: rel.ReleaseRequest, final: RenderedFinal) -> str:
    try:
        release_id = await rel.record_in_app_release(
            request,
            UUID(final.final_version_id),
            UUID(final.evidence_version_id),
            final.render_hash,
            final.page_count,
        )
    except DomainConflict as refused:
        raise _refused(refused) from None
    return str(release_id)


@activity.defn(name="assurance.release.fail")
async def fail_activity(request: rel.ReleaseRequest, reason: str) -> None:
    await rel.fail_release(request, reason)


def _reason(error: ActivityError) -> str:
    cause = error.cause
    if isinstance(cause, ApplicationError):
        return cause.message[:60] or "release_failed"
    return "release_failed"


@workflow.defn(name="ReleaseWorkflow")
class ReleaseWorkflow:
    """G8 after the EP's decision; on failure nothing but the reason is recorded."""

    @workflow.run
    async def run(self, request: rel.ReleaseRequest) -> str:
        try:
            version_no = await workflow.execute_activity(
                "assurance.release.consume_and_render",
                request,
                result_type=int,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_STEP_RETRY,
            )
            final = await workflow.execute_activity(
                "assurance.release.final_render",
                args=[request, version_no],
                result_type=RenderedFinal,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_RENDER_RETRY,
            )
            return await workflow.execute_activity(
                "assurance.release.record",
                args=[request, final],
                result_type=str,
                start_to_close_timeout=_TIMEOUT,
                retry_policy=_STEP_RETRY,
            )
        except ActivityError as error:
            await workflow.execute_activity(
                "assurance.release.fail",
                args=[request, _reason(error)],
                start_to_close_timeout=_TIMEOUT,
                retry_policy=RetryPolicy(maximum_attempts=5),
            )
            return f"failed:{_reason(error)}"


async def start_release(request: rel.ReleaseRequest) -> str:
    """Dispatch after the request's unit of work committed (one run per decision)."""
    from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

    from abacus.kernel.dispatch import dispatch

    run_id = rel.workflow_id(
        UUID(request.tenant_id), UUID(request.work_item_id), UUID(request.grant_id)
    )
    await dispatch(
        ReleaseWorkflow,
        request,
        id=run_id,
        id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return run_id


WORKFLOWS: Final[dict[type, str]] = {ReleaseWorkflow: "time_sensitive"}
ACTIVITIES: Final[tuple[object, ...]] = (
    consume_and_render_activity,
    final_render_activity,
    record_activity,
    fail_activity,
)

__all__ = ["ACTIVITIES", "WORKFLOWS", "ReleaseWorkflow", "RenderedFinal", "start_release"]
