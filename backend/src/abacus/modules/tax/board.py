"""The practice board's read models and assignment (T-02-T09; T-02 §3, §4.3; TAX-01;
`docs/contracts/tax-returns.md`).

Rows and tiles compose `tax_returns` (this module's) with the work items the viewer may see
(`engagements.api.work_item_facts`, `visible()`-filtered with walls): a walled return is absent
from the rows, the tiles, the totals and the office counts, with no hidden count (INV-3,
DEC-43). Done means `filed` or `accepted`; every other status is open (TY2025 at Brightwater
Hale: 79 open, 145 done, 224 total).

- Filters: tax year (the latest on file by default), status, review level, form, office, partner
  (the signer), preparer, due within n days of today (business time), and `q`, a case-folded
  substring of the client's name. Sort is an allowlist: `extended_due` (the default: the
  extended date, else the original, nulls last, then client) or `client`; `group_by=office`
  orders by office first.
- Row facts: people chips (initials and name) for the preparer, the first reviewer function held
  and the signer; the sync chip; tags `ext` and `on_hold`.
- Bulk assign maps a role to its work-item function and assigns through
  `engagements.api.assign_work_item` (its own wall, team and G2 checks): a return it refuses, or
  one the viewer can't see, is listed in `refused`, never explained.
- G-01's office facts (`tax_returns`: the latest year's returns per office) and the C15 search
  projection (`tax_return`: client, form and year; metadata only) are registered from `api.py`.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.clock import today
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.modules.engagements.api import (
    WorkItemFacts,
    assign_work_item,
    work_item_facts,
    work_item_offices,
)
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise, names_of
from abacus.modules.platform.api import SearchDocument
from abacus.modules.tax.returns_contract import (
    AssignmentRole,
    BulkAssignOut,
    Form,
    OfficeTotalOut,
    PersonChipOut,
    ReviewLevel,
    StatusTileOut,
    TaxReturnRowOut,
    TaxReturnSummaryOut,
)

READ: Final = "tax_return.read_metadata"
ASSIGN: Final = "tax_return.assign"
KIND: Final = "tax_return"
DONE: Final = frozenset({"filed", "accepted"})
STATUSES: Final = (
    "not_started",
    "gathering",
    "preparing",
    "prepared",
    "in_review",
    "action_required",
    "approved",
    "awaiting_signature",
    "filed",
    "accepted",
    "rejected",
    "fixing",
)
FUNCTION_OF: Final[Mapping[AssignmentRole, str]] = {
    "preparer": "preparer",
    "reviewer": "detail_reviewer",
    "signer": "signer",
}
_REVIEWERS: Final = ("detail_reviewer", "first_level_reviewer", "manager_reviewer")
# After an e-file rejection: no tile of their own until a return is in one (TAX-01's ten tiles).
_AFTER_FILING: Final = frozenset({"rejected", "fixing"})
Sort = Literal["extended_due", "client"]

_RETURNS = text(
    "SELECT work_item_id, form, tax_year, status, review_level, extended, on_hold, sync_status, "
    "original_due_on, extended_due_on FROM tax_returns WHERE tax_year = :tax_year"
)
_LATEST_YEAR = text("SELECT max(tax_year) FROM tax_returns")
_ONE = text("SELECT form, tax_year FROM tax_returns WHERE work_item_id = :work_item_id")


@dataclass(frozen=True)
class _Return:
    work_item_id: UUID
    form: str
    tax_year: int
    status: str
    review_level: str | None
    extended: bool
    on_hold: bool
    sync_status: str | None
    original_due_on: date | None
    extended_due_on: date | None


@dataclass(frozen=True)
class Filters:
    tax_year: int | None = None
    status: frozenset[str] = frozenset()
    review_level: ReviewLevel | None = None
    form: frozenset[str] = frozenset()
    office: frozenset[UUID] = frozenset()
    partner: UUID | None = None
    preparer: UUID | None = None
    due_within_days: int | None = None
    q: str | None = None
    group_by_office: bool = False
    sort: Sort = "extended_due"


async def _year(tenant: TenantContext, asked: int | None) -> int | None:
    if asked is not None:
        return asked
    async with tenant_session(tenant) as session:
        return cast(int | None, await session.scalar(_LATEST_YEAR))


async def _returns(tenant: TenantContext, tax_year: int) -> list[_Return]:
    async with tenant_session(tenant) as session:
        rows = (await session.execute(_RETURNS, {"tax_year": tax_year})).all()
    return [_Return(*row) for row in rows]


@dataclass(frozen=True)
class _Board:
    tax_year: int | None
    rows: list[tuple[_Return, WorkItemFacts]]


async def _board(ctx: AuthContext, tax_year: int | None) -> _Board:
    """The viewer's returns for the year: only those whose work item they may see."""
    await authorise(ctx, READ, Resource.firm(ctx.tenant_id))
    year = await _year(ctx.tenant, tax_year)
    if year is None:
        return _Board(None, [])
    facts = {f.work_item_id: f for f in await work_item_facts(ctx, KIND)}
    return _Board(
        year,
        [
            (r, facts[r.work_item_id])
            for r in await _returns(ctx.tenant, year)
            if r.work_item_id in facts
        ],
    )


