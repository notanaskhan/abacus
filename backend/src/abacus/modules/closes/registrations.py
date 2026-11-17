"""The closes module's registrations (C-01-T26; C-01 §4.6, §4.8; DEC-5412; amber).

- **C13 gates** (HOME-02): a flux set with explained lines waits on the engagement's Managers and
  Partners (`close_flux_acceptance`, kind `proposal`); a reconciliation with no open item and no
  current L1 waits on the close's preparer (`close_reconciliation_sign_off`, kind
  `sign_off_request`). The plan publication gate is C-01-T15's (`gate_sources.py`).
- **HOME-01's Closes tile**: the visible closes of the month being closed (the month before the
  firm's today), by CLS-01's tile, narrowed to an office ("Closes 11 of 22 · August 2026").
- **C15 search**: a close is found by its client and month and opens CLS-02.
- **C16 notifications** (identifiers only, DEC-61): a close run that finished with open issues
  (preparer and reviewer), a close run that waits on a person (its starter), a client's answer to
  a transaction question (the issue's assignee). The catalogue rows are in `notifications`.
- **KNW-04 a**: the month's close AJEs and how the firm's AJE thresholds sorted them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import date
from typing import Final, cast
from uuid import UUID

from sqlalchemy import Column, literal, select, text

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.logging import get_logger
from abacus.kernel.uow import Ref, Target, uow
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.closes import repository as repo
from abacus.modules.closes.events import (
    CloseQuestionAnswered,
    CloseRunFinished,
    CloseRunNeedsInput,
)
from abacus.modules.engagements.api import client_of, function_holders, work_item_facts
from abacus.modules.identity.api import AuthContext
from abacus.modules.platform.api import (
    HomeCount,
    HomeOfficeCount,
    HomeStatusCount,
    SearchIndexDocument,
    SearchProjection,
    register_home_count,
    register_search_projection,
)
from abacus.modules.review.api import (
    GateFacts,
    GateSource,
    GateView,
    OpenGate,
    register_gate_presenter,
    register_gate_source,
)

_log = get_logger(__name__)

FLUX_GATE: Final = "close_flux_acceptance"
RECON_GATE: Final = "close_reconciliation_sign_off"
_OPEN_STATUSES: Final = ("not_started", "in_progress", "in_review")
# An AJE KNW-04a lists: pending or approved (adjustments' PENDING and RECORDED).
_LIVE_ENTRY: Final = frozenset(
    {"proposed", "within_threshold", "review_required", "approved", "client_approved"}
)
MONTHS: Final = (
    "January", "February", "March", "April", "May", "June", "July", "August", "September",
    "October", "November", "December",
)  # fmt: skip


def month_label(period: str) -> str:
    year, month = (int(x) for x in period.split("-"))
    return f"{MONTHS[month - 1]} {year}"


def closing_period(on: date) -> str:
    """The month being closed: the one before the firm's today (Sep 14 closes August)."""
    return f"{on.year - 1}-12" if on.month == 1 else f"{on.year:04d}-{on.month - 1:02d}"


def _close_id(ref: str | None) -> UUID | None:
    if ref is None or not ref.startswith("close:"):
        return None
    try:
        return UUID(ref.split(":", 1)[1])
    except ValueError:
        return None


# --- C13: flux acceptance ------------------------------------------------------------------------

_FLUX_DUE: Final = text(
    "SELECT s.id, s.close_id, s.basis, c.engagement_id, c.period, c.due_on, count(*) AS n "
    "FROM analytic_sets s JOIN closes c ON c.work_item_id = s.close_id "
    "JOIN analytic_lines l ON l.set_id = s.id AND l.status = 'explained' "
    "WHERE c.status = ANY(:open) AND c.locked_at IS NULL "
    "AND (CAST(:e AS uuid) IS NULL OR c.engagement_id = CAST(:e AS uuid)) "
    "AND s.version = (SELECT max(x.version) FROM analytic_sets x "
    "WHERE x.close_id = s.close_id AND x.basis = s.basis) "
    "GROUP BY s.id, s.close_id, s.basis, c.engagement_id, c.period, c.due_on"
)
_FLUX_FACTS: Final = text(
    "SELECT s.id, s.close_id, s.basis, c.period, "
    "(SELECT count(*) FROM analytic_lines l WHERE l.set_id = s.id AND l.status = 'explained') "
    "AS n FROM analytic_sets s JOIN closes c ON c.work_item_id = s.close_id WHERE s.id = ANY(:ids)"
)


