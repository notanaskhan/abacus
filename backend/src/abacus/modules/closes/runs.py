"""Close runs (C-01-T20; C-01 F3; SPEC-655 AC-28 to AC-31; DEC-50, DEC-57; amber): the CLS-02 run
card over P-10's engagement run with `closes.close_run`'s code plan.

- **Start** (`POST /v1/closes/{id}/runs`): a live person only (an agent principal is refused 403
  at the route, DEC-50: Auto mode stays off for real firms); 409 `run_in_progress` while a run of
  the close is open. The close's plan is pinned on its first run if BD1 has not pinned it
  (QC-2), the close moves Not started → In progress (AC-11), and the run is P-10's
  (`start_engagement_run`, work item `close:<id>`, concurrency 3).
- **History** and **the run card**: runs newest first; each step a procedure row in its task group
  (CLS-02 order), its status word, and the decision step's card on the third-party group.
- **Retry** of a failed procedure: a new run scoped to that step (`task`), so the retry is its own
  row and the failed attempt stays in the history (AC-30).
"""

from __future__ import annotations

from collections import defaultdict
from typing import Final
from uuid import UUID

from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.agents.api import (
    PlanRequest,
    run_step_rows,
    start_engagement_run,
    work_item_runs,
)
from abacus.modules.closes.contract import (
    ClosePersonOut,
    CloseProcedureOut,
    CloseRunHistoryItemOut,
    CloseRunInProgress,
    CloseRunOut,
    CloseRunsOut,
    CloseTaskGroupOut,
    StartRunIn,
    StartRunOut,
)
from abacus.modules.closes.plans import pin_plan
from abacus.modules.closes.run_plan import (
    GROUP_OF,
    GROUPS,
    PROVIDER,
    plan_rows,
    step_key,
    work_item_ref,
)
from abacus.modules.closes.service import refuse_non_human, start_close, visible_close
from abacus.modules.engagements.api import get_ref
from abacus.modules.identity.api import AuthContext, authorise, names_of

START: Final = "close_run.start"
_STEP_STATUS: Final = {
    "queued": "queued",
    "running": "running",
    "waiting_on_inputs": "needs_attention",
    "blocked_on_decision": "needs_attention",
    "succeeded": "done",
    "failed": "failed",
    "cancelled": "failed",
    "skipped": "done",
}
_RUN_STATUS: Final = {
    "queued": "running",
    "running": "running",
    "awaiting_plan_approval": "running",
    "waiting_on_inputs": "needs_input",
    "blocked_on_decision": "needs_input",
    "succeeded": "complete",
    "completed": "complete",
    "completed_with_exceptions": "complete_with_exceptions",
    "failed": "failed",
    "cancelled": "failed",
}


def _keys(body: StartRunIn) -> tuple[str, ...]:
    if body.scope == "group":
        return () if body.group_key is None else (body.group_key,)
    if body.scope == "accounts":
        return tuple(body.account_external_ids)
    return ()


async def start_run(ctx: AuthContext, close_id: UUID, body: StartRunIn) -> StartRunOut:
    # AC-28, INV-1 (S47 end pass): only a live human with `close_run.start` starts a run, checked
    # before the pin or the status change is written.
    await refuse_non_human(ctx, close_id, START)
    close = await visible_close(ctx, close_id)
    await authorise(ctx, START, (await get_ref(ctx, close.engagement_id)).resource())
    ref = work_item_ref(close_id)
    if any(r.active for r in await work_item_runs(ctx.tenant, ref, 5)):
        raise CloseRunInProgress(facts={"close": "run_open"})
    async with uow(ctx.tenant) as tx:
        pinned = await pin_plan(tx.session, close_id)
        await start_close(tx, close_id)
        tx.record(
            "close_run.requested",
            target=Target("close", close_id),
            after=Ref(pinned=int(pinned is not None), scope_keys=len(_keys(body))),
        )
    started = await start_engagement_run(
        ctx,
        close.engagement_id,
        work_item_ref=ref,
        provider=PROVIDER,
        request=PlanRequest(close_id, body.scope, _keys(body)),
    )
    return StartRunOut(run_id=started.run_id, run_no=max(started.run_number, 1))


async def _person(user_id: UUID | None) -> ClosePersonOut:
    if user_id is None:
        return ClosePersonOut(user_id=UUID(int=0), name="Accrued", initials="A")
    name = (await names_of([user_id])).get(user_id, "Unknown")
    initials = "".join(w[0] for w in name.split()[:2]).upper() or "?"
    return ClosePersonOut(user_id=user_id, name=name, initials=initials[:3])