def _first(facts: WorkItemFacts, functions: Sequence[str]) -> UUID | None:
    for function in functions:
        people = facts.assignees.get(function)
        if people:
            return people[0]
    return None


def _due(r: _Return) -> date | None:
    return r.extended_due_on if r.extended and r.extended_due_on else r.original_due_on


def _initials(name: str) -> str:
    parts = [p for p in name.replace("-", " ").split() if p]
    return "".join(p[0].upper() for p in parts[:2]) or "?"


def _chip(user: UUID | None, names: Mapping[UUID, str]) -> PersonChipOut | None:
    if user is None:
        return None
    name = names.get(user, "")
    return PersonChipOut(user_id=user, initials=_initials(name), name=name)


def _keep(r: _Return, facts: WorkItemFacts, f: Filters, on: date) -> bool:
    if f.status and r.status not in f.status:
        return False
    if f.review_level is not None and r.review_level != f.review_level:
        return False
    if f.form and r.form not in f.form:
        return False
    if f.office and facts.office_id not in f.office:
        return False
    if f.partner is not None and f.partner not in facts.assignees.get("signer", ()):
        return False
    if f.preparer is not None and f.preparer not in facts.assignees.get("preparer", ()):
        return False
    if f.due_within_days is not None:
        due = _due(r)
        if due is None or due > on + timedelta(days=f.due_within_days):
            return False
    return not (f.q and f.q.casefold() not in facts.client_name.casefold())


def _sort_key(row: tuple[_Return, WorkItemFacts], f: Filters) -> tuple[object, ...]:
    r, facts = row
    office = str(facts.office_id) if f.group_by_office and facts.office_id else ""
    if f.sort == "client":
        return (office, facts.client_name.casefold(), r.form, str(r.work_item_id))
    due = _due(r)
    return (
        office,
        due is None,
        due or date.max,
        facts.client_name.casefold(),
        str(r.work_item_id),
    )


async def list_returns(ctx: AuthContext, f: Filters) -> list[TaxReturnRowOut]:
    board = await _board(ctx, f.tax_year)
    on = await today(ctx.tenant)
    kept = sorted(
        (row for row in board.rows if _keep(row[0], row[1], f, on)),
        key=lambda row: _sort_key(row, f),
    )
    people = {
        u
        for _, facts in kept
        for u in (
            _first(facts, ("preparer",)),
            _first(facts, _REVIEWERS),
            _first(facts, ("signer",)),
        )
        if u is not None
    }
    names = await names_of(sorted(people)) if people else {}
    return [_row(r, facts, names) for r, facts in kept]


def _row(r: _Return, facts: WorkItemFacts, names: Mapping[UUID, str]) -> TaxReturnRowOut:
    tags = [tag for tag, on in (("ext", r.extended), ("on_hold", r.on_hold)) if on]
    return TaxReturnRowOut(
        id=r.work_item_id,
        client_id=facts.client_id,
        client_name=facts.client_name,
        form=cast(Form, r.form),
        tax_year=r.tax_year,
        status=r.status,  # type: ignore[arg-type] -- the table's CHECK
        review_level=cast(ReviewLevel | None, r.review_level),
        extended=r.extended,
        on_hold=r.on_hold,
        sync=r.sync_status,  # type: ignore[arg-type] -- the table's CHECK
        preparer=_chip(_first(facts, ("preparer",)), names),
        reviewer=_chip(_first(facts, _REVIEWERS), names),
        signer=_chip(_first(facts, ("signer",)), names),
        office_id=facts.office_id,
        original_due_on=r.original_due_on,
        extended_due_on=r.extended_due_on,
        due_rule_code=None,  # T-02-T10 pins the rule text with the dates
        tags=tags,
    )


