"""The close record (C-01-T14; TASK-8032; SPEC-655 AC-1 to AC-13): the kind's twelve closes, the
status machine, assignments, the portfolio and the record's summary.

- **Generate** (AC-13): a `cas_monthly_close` engagement gets one close per month of the year,
  each a `close` work item with its subtype row; BD1 (requests publish) and the due date come
  from practice's business-day calendar and the plan's close-due business day (default BD7).
  A 13th for a period that exists answers 409 `work_item_exists`.
- **Reconciled** (AC-2): an account of the plan counts when its procedure ties (the newest
  reconciliation reads tie or reconciled; a schedule reads tie or recorded; any other procedure's
  newest step is done with nothing open), its required L1 sign-off is current, and no open issue
  hangs on its reconciling items. Code computes it; nothing is stored.
- **Status** (AC-9 to AC-12, DF-23): Not started → In progress is the system's (the first run or
  incorporation, `start_close`); In review needs every plan account reconciled (409
  `accounts_not_reconciled` naming the first missing account) and no run in progress (409
  `run_in_progress`); back to In progress is the preparer's; Approved, Delivered and Locked run
  C-02's registered guard or fail closed (409 `transition_not_available`). On hold is a side
  flag with a required reason. Every move is a live human's (INV-1: an agent is refused and the
  refusal audited), If-Match on the close's row version (409 `stale_version`).
- **Past due** (AC-3, QC-7): firm business days after `due_on`, until Delivered.
- **Visibility** (AC-4, INV-3): every read filters the `close` work items by `visible()` on
  `close.read`, so a walled close is absent from rows, tiles and the summary line, and its record
  answers 404.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, cast
from uuid import UUID

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.closes import repository as repo
from abacus.modules.closes.business_days import add_business_days, business_days_between
from abacus.modules.closes.contract import (
    AccountsNotReconciled,
    AssigneesIn,
    CloseAction,
    CloseFacts,
    CloseListOut,
    ClosePersonOut,
    ClosePortalBlockOut,
    CloseRowOut,
    CloseRunInProgress,
    CloseStatus,
    CloseSummaryLineOut,
    CloseSummaryOut,
    CloseTilesOut,
    PlannedLinkOut,
    RunningCloseOut,
    RunningClosesOut,
    StatusMoveIn,
    TransitionNotAvailable,
    status_guard,
)
from abacus.modules.closes.events import CloseStatusChanged
from abacus.modules.engagements.api import (
    WorkItemExists,
    WorkItemFacts,
    create_work_item,
    engagement_label,
    engagement_type_of,
    entity_of,
    get_ref,
    reassign_work_item,
    work_item_facts,
)
from abacus.modules.identity.api import AuthContext, Forbidden, authorise, names_of
from abacus.modules.requests.api import binder_document_counts, pending_request_counts
from abacus.modules.review.api import open_issue_counts, open_issues_among, sign_off_states

KIND: Final = "close"
ENGAGEMENT_TYPE: Final = "cas_monthly_close"
READ: Final = "close.read"
MOVE: Final = "close.status_move"
ASSIGN: Final = "close.assign"
DEFAULT_DUE_BUSINESS_DAY: Final = 7
_MONTHS: Final = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)
_TIED_RECONCILIATION: Final = frozenset({"tie", "reconciled"})
_TIED_SCHEDULE: Final = frozenset({"tie", "recorded"})
_FINISHED: Final = frozenset({"delivered", "locked"})
# DV-9, QC-6: Approved counts under In review, Locked under Delivered.
_TILE: Final = {"approved": "in_review", "locked": "delivered"}


class StaleClose(DomainConflict):
    """`If-Match` names another version of the close than the current one (ADR-139: 409)."""

    code = "stale_version"


class NotMonthlyClose(DomainInvalid):
    """Closes are generated only for a `cas_monthly_close` engagement."""

    code = "not_monthly_close"


class OnHoldReasonRequired(DomainInvalid):
    code = "on_hold_reason_required"


# --- generate (AC-13) ---------------------------------------------------------------------------


def _period(year: int, month: int) -> str:
    return f"{year:04d}-{month:02d}"


async def _schedule(year: int, month: int, due_business_day: int) -> tuple[date, date]:
    """BD1 and the due date: business days counted from the period's last day."""
    first_next = date(year + (month == 12), month % 12 + 1, 1)
    month_end = date.fromordinal(first_next.toordinal() - 1)
    return (
        await add_business_days(month_end, 1),
        await add_business_days(month_end, due_business_day),
    )


