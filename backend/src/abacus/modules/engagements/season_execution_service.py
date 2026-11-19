"""Cohort approval and execution (T-08-T12; S51 partials, TASK-8739; DEC-5730; SPEC-710 AC-5,
AC-6; ADR-161). Dark behind `engagements.season_setup`.

- **Approve** (`season_setup.approve_cohort`: a firm partner or manager, never a firm admin, the
  agent or the system): the person pins the cohort's `rows_hash` and the manifest version they saw
  (409 `stale_version` otherwise); one insert-only approval row and a single-use approval grant
  over the rows hash are written in the same unit; the cohort is `approved` and its execution is
  started after commit (FIFO: a cohort waits behind any earlier approved one still executing).
- **Withdraw**: before any step ran (409 `execution_started`, 0960's trigger behind the service);
  the grant is voided and the cohort is a draft again.
- **Execute** (the workflow's activity): consumes the grant (the single gate; a changed row set
  fails closed), then runs every executable row's steps in order. A step is done once: a row's
  `ok` step is never run again, and a failed step records its attempt and error code. Rows with
  exception codes or excluded rows are skipped. Every record a step creates is the system's on
  behalf of the approver. A step whose owner has not registered an executor is recorded failed
  `step_unavailable`, so the cohort reads failed and can be retried once it has one.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from temporalio import activity
from temporalio.common import WorkflowIDConflictPolicy, WorkflowIDReusePolicy

from abacus.kernel import clock
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.dispatch import dispatch
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements import season_execution as rules
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.repository import insert_engagement
from abacus.modules.engagements.season_execution_workflow import (
    ACTIVITY,
    SeasonExecInput,
    SeasonSetupExecutionWorkflow,
)
from abacus.modules.engagements.season_service import CohortApproved, StaleRow, cohort
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    add_rolled_forward_member,
    authorise,
    consume_grant,
    issue_grant,
    member_context,
    void_grant,
)

ACTION: Final = "season_setup.approve_cohort"
SUBJECT: Final = "season_cohort"
GRANT_TTL: Final = timedelta(days=7)


class ExecutionStarted(DomainConflict):
    code = "execution_started"


class ApprovalGrantMismatch(DomainConflict):
    code = "approval_grant_mismatch"


class RowsHidden(DomainConflict):
    """The approver is walled from a row: they cannot approve what they cannot see."""

    code = "rows_hidden"


@dataclass(frozen=True)
class StepRow:
    """What a step executor reads of one row (identifiers only)."""

    row_id: UUID
    tax_year: int
    client_id: UUID
    client_entity_ids: tuple[UUID, ...]
    forms: tuple[str, ...]
    preparer_user_id: UUID | None
    reviewer_user_id: UUID | None
    signer_user_id: UUID | None
    prior_engagement_id: UUID | None
    engagement_id: UUID | None  # set once the engagement step ran


# An executor runs inside the step's unit of work (system, on behalf of the approver) and answers
# the ids it created; it raises to fail the step (its error code is recorded).
StepExecutor = Callable[[UnitOfWork, AuthContext, StepRow], Awaitable[list[UUID]]]
_executors: dict[str, StepExecutor] = {}


def register_season_step(step: str, executor: StepExecutor) -> None:
    """The module that owns a step's records runs it (tax: returns; requests: the binder; ...)."""
    if step not in rules.STEPS:
        raise ValueError(f"unknown season step {step!r}")
    _executors[step] = executor


def workflow_id(tenant_id: UUID, cohort_id: UUID) -> str:
    return f"season_exec:{tenant_id}:{cohort_id}"


# --- approve and withdraw -----------------------------------------------------------------------

_COHORT = text(
    "SELECT c.status, m.version, m.status FROM season_cohorts c JOIN season_manifests m "
    "ON m.id = c.manifest_id WHERE c.id = :c FOR UPDATE OF c"
)
_APPROVE = text(
    "INSERT INTO season_cohort_approvals (tenant_id, cohort_id, manifest_version, rows_hash, "
    "approval_grant_id, approved_by) VALUES (:t, :c, :v, :h, :g, :u) RETURNING id, approved_at"
)
_MARK = text(
    "UPDATE season_cohorts SET status = :s, approver_user_id = :u WHERE id = :c RETURNING id"
)


@dataclass(frozen=True)
class Approval:
    approval_id: UUID
    cohort_id: UUID
    grant_id: UUID
    approved_by: UUID
    approved_at: object