async def summary(ctx: AuthContext, tax_year: int | None) -> TaxReturnSummaryOut:
    board = await _board(ctx, tax_year)
    counts: dict[str, int] = dict.fromkeys(STATUSES, 0)
    offices: dict[UUID, list[int]] = {}
    extended = 0
    for r, facts in board.rows:
        counts[r.status] = counts.get(r.status, 0) + 1
        extended += r.extended
        if facts.office_id is not None:
            tally = offices.setdefault(facts.office_id, [0, 0])
            tally[1 if r.status in DONE else 0] += 1
    done = sum(n for s, n in counts.items() if s in DONE)
    total = len(board.rows)
    return TaxReturnSummaryOut(
        tax_year=board.tax_year or 0,
        total=total,
        open=total - done,
        done=done,
        extended=extended,
        # The board's ten tiles; `rejected` and `fixing` only once a return holds one.
        tiles=[
            StatusTileOut(status=s, count=n)  # type: ignore[arg-type] -- the registry's codes
            for s, n in counts.items()
            if s not in _AFTER_FILING or n
        ],
        offices=[
            OfficeTotalOut(office_id=office, open=tally[0], done=tally[1])
            for office, tally in sorted(offices.items(), key=lambda kv: str(kv[0]))
        ],
    )


async def assign(ctx: AuthContext, return_id: UUID, role: AssignmentRole, user_id: UUID) -> None:
    """One assignment: the viewer must see the return, then engagements' own checks."""
    await authorise(ctx, ASSIGN, Resource.firm(ctx.tenant_id))
    if return_id not in {f.work_item_id for f in await work_item_facts(ctx, KIND)}:
        raise NotFound("tax_return")
    await assign_work_item(ctx, return_id, user_id, FUNCTION_OF[role])


async def bulk_assign(
    ctx: AuthContext, return_ids: Sequence[UUID], role: AssignmentRole, user_id: UUID
) -> BulkAssignOut:
    await authorise(ctx, ASSIGN, Resource.firm(ctx.tenant_id))
    seen = {f.work_item_id for f in await work_item_facts(ctx, KIND)}
    assigned = 0
    refused: list[UUID] = []
    for return_id in dict.fromkeys(return_ids):
        if return_id not in seen:
            refused.append(return_id)
            continue
        try:
            await assign_work_item(ctx, return_id, user_id, FUNCTION_OF[role])
        except (NotFound, Forbidden, DomainConflict, DomainInvalid):
            refused.append(return_id)
            continue
        assigned += 1
    return BulkAssignOut(assigned=assigned, refused=refused)


# --- registrations -------------------------------------------------------------------------------


async def returns_by_office(tenant: TenantContext) -> dict[UUID, int]:
    """G-01's office fact `tax_returns`: the latest year's returns per office (counts only)."""
    year = await _year(tenant, None)
    if year is None:
        return {}
    offices = await work_item_offices(
        tenant, [r.work_item_id for r in await _returns(tenant, year)]
    )
    counts: dict[UUID, int] = {}
    for office in offices.values():
        if office is not None:
            counts[office] = counts.get(office, 0) + 1
    return counts


async def return_search_document(tenant: TenantContext, return_id: UUID) -> SearchDocument | None:
    """C15 metadata only: the form and year (the client's name comes with the work item)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_ONE, {"work_item_id": return_id})).first()
    if row is None:
        return None
    form, year = row
    return SearchDocument(
        object_type=KIND,
        object_id=return_id,
        engagement_id=None,
        title=f"Form {str(form).upper()} · TY{year}",
        body="tax return",
    )


__all__ = [
    "DONE",
    "FUNCTION_OF",
    "Filters",
    "assign",
    "bulk_assign",
    "list_returns",
    "return_search_document",
    "returns_by_office",
    "summary",
]