async def generate_closes(ctx: AuthContext, engagement_id: UUID, year: int) -> list[UUID]:
    """Twelve closes YYYY-01…YYYY-12, one work item each (AC-13). A period that exists answers
    409 `work_item_exists`: the generator never writes a second close for a month."""
    if await engagement_type_of(ctx.tenant, engagement_id) != ENGAGEMENT_TYPE:
        raise NotMonthlyClose(facts={"engagement_type": "not cas_monthly_close"})
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "close.create", ref.resource())
    entity = await entity_of(ctx.tenant, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        existing = await repo.periods_of(session, engagement_id)
    created: list[UUID] = []
    for month in range(1, 13):
        period = _period(year, month)
        if period in existing:
            continue
        publish_on, due_on = await _schedule(year, month, DEFAULT_DUE_BUSINESS_DAY)
        created.append(
            await create_work_item(
                ctx,
                engagement_id,
                KIND,
                name=f"{_MONTHS[month - 1]} {year} Close",
                client_entity_id=entity,
                due_on=due_on,
                details={
                    "period": period,
                    "requests_publish_on": publish_on,
                    "due_on": due_on,
                },
            )
        )
    if not created and existing:
        raise WorkItemExists(facts={"kind": KIND})
    return created


# --- reconciled accounts (AC-2) -----------------------------------------------------------------


@dataclass(frozen=True)
class Reconciled:
    reconciled: int
    total: int
    missing: tuple[UUID, ...]  # the plan rows not yet tied, plan order (ids: facts never name)

    @property
    def pct(self) -> int:
        if self.total == 0:
            return 0
        return (self.reconciled * 200 + self.total) // (self.total * 2)  # half up


async def reconciled_facts(
    tenant: TenantContext, closes: Sequence[repo.CloseRow]
) -> tuple[dict[UUID, Reconciled], frozenset[UUID], dict[UUID, int]]:
    """Per close: the reconciled count, which closes have a run in progress, and the plan
    version number each reads (the pinned one, or the one it would pin)."""
    async with tenant_session(tenant) as session:
        pinned = {c.work_item_id: c.close_plan_version_id for c in closes}
        numbers = await repo.plan_versions(session, [v for v in pinned.values() if v])
        unpinned: dict[str, list[UUID]] = {}
        for c in closes:
            if c.close_plan_version_id is None and c.client_entity_id is not None:
                unpinned.setdefault(c.period, []).append(c.client_entity_id)
        effective: dict[tuple[UUID, str], tuple[UUID, int]] = {}
        for period, entities in unpinned.items():
            for entity, found in (
                await repo.effective_versions(session, entities, period)
            ).items():
                effective[(entity, period)] = found
        version_of: dict[UUID, UUID | None] = {}
        number_of: dict[UUID, int] = {}
        for c in closes:
            if c.close_plan_version_id is not None:
                version_of[c.work_item_id] = c.close_plan_version_id
                number_of[c.work_item_id] = numbers.get(c.close_plan_version_id, 0)
            elif c.client_entity_id is not None and (c.client_entity_id, c.period) in effective:
                vid, number = effective[(c.client_entity_id, c.period)]
                version_of[c.work_item_id], number_of[c.work_item_id] = vid, number
            else:
                version_of[c.work_item_id] = None
        accounts = await repo.plan_accounts(session, [v for v in version_of.values() if v])
        done = await repo.computed(session, [c.work_item_id for c in closes])
    recs = list(done.reconciliations.items())
    open_issues = await open_issues_among(
        tenant, [i for issues in done.item_issues.values() for i in issues]
    )
    signed: dict[UUID, bool] = {}
    if recs:
        states = await sign_off_states(
            tenant,
            "reconciliation",
            [r.reconciliation_id for _, r in recs],
            {r.reconciliation_id: r.content_hash for _, r in recs},
        )
        for rid, levels in states.items():
            l1 = next((lv for lv in levels if lv.level == 1), None)
            signed[rid] = l1 is not None and l1.signed_by is not None and not l1.stale
    out: dict[UUID, Reconciled] = {}
    for c in closes:
        version = version_of[c.work_item_id]
        rows: list[repo.PlanAccount] = accounts.get(version, []) if version is not None else []
        missing: list[UUID] = []
        for row in rows:
            if not _account_ties(c.work_item_id, row, done, signed, open_issues):
                missing.append(row.row_id)
        out[c.work_item_id] = Reconciled(len(rows) - len(missing), len(rows), tuple(missing))
    return out, done.running, number_of


def _account_ties(
    close_id: UUID,
    row: repo.PlanAccount,
    done: repo.Computed,
    signed: dict[UUID, bool],
    open_issues: frozenset[UUID],
) -> bool:
    account = row.account_external_id
    if row.procedure == "reconciliation":
        rec = done.reconciliations.get((close_id, account)) if account else None
        if rec is None or rec.tally not in _TIED_RECONCILIATION:
            return False
        if any(i in open_issues for i in done.item_issues.get(rec.reconciliation_id, [])):
            return False
        return signed.get(rec.reconciliation_id, False)
    tie = done.schedules.get((close_id, account)) if account else None
    if tie is not None:
        return tie in _TIED_SCHEDULE
    step = done.procedures.get((close_id, row.row_id))
    return step is not None and step[0] == "done" and step[1] == 0


# --- reads (AC-1, AC-3, AC-4, AC-7) -------------------------------------------------------------


async def people(ids: set[UUID]) -> dict[UUID, ClosePersonOut]:
    """C-01-T24: the people named on a close's records, as CLS screens show them."""
    return await _people(ids)


async def _people(ids: set[UUID]) -> dict[UUID, ClosePersonOut]:
    names = await names_of(sorted(ids, key=str)) if ids else {}
    return {
        uid: ClosePersonOut(user_id=uid, name=name, initials=_initials(name))
        for uid, name in names.items()
    }


def _initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p[:1].isalpha()]
    return ("".join(p[0] for p in parts[:1] + parts[-1:]) if len(parts) > 1 else name[:2]).upper()