async def flux_acceptances_due(
    tenant: TenantContext, engagement_id: UUID | None
) -> list[OpenGate]:
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(_FLUX_DUE, {"open": list(_OPEN_STATUSES), "e": engagement_id})
        ).all()
    return [
        OpenGate(
            r.id,
            r.engagement_id,
            due_on=r.due_on,
            work_item_id=r.close_id,
            client_id=await client_of(tenant, r.engagement_id),
        )
        for r in rows
    ]


async def present_flux(ctx: AuthContext, rows: Sequence[GateView]) -> Mapping[UUID, GateFacts]:
    async with tenant_session(ctx.tenant) as session:
        found = {
            r.id: r
            for r in await session.execute(_FLUX_FACTS, {"ids": [x.subject_id for x in rows]})
        }
    out: dict[UUID, GateFacts] = {}
    for row in rows:
        hit = found.get(row.subject_id)
        if hit is None:
            continue
        basis = "month over month" if hit.basis == "mom" else "year over year"
        lines = "1 flux line" if hit.n == 1 else f"{hit.n} flux lines"
        out[row.id] = GateFacts(
            title=f"Accept {lines}",
            context=f"{month_label(str(hit.period))} close · {basis}",
            subject_route=f"CLS-10?closeId={hit.close_id}&basis={hit.basis}",
        )
    return out


# --- C13: reconciliation L1 ----------------------------------------------------------------------

_RECON_READY: Final = text(
    "SELECT DISTINCT ON (r.close_id, r.account_external_id) r.id, r.close_id, "
    "r.account_external_id, r.content_hash, c.engagement_id, c.due_on, "
    "(SELECT count(*) FROM reconciling_items i LEFT JOIN reconciling_item_resolutions x "
    "ON x.item_id = i.id WHERE i.reconciliation_id = r.id AND x.id IS NULL) AS open_items "
    "FROM reconciliations r JOIN closes c ON c.work_item_id = r.close_id "
    "WHERE c.status = ANY(:open) AND c.locked_at IS NULL "
    "AND (CAST(:e AS uuid) IS NULL OR c.engagement_id = CAST(:e AS uuid)) "
    "ORDER BY r.close_id, r.account_external_id, r.version DESC"
)
_RECON_FACTS: Final = text(
    "SELECT r.id, r.close_id, r.account_external_id, c.period FROM reconciliations r "
    "JOIN closes c ON c.work_item_id = r.close_id WHERE r.id = ANY(:ids)"
)


async def reconciliation_l1_due(
    tenant: TenantContext, engagement_id: UUID | None
) -> list[OpenGate]:
    """The newest version of each account's reconciliation with no open item and no current
    (unstale) L1: it waits on the close's preparer."""
    from abacus.modules.closes.reconciliations import TARGET
    from abacus.modules.review.api import sign_off_states

    async with tenant_session(tenant) as session:
        rows = [
            r
            for r in (
                await session.execute(
                    _RECON_READY, {"open": list(_OPEN_STATUSES), "e": engagement_id}
                )
            ).all()
            if int(r.open_items) == 0
        ]
    if not rows:
        return []
    states = await sign_off_states(
        tenant, TARGET, [r.id for r in rows], {r.id: str(r.content_hash) for r in rows}
    )
    out: list[OpenGate] = []
    holders: dict[UUID, dict[str, tuple[UUID, ...]]] = {}
    for r in rows:
        l1 = next((s for s in states.get(r.id, []) if s.level == 1), None)
        if l1 is not None and l1.signed_by is not None and not l1.stale:
            continue
        if r.close_id not in holders:
            holders[r.close_id] = await function_holders(tenant, r.close_id)
        preparer = holders[r.close_id].get("close_preparer", ())
        out.append(
            OpenGate(
                r.id,
                r.engagement_id,
                assignee_user_id=preparer[0] if preparer else None,
                due_on=r.due_on,
                work_item_id=r.close_id,
                client_id=await client_of(tenant, r.engagement_id),
            )
        )
    return out


