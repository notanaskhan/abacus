"""The screening workflow (ADR-017, ADR-090). PROTECTED. TASK-011 design §7.

Started by the relay for each `evidence_version.created`
(`screening:<tenant_id>:<evidence_version_id>`).
Orchestration only: activities by name, identifiers in and out, no I/O (WF-001). Steps:
create the agent run (none: `skipped`), then screen it as one activity. Any failure,
cancellation included, ends in `screening.fail_run`, which retries until it succeeds, so a run
never stays `running` because of the workflow. Changes are guarded with `workflow.patched(...)`.
Q-02-T41 (`run_record_v1`): once a run has ended, each specialist workflow persists its run record
(`agents.persist_run_record`) before releasing its slot.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy
from temporalio.exceptions import ActivityError, ApplicationError, is_cancelled_exception
from temporalio.workflow import ActivityCancellationType

with workflow.unsafe.imports_passed_through():
    from abacus.modules.agents.workflow_types import (
        CANCELLED,
        CAPACITY_TIMEOUT,
        INTERNAL_ERROR,
        NOT_ADMITTED,
        PROVIDER_UNAVAILABLE,
        EntryAssessInput,
        EntryAssessRunInput,
        FailInput,
        GuidanceDraftInput,
        GuidanceDraftRunInput,
        MatchInput,
        MatchRunInput,
        RunInput,
        ScreeningInput,
        ScreeningOutcome,
        SlotGrant,
    )

_TIMEOUT = timedelta(minutes=2)
# Screening may call the model twice (call and repair), each bounded by the spec's `max_seconds`
# (60): 5 minutes leaves room for the database work. The activity heartbeats, so a timed-out
# attempt is cancelled before its retry starts (no two attempts spend the run's budget at once).
_SCREEN_TIMEOUT = timedelta(minutes=5)
_SCREEN_HEARTBEAT = timedelta(seconds=30)
_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=4,
)
_FAIL_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=0,
)
# SPEC-003: ask for a slot at least this often; release a few times, then leave it to the lease.
_MAX_ASK_INTERVAL = 60.0  # also bounds slot lease renewal (15 min): never raise past ~5 min
_MIN_ADMISSION_ASK = 5.0
_RELEASE_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=5,
)
_RELEASE_WITHIN = timedelta(hours=1)
_UNAVAILABLE = frozenset({"ProviderError"})
# Q-02-T41 (ADR-169 §3): every specialist workflow persists its run's record once it has ended.
RUN_RECORD_PATCH = "run_record_v1"
_PERSIST_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=2.0,
    maximum_interval=timedelta(minutes=1),
    maximum_attempts=10,
)


@workflow.defn(name="screening")
class ScreeningWorkflow:
    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "screening.create_run",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        run = RunInput(input.tenant_id, run_id)
        # SPEC-003: hold a work slot of the run's class while it screens (TASK-018 design §4).
        slotted = workflow.patched("work-slots")
        # The class's maximum wait covers the whole wait, for a slot and then for admission.
        waiting_from = workflow.now()
        try:
            if slotted and not await wait_for_slot("screening.acquire_slot", run):
                return await _fail(run, CAPACITY_TIMEOUT)
            # SPEC-003 AC-11: a model call not admitted waits (durably) and screens again.
            admission = workflow.patched("admission")
            backoff = _MIN_ADMISSION_ASK
            while True:
                try:
                    outcome = await workflow.execute_activity(
                        "screening.screen",
                        run,
                        result_type=ScreeningOutcome,
                        start_to_close_timeout=_SCREEN_TIMEOUT,
                        heartbeat_timeout=_SCREEN_HEARTBEAT,
                        retry_policy=_RETRY,
                    )
                    await _persist(run)  # Q-02-T41: after the terminal state
                    return outcome
                except ActivityError as err:
                    refused = _not_admitted(err) if admission else None
                    if refused is None:
                        raise
                    retry_after, max_wait = refused
                    if (workflow.now() - waiting_from).total_seconds() >= max_wait:
                        return await _fail(run, CAPACITY_TIMEOUT)
                    # At least what the bucket asked for, backing off per refusal; at most 60 s,
                    # which also keeps the slot's 15-minute lease renewed (each ask renews it).
                    delay = max(retry_after, backoff) * (0.5 + workflow.random().random())
                    await workflow.sleep(timedelta(seconds=min(delay, _MAX_ASK_INTERVAL)))
                    backoff = min(backoff * 2, _MAX_ASK_INTERVAL)
        except ActivityError as err:
            if is_cancelled_exception(err):
                await _fail(run, CANCELLED)
                raise asyncio.CancelledError from err
            return await _fail(run, _code(err))
        except asyncio.CancelledError:
            await _fail(run, CANCELLED)
            raise
        finally:
            if slotted:
                await _release("screening.release_slot", run)


def _not_admitted(err: ActivityError) -> tuple[float, float] | None:
    """(retry_after, max_wait) seconds if the screen wasn't admitted; None for any other error."""
    cause = err.cause
    if not isinstance(cause, ApplicationError) or cause.type != NOT_ADMITTED:
        return None
    details = cause.details
    retry_after = float(str(details[1])) if len(details) >= 2 else 30.0
    max_wait = float(str(details[2])) if len(details) >= 3 else 600.0
    return retry_after, max_wait