async def approve_cohort(
    ctx: AuthContext, cohort_id: UUID, *, rows_hash: str, manifest_version: int
) -> Approval:
    await authorise(ctx, ACTION, Resource.firm(ctx.tenant_id))
    seen = await cohort(ctx, cohort_id)  # the reader's view (walls) — what they approve
    if seen.rows_hash != rows_hash:
        raise StaleRow(facts={"cohort_id": str(cohort_id)})
    async with tenant_session(ctx.tenant) as session:
        every = [(cast(UUID, r[0]), int(cast(int, r[1]))) for r in await session.execute(
            _ROW_IDS, {"c": cohort_id})]  # fmt: skip
    if rows_hash_of(every) != rows_hash:
        raise RowsHidden(facts={"cohort_id": str(cohort_id)})
    now = await clock.now(ctx.tenant)
    async with uow(ctx.tenant) as tx:
        found = (await tx.session.execute(_COHORT, {"c": cohort_id})).first()
        if found is None:
            raise NotFound(SUBJECT)
        if found[0] != "draft" or found[2] != "ready":
            raise CohortApproved(facts={"cohort_id": str(cohort_id)})
        if int(cast(int, found[1])) != manifest_version:
            raise StaleRow(facts={"cohort_id": str(cohort_id)})
        grant = await issue_grant(
            tx,
            ctx,
            action=ACTION,
            resource=Resource.firm(ctx.tenant_id),
            subject=Target(SUBJECT, cohort_id),
            payload_sha256=rows_hash,
            not_before=now,
            expires_at=now + GRANT_TTL,
        )
        row = (
            await tx.session.execute(
                _APPROVE,
                {"t": ctx.tenant_id, "c": cohort_id, "v": manifest_version, "h": rows_hash,
                 "g": grant, "u": ctx.user_id},
            )
        ).one()  # fmt: skip
        await tx.session.execute(_MARK, {"s": "approved", "u": ctx.user_id, "c": cohort_id})
        tx.record(
            "season_cohort.approved",
            target=Target(SUBJECT, cohort_id),
            after=Ref(version=manifest_version),
        )
    await dispatch(
        SeasonSetupExecutionWorkflow,
        SeasonExecInput(str(ctx.tenant_id), str(cohort_id)),
        id=workflow_id(ctx.tenant_id, cohort_id),
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )
    return Approval(cast(UUID, row[0]), cohort_id, grant, ctx.user_id, row[1])


_LIVE_APPROVAL = text(
    "SELECT a.id, a.approval_grant_id FROM season_cohort_approvals a WHERE a.cohort_id = :c "
    "AND NOT EXISTS (SELECT 1 FROM season_cohort_withdrawals w WHERE w.approval_id = a.id) "
    "ORDER BY a.approved_at DESC LIMIT 1"
)
_STARTED = text(
    "SELECT EXISTS (SELECT 1 FROM season_row_steps s JOIN season_manifest_rows r "
    "ON r.id = s.row_id WHERE r.cohort_id = :c)"
)
_WITHDRAW = text(
    "INSERT INTO season_cohort_withdrawals (tenant_id, approval_id, reason, withdrawn_by) "
    "VALUES (:t, :a, :r, :u)"
)


async def withdraw_cohort(ctx: AuthContext, cohort_id: UUID, reason: str) -> None:
    await authorise(ctx, ACTION, Resource.firm(ctx.tenant_id))
    await cohort(ctx, cohort_id)
    async with uow(ctx.tenant) as tx:
        found = (await tx.session.execute(_COHORT, {"c": cohort_id})).first()
        live = (await tx.session.execute(_LIVE_APPROVAL, {"c": cohort_id})).first()
        if found is None or live is None:
            raise NotFound("season_cohort_approval")
        if found[0] != "approved" or await tx.session.scalar(_STARTED, {"c": cohort_id}):
            raise ExecutionStarted(facts={"cohort_id": str(cohort_id)})
        await tx.session.execute(
            _WITHDRAW, {"t": ctx.tenant_id, "a": live[0], "r": reason.strip(), "u": ctx.user_id}
        )
        await void_grant(tx, cast(UUID, live[1]))
        await tx.session.execute(_MARK, {"s": "draft", "u": None, "c": cohort_id})
        tx.record("season_cohort.withdrawn", target=Target(SUBJECT, cohort_id))


# --- execute -------------------------------------------------------------------------------------