async def present_reconciliation(
    ctx: AuthContext, rows: Sequence[GateView]
) -> Mapping[UUID, GateFacts]:
    async with tenant_session(ctx.tenant) as session:
        found = {
            r.id: r
            for r in await session.execute(_RECON_FACTS, {"ids": [x.subject_id for x in rows]})
        }
    out: dict[UUID, GateFacts] = {}
    for row in rows:
        hit = found.get(row.subject_id)
        if hit is None:
            continue
        out[row.id] = GateFacts(
            title=f"Sign off reconciliation {hit.account_external_id}",
            context=f"{month_label(str(hit.period))} close",
            subject_route=(f"CLS-05?closeId={hit.close_id}&account={hit.account_external_id}"),
            overlay="sign_off",
        )
    return out


def register_gates() -> None:
    register_gate_source(
        GateSource(
            FLUX_GATE,
            "proposal",
            "flux.read",
            frozenset(
                {"analytic_set.computed", "analytic_line.explained", "analytic_line.accepted"}
            ),
            flux_acceptances_due,
        )
    )
    register_gate_presenter(FLUX_GATE, present_flux)
    register_gate_source(
        GateSource(
            RECON_GATE,
            "sign_off_request",
            "close.read",
            frozenset(
                {
                    "reconciliation.computed",
                    "reconciling_item.resolved",
                    "sign_off.recorded",
                    "sign_off.went_stale",
                }
            ),
            reconciliation_l1_due,
        )
    )
    register_gate_presenter(RECON_GATE, present_reconciliation)


# --- HOME-01: the Closes tile --------------------------------------------------------------------

_TILES: Final = ("not_started", "in_progress", "in_review", "delivered")
_TILE_OF: Final = {"approved": "in_review", "locked": "delivered"}


def tile_counts(statuses: Sequence[str]) -> dict[str, int]:
    """CLS-01's four tiles (Approved counts as In review, Locked as Delivered)."""
    out: dict[str, int] = dict.fromkeys(_TILES, 0)
    for s in statuses:
        key = _TILE_OF.get(s, s)
        if key in out:
            out[key] += 1
    return out


async def closes_tile(viewer: object, office_id: UUID | None) -> HomeCount:
    ctx = cast(AuthContext, viewer)  # HOME-01's count slot passes the signed-in person
    period = closing_period(await today(ctx.tenant))
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, "close", "close.read")}
    async with tenant_session(ctx.tenant) as session:
        closes = [c for c in await repo.closes_by_ids(session, list(facts)) if c.period == period]
    by_office: dict[UUID, int] = {}
    for c in closes:
        office = facts[c.work_item_id].office_id
        if office is not None:
            by_office[office] = by_office.get(office, 0) + 1
    if office_id is not None:
        closes = [c for c in closes if facts[c.work_item_id].office_id == office_id]
    tiles = tile_counts([c.status for c in closes])
    return HomeCount(
        total=len(closes),
        by_status=tuple(
            HomeStatusCount(code, n, f"period={period}&status={code}")
            for code, n in tiles.items()
            if n
        ),
        by_office=tuple(HomeOfficeCount(o, n) for o, n in sorted(by_office.items(), key=str)),
        target_filter=f"period={period}",
    )


# --- C15: a close in the command palette ---------------------------------------------------------