async def _fail(run: RunInput, code: str) -> ScreeningOutcome:
    outcome = await workflow.execute_activity(
        "screening.fail_run",
        FailInput(run.tenant_id, run.run_id, code),
        result_type=ScreeningOutcome,
        start_to_close_timeout=_TIMEOUT,
        retry_policy=_FAIL_RETRY,
    )
    await _persist(run)  # Q-02-T41: a failed or cancelled run gets its record too
    return outcome


async def _persist(run: RunInput) -> None:
    """Q-02-T41 (ADR-169 §3): persist the ended run's record, behind `run_record_v1` so the
    histories recorded before it still replay. Repeat-safe; a run still running gets none. A
    record that can't be written within the hour never changes the run's outcome: the run row
    keeps everything a later persist needs."""
    if not workflow.patched(RUN_RECORD_PATCH):
        return
    try:
        await workflow.execute_activity(
            "agents.persist_run_record",
            run,
            start_to_close_timeout=_TIMEOUT,
            schedule_to_close_timeout=_RELEASE_WITHIN,
            retry_policy=_PERSIST_RETRY,
        )
    except ActivityError:
        return


def _code(err: ActivityError) -> str:
    cause = err.cause
    if isinstance(cause, ApplicationError) and cause.type in _UNAVAILABLE:
        return PROVIDER_UNAVAILABLE
    return INTERNAL_ERROR


async def wait_for_slot(activity: str, arg: object) -> bool:
    """SPEC-003 (TASK-018 design §4, D2): ask `activity` for the run's work slot until granted
    (True), or until the class's maximum wait has passed (False). Between asks the workflow
    sleeps on a durable timer with jittered backoff (capped at 60 s, so at most 90 s between asks,
    well inside the 3 minutes after which the ledger stops counting a silent waiter). Waiting holds
    no worker slot and survives deploys. The same loop is in the other module's workflows: ADR-017
    keeps workflows from sharing code outside their module, and a test keeps the two identical."""
    started = workflow.now()
    delay = 1.0
    while True:
        grant = await workflow.execute_activity(
            activity,
            arg,
            result_type=SlotGrant,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
            # A cancelled workflow waits for an ask in flight, so the release comes after it.
            cancellation_type=ActivityCancellationType.WAIT_CANCELLATION_COMPLETED,
        )
        if grant.granted:
            return True
        if (workflow.now() - started).total_seconds() >= grant.max_wait_seconds:
            return False
        await workflow.sleep(timedelta(seconds=delay * (0.5 + workflow.random().random())))
        delay = min(delay * 2, _MAX_ASK_INTERVAL)


async def _release(activity: str, arg: object) -> None:
    """Free the run's slot, a bounded number of times: if the ledger is unreachable the lease
    reclaims the slot anyway, and a failed release never changes the run's outcome."""
    try:
        await workflow.execute_activity(
            activity,
            arg,
            start_to_close_timeout=_TIMEOUT,
            schedule_to_close_timeout=_RELEASE_WITHIN,
            retry_policy=_RELEASE_RETRY,
        )
    except ActivityError:
        return  # the lease reclaims the slot