async def _past_due(close: repo.CloseRow, on: date) -> int | None:
    if close.due_on is None or close.status in _FINISHED or on <= close.due_on:
        return None
    days = await business_days_between(close.due_on, on)
    return days or None


def _allowed(close: repo.CloseRow, may_move: bool) -> list[CloseAction]:
    actions: list[CloseAction] = []
    if close.status in ("not_started", "in_progress") and not close.on_hold:
        actions.append("close_run.start")
    if may_move and close.status not in _FINISHED:
        actions.append("close.status_move")
    return actions


async def list_closes(
    ctx: AuthContext,
    *,
    period: str,
    status: str | None = None,
    preparer: UUID | None = None,
    reviewer: UUID | None = None,
    attest: bool | None = None,
    q: str | None = None,
) -> CloseListOut:
    """CLS-01: the period's visible closes, the tiles and the summary line. Filters narrow the
    rows; the tiles and the summary count the period's visible closes before the status filter,
    so a tile never reads 0 because it is the one selected (CLS-01 b)."""
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, KIND, READ)}
    async with tenant_session(ctx.tenant) as session:
        closes = [c for c in await repo.closes_by_ids(session, list(facts)) if c.period == period]
    on = await today(ctx.tenant)
    recon, running, _ = await reconciled_facts(ctx.tenant, closes)
    ids = [c.work_item_id for c in closes]
    issues = await open_issue_counts(ctx.tenant, ids)
    people = await _people(
        {
            u
            for c in closes
            for fn in ("close_preparer", "close_reviewer")
            for u in facts[c.work_item_id].assignees.get(fn, ())[:1]
        }
    )
    rows: list[CloseRowOut] = []
    for c in closes:
        f = facts[c.work_item_id]
        prep = f.assignees.get("close_preparer", ())
        rev = f.assignees.get("close_reviewer", ())
        r = recon[c.work_item_id]
        rows.append(
            CloseRowOut(
                close_id=c.work_item_id,
                engagement_id=c.engagement_id,
                client_id=f.client_id,
                client_entity_id=c.client_entity_id,
                client_name=f.client_name,
                period=c.period,
                status=cast(CloseStatus, c.status),
                on_hold=c.on_hold,
                attest=False,
                accounts_reconciled=r.reconciled,
                accounts_total=r.total,
                reconciled_pct=r.pct,
                open_issues=issues.get(c.work_item_id, 0),
                due_on=c.due_on,
                days_past_due=await _past_due(c, on),
                preparer=people.get(prep[0]) if prep else None,
                reviewer=people.get(rev[0]) if rev else None,
                running=c.work_item_id in running,
                run_no=c.run_no,
                allowed_actions=_allowed(c, may_move=True),
            )
        )
    rows.sort(key=lambda r: r.client_name.casefold())
    tiles = {"not_started": 0, "in_progress": 0, "in_review": 0, "delivered": 0}
    for row in rows:
        tiles[_TILE.get(row.status, row.status)] += 1
    summary = CloseSummaryLineOut(
        open_issues=sum(r.open_issues for r in rows),
        past_due=sum(r.days_past_due is not None for r in rows),
        running=sum(r.running for r in rows),
    )

    def keep(row: CloseRowOut) -> bool:
        if status == "past_due" and row.days_past_due is None:
            return False
        if status not in (None, "past_due") and row.status != status:
            return False
        if attest is not None and row.attest != attest:
            return False
        if preparer is not None and (row.preparer is None or row.preparer.user_id != preparer):
            return False
        if reviewer is not None and (row.reviewer is None or row.reviewer.user_id != reviewer):
            return False
        return q is None or q.casefold() in row.client_name.casefold()

    return CloseListOut(
        items=[r for r in rows if keep(r)],
        tiles=CloseTilesOut(**tiles),
        summary=summary,
        next_cursor=None,
    )