_SEARCH_ONE: Final = text(
    "SELECT work_item_id, engagement_id, period, status, due_on, "
    "coalesce(locked_at, plan_pinned_at, clock_timestamp()) AS updated_at FROM closes "
    "WHERE work_item_id = :id"
)
_SEARCH_IDS: Final = text(
    "SELECT work_item_id FROM closes "
    "WHERE (CAST(:after AS uuid) IS NULL OR work_item_id > CAST(:after AS uuid)) "
    "ORDER BY work_item_id LIMIT :limit"
)


async def build_close(tenant: TenantContext, close_id: UUID) -> SearchIndexDocument | None:
    from abacus.modules.organisations.api import client_name_column

    async with tenant_session(tenant) as session:
        row = (await session.execute(_SEARCH_ONE, {"id": close_id})).mappings().first()
    if row is None:
        return None
    engagement = cast(UUID, row["engagement_id"])
    client_id = await client_of(tenant, engagement)
    if client_id is None:
        return None
    async with tenant_session(tenant) as session:
        name = await session.scalar(
            select(client_name_column(cast(Column[UUID], literal(client_id))))
        )
    month = month_label(str(row["period"]))
    return SearchIndexDocument(
        object_id=close_id,
        title=f"{month} close"[:200],
        context=None if name is None else str(name),
        engagement_id=engagement,
        work_item_id=close_id,
        client_id=client_id,
        identifiers=(str(row["period"]),),
        status_code=str(row["status"]),
        due_on=row["due_on"],
        source_updated_at=row["updated_at"],
        target_params={"closeId": str(close_id)},
    )


async def close_ids(tenant: TenantContext, after: UUID | None, limit: int) -> list[UUID]:
    async with tenant_session(tenant) as session:
        rows = await session.execute(_SEARCH_IDS, {"after": after, "limit": limit})
        return [UUID(str(r)) for r in rows.scalars()]


def _close_of_event(payload: Mapping[str, object]) -> list[UUID]:
    raw = payload.get("close_id")
    return [] if raw is None else [UUID(str(raw))]


CLOSE_PROJECTION: Final = SearchProjection(
    object_type="close",
    group="closes",
    read_action="close.read",
    scope_kind="work_item",
    build=build_close,
    target="CLS-02",
    triggers={"close.created": _close_of_event, "close.status_changed": _close_of_event},
    list_ids=close_ids,
)


# --- C16: close runs and answered questions ------------------------------------------------------


def _system(tenant_id: UUID) -> TenantContext:
    return TenantContext(tenant_id, "system", "closes:notifications")


async def on_run_ready(event: OutboxEvent) -> None:
    """A close run that finished with open issues tells the close's preparer and reviewer."""
    from abacus.modules.agents.api import run_work_item_ref
    from abacus.modules.review.api import open_issue_counts

    tenant = _system(event.tenant_id)
    run_id = UUID(str(event.payload["run_id"]))
    close_id = _close_id(await run_work_item_ref(tenant, run_id))
    if close_id is None:
        return
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        return
    open_issues = (await open_issue_counts(tenant, [close_id])).get(close_id, 0)
    if open_issues == 0:
        return
    held = await function_holders(tenant, close_id)
    people = sorted(
        {u for fn in ("close_preparer", "close_reviewer") for u in held.get(fn, ())[:1]}, key=str
    )
    async with uow(tenant) as tx:
        tx.record(
            "close_run.completed",
            target=Target("close", close_id),
            after=Ref(run_id=run_id, open_issues=open_issues),
        )
        tx.emit(
            CloseRunFinished(
                close_id=close_id,
                engagement_id=close.engagement_id,
                run_id=run_id,
                open_issues=open_issues,
                recipient_user_ids=people,
            )
        )