_EXEC_COHORT = text(
    "SELECT c.status, s.tax_year, a.approval_grant_id, a.rows_hash, a.approved_by "
    "FROM season_cohorts c JOIN season_manifests m ON m.id = c.manifest_id "
    "JOIN seasons s ON s.id = m.season_id JOIN season_cohort_approvals a ON a.cohort_id = c.id "
    "WHERE c.id = :c AND NOT EXISTS (SELECT 1 FROM season_cohort_withdrawals w "
    "WHERE w.approval_id = a.id) ORDER BY a.approved_at DESC LIMIT 1"
)
_ROW_IDS = text(
    "SELECT id, row_version FROM season_manifest_rows WHERE cohort_id = :c ORDER BY id"
)
_EXEC_ROWS = text(
    "SELECT id, client_id, client_entity_ids, forms, preparer_user_id, reviewer_user_id, "
    "signer_user_id, prior_engagement_id FROM season_manifest_rows WHERE cohort_id = :c "
    "AND excluded_at IS NULL AND cardinality(exception_codes) = 0 ORDER BY id"
)
_STEPS_OF = text(
    "SELECT step, status, attempt, ref_ids FROM season_row_steps WHERE row_id = :r "
    "ORDER BY step, attempt"
)
_STEP = text(
    "INSERT INTO season_row_steps (tenant_id, row_id, step, attempt, status, ref_ids, error_code) "
    "VALUES (:t, :r, :s, :a, :st, :refs, :e)"
)
_STATUS = text("UPDATE season_cohorts SET status = :s WHERE id = :c")
_EARLIER = text(
    "SELECT EXISTS (SELECT 1 FROM season_cohorts o JOIN season_cohort_approvals a "
    "ON a.cohort_id = o.id WHERE o.manifest_id = (SELECT manifest_id FROM season_cohorts "
    "WHERE id = :c) AND o.id <> :c AND o.status = 'executing' AND a.approved_at < "
    "(SELECT max(approved_at) FROM season_cohort_approvals WHERE cohort_id = :c))"
)


class EarlierCohortRunning(Exception):
    """FIFO: an earlier approved cohort is still executing; the activity retries."""


def rows_hash_of(rows: list[tuple[UUID, int]]) -> str:
    import hashlib

    body = ",".join(f"{r}:{v}" for r, v in sorted(rows, key=lambda x: str(x[0])))
    return hashlib.sha256(body.encode()).hexdigest()


async def execute_cohort(tenant_id: UUID, cohort_id: UUID) -> str:
    """The cohort's steps, once each; answers the cohort's status."""
    system = TenantContext(tenant_id, "system", f"season_exec:{cohort_id}")
    async with tenant_session(system) as session:
        found = (await session.execute(_EXEC_COHORT, {"c": cohort_id})).first()
        row_ids = [(cast(UUID, r[0]), int(cast(int, r[1]))) for r in await session.execute(
            _ROW_IDS, {"c": cohort_id})]  # fmt: skip
        if await session.scalar(_EARLIER, {"c": cohort_id}):
            raise EarlierCohortRunning
    if found is None:
        raise NotFound(SUBJECT)
    if found[0] in ("executed",):
        return str(found[0])
    approver = cast(UUID, found[4])
    if (
        not await consume_grant(tenant_id, cast(UUID, found[2]), cohort_id, rows_hash_of(row_ids))
        or rows_hash_of(row_ids) != found[3]
    ):
        raise ApprovalGrantMismatch(facts={"cohort_id": str(cohort_id)})
    approver_ctx = await member_context(tenant_id, approver)
    if approver_ctx is None:
        raise ApprovalGrantMismatch(facts={"cohort_id": str(cohort_id)})
    acting = TenantContext(tenant_id, "system", system.actor_id, on_behalf_of_user_id=approver)
    if found[0] == "approved":
        async with uow(acting) as tx:
            await tx.session.execute(_STATUS, {"s": "executing", "c": cohort_id})
            tx.record("season_cohort.executing", target=Target(SUBJECT, cohort_id))
    tax_year = int(cast(int, found[1]))
    async with tenant_session(acting) as session:
        rows = [tuple(r) for r in await session.execute(_EXEC_ROWS, {"c": cohort_id})]
    failed = False
    for r in rows:
        if activity.in_activity():
            activity.heartbeat(str(r[0]))
        failed |= not await _run_row(acting, approver_ctx, tax_year, r)
    status = "failed" if failed else "executed"
    async with uow(acting) as tx:
        await tx.session.execute(_STATUS, {"s": status, "c": cohort_id})
        tx.record(f"season_cohort.{status}", target=Target(SUBJECT, cohort_id))
    return status