async def running_closes(ctx: AuthContext) -> RunningClosesOut:
    """The running pill and its popover (CLS-01 a): visible closes whose newest run still has a
    procedure queued or running, with "Run 2 · 6 of 9 complete · started 9:06 AM"."""
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, KIND, READ)}
    async with tenant_session(ctx.tenant) as session:
        closes = {c.work_item_id: c for c in await repo.closes_by_ids(session, list(facts))}
        runs = await repo.running_runs(session, list(closes))
    items = [
        RunningCloseOut(
            close_id=run.close_id,
            client_name=facts[run.close_id].client_name,
            period=closes[run.close_id].period,
            run_id=run.run_id,
            run_no=max(closes[run.close_id].run_no, 1),
            done=run.done,
            total=run.total,
            started_at=run.started_at,
        )
        for run in runs
    ]
    items.sort(key=lambda i: i.client_name.casefold())
    return RunningClosesOut(items=items)


async def _visible_close(ctx: AuthContext, close_id: UUID) -> tuple[repo.CloseRow, WorkItemFacts]:
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, KIND, READ)}
    found = facts.get(close_id)
    if found is None:
        raise NotFound(KIND)  # walled, unknown or another kind: the same answer (INV-3)
    async with tenant_session(ctx.tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        raise NotFound(KIND)
    return close, found


async def visible_close(ctx: AuthContext, close_id: UUID) -> repo.CloseRow:
    """The close when the person may read it (`close.read`); walled or unknown: 404 (INV-3)."""
    close, _ = await _visible_close(ctx, close_id)
    return close


async def close_summary(ctx: AuthContext, close_id: UUID) -> CloseSummaryOut:
    """CLS-02's record bar and Summary rail (AC-7)."""
    close, f = await _visible_close(ctx, close_id)
    recon, running, numbers = await reconciled_facts(ctx.tenant, [close])
    r = recon[close_id]
    issues = (await open_issue_counts(ctx.tenant, [close_id])).get(close_id, 0)
    documents = (await binder_document_counts(ctx.tenant, [close_id])).get(close_id, 0)
    pending = (await pending_request_counts(ctx.tenant, [close_id])).get(close_id, 0)
    prep = f.assignees.get("close_preparer", ())
    rev = f.assignees.get("close_reviewer", ())
    people = await _people(set(prep[:1]) | set(rev[:1]))
    year, month = (int(p) for p in close.period.split("-"))
    prev = _period(year - (month == 1), (month - 2) % 12 + 1)
    nxt = _period(year + (month == 12), month % 12 + 1)
    async with tenant_session(ctx.tenant) as session:
        around = await repo.neighbours(session, close.engagement_id, [prev, nxt])
    # The record bar links only to neighbours the viewer may open (a walled or unassigned month
    # is not named, INV-3).
    seen = {x.work_item_id for x in await work_item_facts(ctx, KIND, READ)}
    around = {period: item for period, item in around.items() if item in seen}
    on = await today(ctx.tenant)
    blocked: str | None = None
    if close.status == "in_progress":
        if close_id in running:
            blocked = CloseRunInProgress.code
        elif r.total == 0 or r.reconciled < r.total:
            blocked = AccountsNotReconciled.code
    ref = await get_ref(ctx, close.engagement_id)
    may_move = True
    try:
        await authorise(ctx, MOVE, ref.resource())
    except Forbidden:
        may_move = False
    allowed = _allowed(close, may_move)
    try:
        await authorise(ctx, ASSIGN, ref.resource())
        allowed.insert(0, "close.assign")
    except Forbidden:
        pass
    label = await engagement_label(ctx.tenant, close.engagement_id)
    return CloseSummaryOut(
        close_id=close_id,
        engagement_id=close.engagement_id,
        engagement_name=label.name if label is not None else "",
        client_id=f.client_id,
        client_entity_id=close.client_entity_id,
        client_name=f.client_name,
        period=close.period,
        previous_period_close_id=around.get(prev),
        next_period_close_id=around.get(nxt),
        status=cast(CloseStatus, close.status),
        on_hold=close.on_hold,
        on_hold_reason=close.on_hold_reason,
        attest=False,
        preparer=people.get(prep[0]) if prep else None,
        reviewer=people.get(rev[0]) if rev else None,
        open_issues=issues,
        adjustments=await _adjustments(ctx, close_id),
        documents_in_binder=documents,
        accounts_reconciled=r.reconciled,
        accounts_total=r.total,
        due_on=close.due_on,
        days_past_due=await _past_due(close, on),
        requests_publish_on=close.requests_publish_on,
        plan_version=numbers.get(close_id) or None,
        run_no=close.run_no,
        sync=None,  # C9 v2.1 sync facts arrive with C-01-T17's LedgerSyncWorkflow
        portal=ClosePortalBlockOut(
            requests_pending=pending,
            messages=PlannedLinkOut(target="INB-04", label="Messages"),
        ),
        in_review_blocked_by=blocked,
        planned_links=[PlannedLinkOut(target="HOME-03", label="Past Due")],
        allowed_actions=allowed,
        row_version=close.row_version,
    )


async def close_for(tenant: TenantContext, work_item_id: UUID) -> CloseFacts:
    """C-01 §4.4: what C-02, K-04, I-01 and P-08 read about one close (callers authorised)."""
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, work_item_id)
    if close is None:
        raise NotFound(KIND)
    recon, _, numbers = await reconciled_facts(tenant, [close])
    r = recon[work_item_id]
    return CloseFacts(
        close_id=work_item_id,
        engagement_id=close.engagement_id,
        client_entity_id=close.client_entity_id,
        period=close.period,
        status=cast(CloseStatus, close.status),
        on_hold=close.on_hold,
        plan_version=numbers.get(work_item_id) or None,
        accounts_reconciled=r.reconciled,
        accounts_total=r.total,
        open_issues=(await open_issue_counts(tenant, [work_item_id])).get(work_item_id, 0),
        attest=False,
    )