async def on_run_needs_input(event: OutboxEvent) -> None:
    """A close run that waits on a person tells the person it runs as."""
    from abacus.modules.agents.api import run_work_item_ref

    tenant = _system(event.tenant_id)
    run_id = UUID(str(event.payload["run_id"]))
    close_id = _close_id(await run_work_item_ref(tenant, run_id))
    raw_user = event.payload.get("user_id")
    if close_id is None or raw_user is None:
        return
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        return
    async with uow(tenant) as tx:
        tx.record(
            "close_run.needs_input", target=Target("close", close_id), after=Ref(run_id=run_id)
        )
        tx.emit(
            CloseRunNeedsInput(
                close_id=close_id,
                engagement_id=close.engagement_id,
                run_id=run_id,
                recipient_user_ids=[UUID(str(raw_user))],
            )
        )


async def on_question_answered(event: OutboxEvent) -> None:
    """A client answered a close's question: the issue's assignee hears of it."""
    from abacus.modules.review.api import issue_row

    raw_issue, raw_item = event.payload.get("issue_id"), event.payload.get("work_item_id")
    if raw_issue is None or raw_item is None:
        return
    tenant = _system(event.tenant_id)
    close_id, issue_id = UUID(str(raw_item)), UUID(str(raw_issue))
    async with tenant_session(tenant) as session:
        close = await repo.close_row(session, close_id)
    if close is None:
        return  # not a close's question
    issue = await issue_row(tenant, issue_id)
    if issue.assignee_user_id is None:
        return
    question_id = UUID(str(event.payload["question_id"]))
    async with uow(tenant) as tx:
        tx.record(
            "close_question.answered",
            target=Target("close", close_id),
            after=Ref(question_id=question_id, issue_id=issue_id),
        )
        tx.emit(
            CloseQuestionAnswered(
                close_id=close_id,
                engagement_id=close.engagement_id,
                question_id=question_id,
                issue_id=issue_id,
                recipient_user_ids=[issue.assignee_user_id],
            )
        )


SUBSCRIPTIONS: Final = {
    "agent_run.ready_for_review": on_run_ready,
    "agent_run.needs_input": on_run_needs_input,
    "transaction_question.answered": on_question_answered,
}


# --- KNW-04 a: how the AJE thresholds sorted the month's closes ----------------------------------


async def aje_examples(viewer: AuthContext, period: str | None) -> list[object]:
    """Each visible close AJE of the month (default: the month being closed), with its outcome
    under the firm's AJE thresholds (KNW-04a: "How v2 sorted the August 2026 closes")."""
    from abacus.modules.adjustments.api import entries_of
    from abacus.modules.methodology.api import ExampleRow

    month = period or closing_period(await today(viewer.tenant))
    facts = {f.work_item_id: f for f in await work_item_facts(viewer, "close", "close.read")}
    async with tenant_session(viewer.tenant) as session:
        closes = [c for c in await repo.closes_by_ids(session, list(facts)) if c.period == month]
    rows: list[object] = []
    for c in sorted(closes, key=lambda x: facts[x.work_item_id].client_name.casefold()):
        f = facts[c.work_item_id]
        for e in await entries_of(viewer, c.work_item_id, "aje"):
            if e.status not in _LIVE_ENTRY:
                continue
            rows.append(
                ExampleRow(
                    client_id=f.client_id,
                    client_name=f.client_name,
                    label=e.ref,
                    amount_usd=int(e.amount),
                    outcome=e.threshold_result,
                    detail=e.description,
                    route=f"CLS-02?closeId={c.work_item_id}",
                )
            )
    return rows


def register() -> None:
    from abacus.modules.methodology.api import register_standard_examples

    register_gates()
    register_home_count("closes", closes_tile)
    register_search_projection(CLOSE_PROJECTION)
    register_standard_examples("aje_thresholds", aje_examples)  # type: ignore[arg-type] -- ExampleRow


__all__ = [
    "CLOSE_PROJECTION",
    "SUBSCRIPTIONS",
    "aje_examples",
    "closes_tile",
    "closing_period",
    "month_label",
    "register",
    "tile_counts",
]