async def _run_row(
    acting: TenantContext, approver: AuthContext, tax_year: int, r: tuple[object, ...]
) -> bool:
    row_id = cast(UUID, r[0])
    async with tenant_session(acting) as session:
        history = [tuple(s) for s in await session.execute(_STEPS_OF, {"r": row_id})]
    done = {str(s[0]): list(cast(list[UUID], s[3])) for s in history if s[1] == "ok"}
    attempts = {str(s[0]): int(cast(int, s[2])) for s in history}
    engagement = (done.get("engagement") or [None])[0]
    for step in rules.STEPS:
        if step in done:
            continue
        view = StepRow(
            row_id, tax_year, cast(UUID, r[1]), tuple(cast(list[UUID], r[2])),
            tuple(cast(list[str], r[3])), cast(UUID | None, r[4]), cast(UUID | None, r[5]),
            cast(UUID | None, r[6]), cast(UUID | None, r[7]), engagement,
        )  # fmt: skip
        attempt = attempts.get(step, 0) + 1
        executor = _executors.get(step)
        try:
            async with uow(acting) as tx:
                if executor is None:
                    raise _StepFailed("step_unavailable")
                refs = await executor(tx, approver, view)
                await tx.session.execute(
                    _STEP,
                    {"t": acting.tenant_id, "r": row_id, "s": step, "a": attempt, "st": "ok",
                     "refs": refs, "e": None},
                )  # fmt: skip
                tx.record(
                    "season_row.step_done",
                    target=Target("season_manifest_row", row_id),
                    after=Ref(attempt=attempt),
                )
            if step == "engagement" and refs:
                engagement = refs[0]
        except Exception as exc:
            code = exc.code if isinstance(exc, _StepFailed) else _code_of(exc)
            async with uow(acting) as tx:
                await tx.session.execute(
                    _STEP,
                    {"t": acting.tenant_id, "r": row_id, "s": step, "a": attempt,
                     "st": "failed", "refs": [], "e": code},
                )  # fmt: skip
                tx.record(
                    "season_row.step_failed",
                    target=Target("season_manifest_row", row_id),
                    after=Ref(attempt=attempt),
                )
            return False
    return True


class _StepFailed(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _code_of(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if isinstance(code, str) and code.replace("_", "").isalnum() and code[:1].isalpha():
        return code.lower()[:60]
    return "step_failed"


@activity.defn(name=ACTIVITY)
async def execute_cohort_activity(given: SeasonExecInput) -> str:
    return await execute_cohort(UUID(given.tenant_id), UUID(given.cohort_id))


# --- the steps engagements owns ------------------------------------------------------------------

_ROLES: Final = (("signer_user_id", "engagement_partner"), ("preparer_user_id", "senior"),
                 ("reviewer_user_id", "reviewer"))  # fmt: skip


async def _engagement_step(tx: UnitOfWork, approver: AuthContext, row: StepRow) -> list[UUID]:
    """The season's tax engagement for the client's first entity, rolled from last year's."""
    if not row.client_entity_ids:
        raise _StepFailed("entity_missing")
    engagement_id = uuid4()
    await insert_engagement(
        tx.session,
        engagement_id=engagement_id,
        tenant_id=approver.tenant_id,
        client_id=row.client_id,
        client_entity_id=row.client_entity_ids[0],
        name=f"{row.tax_year - 1} tax returns",
        fiscal_period_start=date(row.tax_year - 1, 1, 1),
        fiscal_period_end=date(row.tax_year - 1, 12, 31),
        created_by=approver.user_id,
        type="tax_compliance",
        prior_engagement_id=row.prior_engagement_id,
    )
    tx.record(
        "engagement.created",
        target=Target("engagement", engagement_id),
        scope=Scope(engagement_id=engagement_id),
    )
    tx.emit(EngagementCreated(engagement_id=engagement_id))
    return [engagement_id]


async def _assignments_step(tx: UnitOfWork, approver: AuthContext, row: StepRow) -> list[UUID]:
    """The carried people join the engagement (each re-checked: active, not walled, consent)."""
    if row.engagement_id is None:
        raise _StepFailed("engagement_missing")
    added: list[UUID] = []
    for attr, role in _ROLES:
        person = cast(UUID | None, getattr(row, attr))
        if person is None or person in added:
            continue
        await add_rolled_forward_member(
            tx,
            approver,
            row.engagement_id,
            row.client_id,
            person,
            role,  # pyright: ignore[reportArgumentType] -- a staff role literal
        )
        added.append(person)
    return added


register_season_step("engagement", _engagement_step)
register_season_step("assignments", _assignments_step)

__all__ = [
    "ACTION",
    "Approval",
    "ApprovalGrantMismatch",
    "ExecutionStarted",
    "RowsHidden",
    "StepExecutor",
    "StepRow",
    "approve_cohort",
    "execute_cohort",
    "execute_cohort_activity",
    "register_season_step",
    "rows_hash_of",
    "withdraw_cohort",
    "workflow_id",
]