# --- writes (AC-8 to AC-12) ---------------------------------------------------------------------


def _version(if_match: str) -> int:
    raw = if_match.strip().strip('"')
    if raw.startswith("W/"):
        raw = raw[2:].strip('"')
    try:
        return int(raw)
    except ValueError:
        raise StaleClose(facts={"if_match": "not a version"}) from None


async def refuse_non_human(ctx: AuthContext, close_id: UUID, action: str) -> None:
    """INV-1: an agent, the system or a support session is refused, and the refusal kept."""
    if ctx.tenant.actor_kind == "human" and not ctx.is_support and not ctx.client:
        return
    if not ctx.client:
        async with uow(ctx.tenant) as tx:
            tx.record("decision.refused_non_human", target=Target("close", close_id))
    raise Forbidden(action, "role")


async def move_status(
    ctx: AuthContext, close_id: UUID, body: StatusMoveIn, if_match: str
) -> CloseSummaryOut:
    await refuse_non_human(ctx, close_id, MOVE)
    close, _ = await _visible_close(ctx, close_id)
    ref = await get_ref(ctx, close.engagement_id)
    await authorise(ctx, MOVE, ref.resource())
    seen = _version(if_match)
    to = body.to
    on_hold, reason = close.on_hold, close.on_hold_reason
    if body.on_hold is not None:
        if not body.on_hold.reason.strip():
            raise OnHoldReasonRequired(facts={"field": "reason"})
        on_hold, reason = True, body.on_hold.reason.strip()
    elif body.clear_hold:
        on_hold, reason = False, None
    status = close.status
    if close.status == "locked":
        raise TransitionNotAvailable(facts={"from": "locked"})
    if to is not None and to != close.status:
        if to == "in_review":
            if close.status != "in_progress":
                raise TransitionNotAvailable(facts={"from": close.status, "to": to})
            recon, running, _ = await reconciled_facts(ctx.tenant, [close])
            if close_id in running:
                raise CloseRunInProgress(facts={"close_id": str(close_id)})
            r = recon[close_id]
            if r.total == 0 or r.missing:
                raise AccountsNotReconciled(
                    facts={
                        # The first plan row not tied; CLS-02 names its account (facts
                        # carry identifiers only, never a client's account name).
                        "plan_row_id": str(r.missing[0]) if r.missing else "plan",
                        "reconciled": r.reconciled,
                        "total": r.total,
                    }
                )
        elif to == "in_progress":
            if close.status not in ("in_review", "approved"):
                raise TransitionNotAvailable(facts={"from": close.status, "to": to})
        else:
            await status_guard(to)(ctx, close_id)  # fail closed until C-02 registers (AC-11)
        status = to
    if (status, on_hold, reason) == (close.status, close.on_hold, close.on_hold_reason):
        return await close_summary(ctx, close_id)
    async with uow(ctx.tenant) as tx:
        moved = await repo.update_status(
            tx.session, close_id, status=status, on_hold=on_hold, reason=reason, seen=seen
        )
        if moved is None:
            raise StaleClose(facts={"close_id": str(close_id)})
        target = Target("close", close_id)
        if status != close.status:
            tx.record(
                "close.status_changed",
                target=target,
                # A Ref carries no text (kernel `_ref_value`): the row versions here, the words on
                # the CloseStatusChanged event below.
                before=Ref(row_version=close.row_version),
                after=Ref(row_version=moved),
            )
            tx.emit(
                CloseStatusChanged(close_id=close_id, from_status=close.status, to_status=status)
            )
        if on_hold != close.on_hold:
            tx.record("close.on_hold_set" if on_hold else "close.on_hold_cleared", target=target)
    return await close_summary(ctx, close_id)