async def run_history(ctx: AuthContext, close_id: UUID) -> CloseRunsOut:
    await visible_close(ctx, close_id)
    runs = await work_item_runs(ctx.tenant, work_item_ref(close_id))
    ready = len(await plan_rows(ctx.tenant, close_id))
    return CloseRunsOut(
        items=[
            CloseRunHistoryItemOut(
                run_id=r.run_id,
                run_no=max(r.run_number, 1),
                status=_RUN_STATUS.get(r.state, "running"),  # pyright: ignore[reportArgumentType] -- a close_run word
                total=len(await run_step_rows(ctx.tenant, r.run_id)),
                started_at=r.created_at,
            )
            for r in runs
        ],
        ready_to_run=ready,
    )


async def run_card(ctx: AuthContext, close_id: UUID, run_no: int) -> CloseRunOut:
    await visible_close(ctx, close_id)  # the caller sees the close (404 otherwise)
    runs = await work_item_runs(ctx.tenant, work_item_ref(close_id))
    found = next((r for r in runs if max(r.run_number, 1) == run_no), None)
    if found is None:
        raise NotFound("close_run")
    newest = runs[0].run_id
    labels = {
        step_key(r): (r.account_name, r.account_external_id, r.procedure)
        for r in await plan_rows(ctx.tenant, close_id)
    }
    grouped: dict[str, list[CloseProcedureOut]] = defaultdict(list)
    done = running = 0
    for step in await run_step_rows(ctx.tenant, found.run_id):
        if step.key is None or step.key not in labels:
            continue
        name, account, procedure = labels[step.key]
        group = GROUP_OF[procedure]
        status = _STEP_STATUS.get(step.state, "queued")
        done += status == "done"
        running += status == "running"
        grouped[group.key].append(
            CloseProcedureOut(
                procedure_id=step.step_id,
                run_step_id=step.step_id,
                label=f"{group.label}: {name}"[:200],
                account_external_id=account,
                status=status,  # pyright: ignore[reportArgumentType] -- a procedure word
                failure=step.error_code,
                retry_of=step.retry_of_step_id,
            )
        )
    groups = [
        CloseTaskGroupOut(key=g.key, label=g.label, procedures=grouped[g.key])
        for g in GROUPS
        if grouped.get(g.key)
    ]
    total = sum(len(g.procedures) for g in groups)
    # C-01-T20 rest (DEC-5432): the newest run reads the close's open exceptions (CLS-06's count,
    # notes excluded), the ones its procedures raised among them; a read-only run keeps 0.
    open_issues = 0
    if found.run_id == newest:
        from abacus.modules.closes.issues import close_issues

        open_issues = (await close_issues(ctx, close_id)).open
    return CloseRunOut(
        run_id=found.run_id,
        run_no=run_no,
        status=_RUN_STATUS.get(found.state, "running"),  # pyright: ignore[reportArgumentType] -- a close_run word
        started_by=await _person(found.initiator_user_id),
        started_at=found.created_at,
        finished_at=found.finished_at,
        done=done,
        total=total,
        running=min(running, 3),
        open_issues=open_issues,
        read_only=found.run_id != newest,
        groups=groups,
    )


async def retry_step(
    ctx: AuthContext, close_id: UUID, run_no: int, step_id: UUID
) -> CloseProcedureOut:
    close = await visible_close(ctx, close_id)
    runs = await work_item_runs(ctx.tenant, work_item_ref(close_id))
    found = next((r for r in runs if max(r.run_number, 1) == run_no), None)
    if found is None:
        raise NotFound("close_run")
    step = next(
        (s for s in await run_step_rows(ctx.tenant, found.run_id) if s.step_id == step_id), None
    )
    if step is None or step.key is None:
        raise NotFound("run_step")
    if step.state != "failed":
        raise CloseRunInProgress(facts={"step": "not_failed"})
    if any(r.active for r in runs):
        raise CloseRunInProgress(facts={"close": "run_open"})
    started = await start_engagement_run(
        ctx,
        close.engagement_id,
        work_item_ref=work_item_ref(close_id),
        provider=PROVIDER,
        request=PlanRequest(close_id, "task", (step.key,)),
    )
    async with uow(ctx.tenant) as tx:
        tx.record(
            "close_procedure.retried",
            target=Target("close", close_id),
            after=Ref(run_id=started.run_id, retry_of=step_id),
        )
    return CloseProcedureOut(
        procedure_id=started.run_id,
        run_step_id=started.run_id,
        label=step.key,
        status="queued",
        retry_of=step_id,
    )


__all__ = ["retry_step", "run_card", "run_history", "start_run"]