@workflow.defn(name="upload_review")
class UploadReviewWorkflow:
    """SPEC-030 (TASK-059): one upload reviewer run: create it, hold a work slot, review (waiting
    when not admitted), and always end a failed run. The slot and fail activities are the
    screener's: they work on any agent run."""

    @workflow.run
    async def run(self, input: ScreeningInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "upload_review.create_run",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        run = RunInput(input.tenant_id, run_id)
        waiting_from = workflow.now()
        try:
            if not await wait_for_slot("screening.acquire_slot", run):
                return await _fail(run, CAPACITY_TIMEOUT)
            backoff = _MIN_ADMISSION_ASK
            while True:
                try:
                    outcome = await workflow.execute_activity(
                        "upload_review.review",
                        run,
                        result_type=ScreeningOutcome,
                        start_to_close_timeout=_SCREEN_TIMEOUT,
                        heartbeat_timeout=_SCREEN_HEARTBEAT,
                        retry_policy=_RETRY,
                    )
                    await _persist(run)  # Q-02-T41: after the terminal state
                    return outcome
                except ActivityError as err:
                    refused = _not_admitted(err)
                    if refused is None:
                        raise
                    retry_after, max_wait = refused
                    if (workflow.now() - waiting_from).total_seconds() >= max_wait:
                        return await _fail(run, CAPACITY_TIMEOUT)
                    delay = max(retry_after, backoff) * (0.5 + workflow.random().random())
                    await workflow.sleep(timedelta(seconds=min(delay, _MAX_ASK_INTERVAL)))
                    backoff = min(backoff * 2, _MAX_ASK_INTERVAL)
        except ActivityError as err:
            if is_cancelled_exception(err):
                await _fail(run, CANCELLED)
                raise asyncio.CancelledError from err
            return await _fail(run, _code(err))
        except asyncio.CancelledError:
            await _fail(run, CANCELLED)
            raise
        finally:
            await _release("screening.release_slot", run)


@workflow.defn(name="inbox_match")
class InboxMatchWorkflow:
    """SPEC-033 (TASK-066): one matcher run on an inbox file: create it, hold a work slot, match
    (waiting when not admitted), and always end a failed run. Slot and fail activities are the
    screener's: they work on any agent run."""

    @workflow.run
    async def run(self, input: MatchInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "inbox_match.create_run",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        run = RunInput(input.tenant_id, run_id)
        given = MatchRunInput(input.tenant_id, run_id, input.inbox_file_id)
        waiting_from = workflow.now()
        try:
            if not await wait_for_slot("screening.acquire_slot", run):
                return await _fail(run, CAPACITY_TIMEOUT)
            backoff = _MIN_ADMISSION_ASK
            while True:
                try:
                    outcome = await workflow.execute_activity(
                        "inbox_match.match",
                        given,
                        result_type=ScreeningOutcome,
                        start_to_close_timeout=_SCREEN_TIMEOUT,
                        heartbeat_timeout=_SCREEN_HEARTBEAT,
                        retry_policy=_RETRY,
                    )
                    await _persist(run)  # Q-02-T41: after the terminal state
                    return outcome
                except ActivityError as err:
                    refused = _not_admitted(err)
                    if refused is None:
                        raise
                    retry_after, max_wait = refused
                    if (workflow.now() - waiting_from).total_seconds() >= max_wait:
                        return await _fail(run, CAPACITY_TIMEOUT)
                    delay = max(retry_after, backoff) * (0.5 + workflow.random().random())
                    await workflow.sleep(timedelta(seconds=min(delay, _MAX_ASK_INTERVAL)))
                    backoff = min(backoff * 2, _MAX_ASK_INTERVAL)
        except ActivityError as err:
            if is_cancelled_exception(err):
                await _fail(run, CANCELLED)
                raise asyncio.CancelledError from err
            return await _fail(run, _code(err))
        except asyncio.CancelledError:
            await _fail(run, CANCELLED)
            raise
        finally:
            await _release("screening.release_slot", run)


@workflow.defn(name="guidance_draft")
class GuidanceDraftWorkflow:
    """SPEC-035 (TASK-073): one guidance drafter run on a request item, or a template item
    (TASK-074: firm-level, no work slot): create it, hold a work slot, draft (waiting when not
    admitted), and always end a failed run. Slot and fail activities are the screener's."""

    @workflow.run
    async def run(self, input: GuidanceDraftInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "guidance_draft.create_run",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        run = RunInput(input.tenant_id, run_id)
        given = GuidanceDraftRunInput(
            input.tenant_id, run_id, input.request_item_id, input.position
        )
        waiting_from = workflow.now()
        try:
            if not await wait_for_slot("screening.acquire_slot", run):
                return await _fail(run, CAPACITY_TIMEOUT)
            backoff = _MIN_ADMISSION_ASK
            while True:
                try:
                    outcome = await workflow.execute_activity(
                        "guidance_draft.draft",
                        given,
                        result_type=ScreeningOutcome,
                        start_to_close_timeout=_SCREEN_TIMEOUT,
                        heartbeat_timeout=_SCREEN_HEARTBEAT,
                        retry_policy=_RETRY,
                    )
                    await _persist(run)  # Q-02-T41: after the terminal state
                    return outcome
                except ActivityError as err:
                    refused = _not_admitted(err)
                    if refused is None:
                        raise
                    retry_after, max_wait = refused
                    if (workflow.now() - waiting_from).total_seconds() >= max_wait:
                        return await _fail(run, CAPACITY_TIMEOUT)
                    delay = max(retry_after, backoff) * (0.5 + workflow.random().random())
                    await workflow.sleep(timedelta(seconds=min(delay, _MAX_ASK_INTERVAL)))
                    backoff = min(backoff * 2, _MAX_ASK_INTERVAL)
        except ActivityError as err:
            if is_cancelled_exception(err):
                await _fail(run, CANCELLED)
                raise asyncio.CancelledError from err
            return await _fail(run, _code(err))
        except asyncio.CancelledError:
            await _fail(run, CANCELLED)
            raise
        finally:
            await _release("screening.release_slot", run)


@workflow.defn(name="entry_assess")
class EntryAssessWorkflow:
    """SPEC-037 Q4 (TASK-085): one entry assessor run on a selected entry: create it, hold a work
    slot, assess (waiting when not admitted), and always end a failed run. Slot and fail
    activities are the screener's."""

    @workflow.run
    async def run(self, input: EntryAssessInput) -> ScreeningOutcome:
        run_id = await workflow.execute_activity(
            "entry_assess.create_run",
            input,
            result_type=str,
            start_to_close_timeout=_TIMEOUT,
            retry_policy=_RETRY,
        )
        if not run_id:
            return ScreeningOutcome("skipped")
        run = RunInput(input.tenant_id, run_id)
        given = EntryAssessRunInput(input.tenant_id, run_id, input.selected_item_id)
        waiting_from = workflow.now()
        try:
            if not await wait_for_slot("screening.acquire_slot", run):
                return await _fail(run, CAPACITY_TIMEOUT)
            backoff = _MIN_ADMISSION_ASK
            while True:
                try:
                    outcome = await workflow.execute_activity(
                        "entry_assess.assess",
                        given,
                        result_type=ScreeningOutcome,
                        start_to_close_timeout=_SCREEN_TIMEOUT,
                        heartbeat_timeout=_SCREEN_HEARTBEAT,
                        retry_policy=_RETRY,
                    )
                    await _persist(run)  # Q-02-T41: after the terminal state
                    return outcome
                except ActivityError as err:
                    refused = _not_admitted(err)
                    if refused is None:
                        raise
                    retry_after, max_wait = refused
                    if (workflow.now() - waiting_from).total_seconds() >= max_wait:
                        return await _fail(run, CAPACITY_TIMEOUT)
                    delay = max(retry_after, backoff) * (0.5 + workflow.random().random())
                    await workflow.sleep(timedelta(seconds=min(delay, _MAX_ASK_INTERVAL)))
                    backoff = min(backoff * 2, _MAX_ASK_INTERVAL)
        except ActivityError as err:
            if is_cancelled_exception(err):
                await _fail(run, CANCELLED)
                raise asyncio.CancelledError from err
            return await _fail(run, _code(err))
        except asyncio.CancelledError:
            await _fail(run, CANCELLED)
            raise
        finally:
            await _release("screening.release_slot", run)