async def set_assignees(
    ctx: AuthContext, close_id: UUID, body: AssigneesIn, if_match: str
) -> CloseSummaryOut:
    """Managers and Partners set the preparer and reviewer (`close_preparer`, `close_reviewer`);
    each change is one unit of work with `close.assignee_changed` (AC-8)."""
    await refuse_non_human(ctx, close_id, ASSIGN)
    close, _ = await _visible_close(ctx, close_id)
    if _version(if_match) != close.row_version:
        raise StaleClose(facts={"close_id": str(close_id)})
    for function, person in (
        ("close_preparer", body.preparer_user_id),
        ("close_reviewer", body.reviewer_user_id),
    ):
        await reassign_work_item(
            ctx,
            close_id,
            function,
            person,
            authorised_under=ASSIGN,
            on_changed="close.assignee_changed",
        )
    return await close_summary(ctx, close_id)


async def start_close(tx: UnitOfWork, close_id: UUID) -> bool:
    """Not started → In progress, the system's transition on the first run or incorporation
    (AC-11), inside the caller's unit of work. False when the close is already past it."""
    if not await repo.start(tx.session, close_id):
        return False
    tx.record(
        "close.status_changed",
        target=Target("close", close_id),  # the words are on the CloseStatusChanged event
    )
    tx.emit(
        CloseStatusChanged(close_id=close_id, from_status="not_started", to_status="in_progress")
    )
    return True


__all__ = [
    "KIND",
    "Reconciled",
    "close_for",
    "close_summary",
    "generate_closes",
    "list_closes",
    "move_status",
    "reconciled_facts",
    "running_closes",
    "set_assignees",
    "start_close",
]


async def _adjustments(ctx: AuthContext, close_id: UUID) -> int:
    """S48 rest (CLS-10 DV-b): the close's AJEs that still count (C-01-T25's live set: proposed
    to client-approved, not rejected or withdrawn)."""
    from abacus.modules.adjustments.api import entries_of
    from abacus.modules.closes.flux import LIVE_ENTRY_STATUSES

    return sum(
        1 for e in await entries_of(ctx, close_id, "aje") if e.status in LIVE_ENTRY_STATUSES
    )
