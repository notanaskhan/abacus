"""The fieldwork flow (SPEC-040; TASK-100): sample approval, one support request per sample, row
sign-offs and the procedure's steps.

A manager or the engagement partner approves the current selection; until then nobody tests it,
asks the client for support or signs a row (`workpapers.require_approved`). Support goes to the
client as one ordinary request listing the items, in code's words (ADR-111). A preparer and then a
reviewer who isn't the preparer sign each row, bound to the result they signed: a newer result
makes their sign-offs stale, never deleted (ADR-004). The steps and counts are worked out by code
from what's recorded; nothing here is stored as a status.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.fieldwork.models import ItemResult, ItemSignoff, SelectedItem
from abacus.modules.fieldwork.repository import (
    all_items,
    approval_of,
    insert_approval,
    insert_signoffs,
    insert_support_request,
    newest_population,
    newest_results,
    newest_selection,
    signoffs_of,
    support_requested,
)
from abacus.modules.fieldwork.workpapers import (
    SUPPORT_AREA,
    OwnWork,
    RowsNotPrepared,
    _current_selection,  # pyright: ignore[reportPrivateUsage] -- the module's own reader
    _procedure,  # pyright: ignore[reportPrivateUsage] -- the module's own reader
    require_approved,
    workpaper_state,
)
from abacus.modules.identity.api import AuthContext, authorise, engagement_team
from abacus.modules.requests.api import NewRequestItem, add_request_item

LEVELS: Final = ("prepared", "reviewed")
_ACTION: Final = {"prepared": "item.sign_prepared", "reviewed": "item.sign_reviewed"}
_REQUEST_LIMIT: Final = 2000  # request_items.description


class AlreadyApproved(DomainConflict):
    code = "sample_already_approved"


class AlreadyRequested(DomainConflict):
    """AC-4: every item already has a support request."""

    code = "already_requested"


class SignoffInvalid(DomainInvalid):
    code = "signoff_invalid"


@dataclass(frozen=True)
class Approval:
    approved_by: UUID
    name: str
    approved_at: datetime
    note: str | None


@dataclass(frozen=True)
class RowSign:
    signed_by: UUID
    name: str
    initials: str
    signed_at: datetime
    stale: bool  # AC-8: signed on a result that's since been replaced


@dataclass(frozen=True)
class RowState:
    item_id: UUID
    prepared: RowSign | None
    reviewed: RowSign | None


@dataclass(frozen=True)
class Step:
    key: str
    label: str
    state: str  # done | current | todo


@dataclass(frozen=True)
class FlowState:
    approval: Approval | None
    steps: list[Step]
    exceptions: int
    needs_input: int
    passed: int
    rows: list[RowState]


def initials(name: str) -> str:
    parts = [p for p in name.split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "?"


async def _names(ctx: AuthContext, engagement_id: UUID) -> dict[UUID, str]:
    return {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}


# --- AC-1, AC-2: approve the sample --------------------------------------------------------


async def approve_sample(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID, note: str | None
) -> None:
    note = (note or "").strip()[:1000] or None
    await _procedure(ctx, engagement_id, procedure_id)
    selection = await _current_selection(ctx, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "sample.approve", ref.resource())
        made = await insert_approval(
            tx.session,
            tenant_id=ctx.tenant_id,
            selection_id=selection.id,
            approved_by=ctx.user_id,
            note=note,
        )
        if not made:
            raise AlreadyApproved(str(selection.id))
        tx.record(
            "sample.approved",
            target=Target("procedure", procedure_id),
            after=Ref(selection_id=selection.id, items=selection.item_count),
        )


# --- AC-4: one support request for the sample -------------------------------------------------


def selection_wording(lines: Sequence[tuple[str, str, str]], total: int) -> str:
    """Code's words (ADR-111): each item's date, reference and amount, never its description, as
    many as fit in a request, then how many more."""
    head = (
        "Support for the selected entries below: for each, the approved entry and the documents "
    )
    head += "behind it.\n"
    body = head
    shown = 0
    for posted_on, reference, amount in lines:
        line = f"{posted_on} · {reference or 'no reference'} · {amount}\n"
        tail = f"and {total - shown - 1} more" if total - shown - 1 > 0 else ""
        if len(body) + len(line) + len(tail) + 1 > _REQUEST_LIMIT:
            break
        body += line
        shown += 1
    if shown < total:
        body += f"and {total - shown} more"
    return body.rstrip()


async def request_selection_support(
    ctx: AuthContext, engagement_id: UUID, procedure_id: UUID
) -> tuple[UUID, int]:
    """One request listing every item still without one; each is linked to it."""
    await _procedure(ctx, engagement_id, procedure_id)
    selection = await _current_selection(ctx, procedure_id)
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.run", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        await require_approved(session, selection.id)
        items = await all_items(session, selection.id)
        asked = await support_requested(session, selection.id)
    need = [i for i in items if i.id not in asked]
    if not need:
        raise AlreadyRequested(str(procedure_id))
    wording = selection_wording(
        [(i.posted_on.isoformat(), i.reference, f"{i.amount:,.2f}") for i in need], len(need)
    )
    made = await add_request_item(ctx, engagement_id, NewRequestItem(wording, SUPPORT_AREA))
    async with uow(ctx.tenant) as tx:
        for item in need:
            await insert_support_request(
                tx.session,
                tenant_id=ctx.tenant_id,
                selected_item_id=item.id,
                request_item_id=made.id,
                requested_by=ctx.user_id,
            )
        tx.record(
            "procedure.support_requested",
            target=Target("procedure", procedure_id),
            after=Ref(request_item_id=made.id, items=len(need)),
        )
    return made.id, len(need)


# --- AC-6 to AC-9: sign rows -------------------------------------------------------------------


def current_signoffs(
    signoffs: Sequence[ItemSignoff], results: dict[UUID, ItemResult], level: str
) -> dict[UUID, ItemSignoff]:
    """Per row, the newest sign-off at `level` on its current result."""
    found: dict[UUID, ItemSignoff] = {}
    for s in signoffs:
        current = results.get(s.selected_item_id)
        if s.level == level and current is not None and current.id == s.item_result_id:
            found[s.selected_item_id] = s
    return found


async def sign_items(
    ctx: AuthContext,
    engagement_id: UUID,
    procedure_id: UUID,
    level: str,
    item_ids: Sequence[UUID],
) -> int:
    """How many rows were signed; rows the person already signed at this level are skipped."""
    if level not in LEVELS or not item_ids:
        raise SignoffInvalid(str(procedure_id))
    await _procedure(ctx, engagement_id, procedure_id)
    selection = await _current_selection(ctx, procedure_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, _ACTION[level], ref.resource())
        await require_approved(tx.session, selection.id)
        results = await newest_results(tx.session, selection.id)
        in_selection = {i.id for i in await all_items(tx.session, selection.id)}
        wanted = list(dict.fromkeys(item_ids))
        if any(i not in in_selection or i not in results for i in wanted):
            raise SignoffInvalid(str(procedure_id))  # a row without a result can't be signed
        signoffs = await signoffs_of(tx.session, selection.id)
        if level == "reviewed":
            prepared = current_signoffs(signoffs, results, "prepared")
            if any(i not in prepared for i in wanted):
                raise RowsNotPrepared(str(procedure_id))
            if any(prepared[i].signed_by == ctx.user_id for i in wanted):
                raise OwnWork(str(procedure_id))  # AC-7: never the row's preparer
        made = await insert_signoffs(
            tx.session,
            [
                {
                    "tenant_id": ctx.tenant_id,
                    "selected_item_id": i,
                    "item_result_id": results[i].id,
                    "level": level,
                    "signed_by": ctx.user_id,
                }
                for i in wanted
            ],
        )
        tx.record(
            "item.signed",
            target=Target("procedure", procedure_id),
            after=Ref(level=LEVELS.index(level), rows=made),
        )
    return made


# --- AC-11, AC-12: where the procedure is ----------------------------------------------------


def _sign(
    s: ItemSignoff | None, names: dict[UUID, str], current: ItemResult | None
) -> RowSign | None:
    if s is None:
        return None
    name = names.get(s.signed_by, "")
    return RowSign(
        s.signed_by,
        name,
        initials(name),
        s.created_at,
        stale=current is None or current.id != s.item_result_id,
    )


async def flow_state(ctx: AuthContext, engagement_id: UUID, procedure_id: UUID) -> FlowState:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "procedure.read", ref.resource())
    await _procedure(ctx, engagement_id, procedure_id)
    names = await _names(ctx, engagement_id)
    approval: Approval | None = None
    items: Sequence[SelectedItem] = []
    results: dict[UUID, ItemResult] = {}
    signoffs: Sequence[ItemSignoff] = []
    asked: set[UUID] = set()
    async with tenant_session(ctx.tenant) as session:
        population = await newest_population(session, procedure_id)
        selection = await newest_selection(session, procedure_id)
        if selection is not None:
            found = await approval_of(session, selection.id)
            if found is not None:
                approval = Approval(
                    found.approved_by,
                    names.get(found.approved_by, ""),
                    found.created_at,
                    found.note,
                )
            items = await all_items(session, selection.id)
            results = await newest_results(session, selection.id)
            signoffs = await signoffs_of(session, selection.id)
            asked = await support_requested(session, selection.id)
    item_ids = [i.id for i in items]
    latest: dict[tuple[UUID, str], ItemSignoff] = {}
    for s in signoffs:
        latest[(s.selected_item_id, s.level)] = s  # oldest first, so the newest wins
    rows = [
        RowState(
            i,
            _sign(latest.get((i, "prepared")), names, results.get(i)),
            _sign(latest.get((i, "reviewed")), names, results.get(i)),
        )
        for i in item_ids
    ]
    prepared = current_signoffs(signoffs, results, "prepared")
    reviewed = current_signoffs(signoffs, results, "reviewed")
    n = len(item_ids)
    exceptions = sum(1 for r in results.values() if r.result == "exception")
    passed = sum(1 for r in results.values() if r.result == "supported")
    needs_input = n - exceptions - passed
    workpaper = (
        (await workpaper_state(ctx, engagement_id, procedure_id)).status
        if selection is not None
        else "not_started"
    )
    done = [
        population is not None and population.tied,
        selection is not None,
        approval is not None,
        n > 0 and all(i in asked or i in results for i in item_ids),
        n > 0 and len(results) >= n,
        n > 0 and len(prepared) >= n,
        n > 0 and len(reviewed) >= n,
        workpaper == "reviewed",
    ]
    labels = [
        ("population", "Population tied"),
        ("selected", "Selected"),
        ("approved", "Approved"),
        ("requested", "Support requested"),
        ("tested", "Tested"),
        ("prepared", "Rows prepared"),
        ("reviewed", "Rows reviewed"),
        ("signed", "Workpaper signed"),
    ]
    first_open = next((k for k, d in enumerate(done) if not d), None)
    steps = [
        Step(key, label, "done" if done[k] else "current" if k == first_open else "todo")
        for k, (key, label) in enumerate(labels)
    ]
    return FlowState(approval, steps, exceptions, needs_input, passed, rows)
