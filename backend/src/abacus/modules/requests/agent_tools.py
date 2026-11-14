"""Request read tools for the Accrued Agent (P-10-T28; C17; ADR-233, ADR-049, ADR-052).

Declared as `ToolDecl` records (`kernel.agent_tools`) and registered by `agents`. The runtime has
authorised `request_item.read` on the engagement (or the run's); each handler reads that
engagement's live items only. A client's words on an item (Ignore notes, "still needed" replies)
are untrusted: the model reads them in `<untrusted>` blocks.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from abacus.kernel.agent_tools import MAX_ROWS, FailedItem, ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.requests.models import RequestItem

Int = classified("internal")
Conf = classified("confidential")
READ: Final = "request_item.read"


class ItemsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    status: Annotated[str | None, Field(max_length=40), Int] = None
    audit_area: Annotated[str | None, Field(max_length=80), Conf] = None


class ItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    request_item_id: Annotated[UUID, Int]  # scoped to the engagement below


class ItemRow(BaseModel):
    id: Annotated[UUID, Int]
    title: Annotated[str | None, Conf] = None
    description: Annotated[str, Conf]
    audit_area: Annotated[str, Conf]
    status: Annotated[str, Int]
    kind: Annotated[str, Int]
    due_on: Annotated[date | None, Int] = None
    client_visible: Annotated[bool, Int]
    blocks_fieldwork: Annotated[bool, Int]


class ItemsOut(BaseModel):
    items: Annotated[list[ItemRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]
    by_status: Annotated[dict[str, int], Int]  # counted by code (ADR-050)


class ItemOut(BaseModel):
    id: Annotated[UUID, Int]
    title: Annotated[str | None, Conf] = None
    description: Annotated[str, Conf]
    audit_area: Annotated[str, Conf]
    status: Annotated[str, Int]
    kind: Annotated[str, Int]
    due_on: Annotated[date | None, Int] = None
    document_kind: Annotated[str | None, Int] = None
    why: Annotated[str | None, Conf] = None
    good_looks_like: Annotated[str | None, Conf] = None
    still_needed: Annotated[str | None, Conf] = None  # may be the client's reply
    na_note: Annotated[str | None, Conf] = None  # the client's own note on an N/A
    period_start: Annotated[date | None, Int] = None
    period_end: Annotated[date | None, Int] = None
    client_visible: Annotated[bool, Int]


def _engagement(caller: ToolCaller, named: UUID | None) -> UUID:
    found = named or caller.engagement_id
    if found is None:
        raise NotFound("engagement")
    return found


async def list_items(caller: ToolCaller, args: ItemsIn) -> ItemsOut:
    engagement = _engagement(caller, args.engagement_id)
    where = [RequestItem.engagement_id == engagement, RequestItem.deleted_at.is_(None)]
    if args.status:
        where.append(RequestItem.status == args.status)
    if args.audit_area:
        where.append(RequestItem.audit_area == args.audit_area)
    async with tenant_session(caller.tenant) as session:
        counted = (
            await session.execute(
                select(RequestItem.status, func.count()).where(*where).group_by(RequestItem.status)
            )
        ).tuples()
        by_status = {status: int(n) for status, n in counted}
        rows = (
            await session.execute(
                select(RequestItem)
                .where(*where)
                .order_by(RequestItem.due_on.asc().nulls_last(), RequestItem.created_at)
                .limit(MAX_ROWS)
            )
        ).scalars()
        items = [
            ItemRow(
                id=r.id,
                title=r.title,
                description=r.description,
                audit_area=r.audit_area,
                status=r.status,
                kind=r.kind,
                due_on=r.due_on,
                client_visible=r.client_visible,
                blocks_fieldwork=r.blocks_fieldwork,
            )
            for r in rows
        ]
    return ItemsOut(items=items, total=sum(by_status.values()), by_status=by_status)


async def read_item(caller: ToolCaller, args: ItemIn) -> ItemOut:
    engagement = _engagement(caller, args.engagement_id)
    async with tenant_session(caller.tenant) as session:
        r = await session.get(RequestItem, args.request_item_id)
    if r is None or r.engagement_id != engagement or r.deleted_at is not None:
        raise NotFound("request_item")  # never another engagement's item
    return ItemOut(
        id=r.id,
        title=r.title,
        description=r.description,
        audit_area=r.audit_area,
        status=r.status,
        kind=r.kind,
        due_on=r.due_on,
        document_kind=r.document_kind,
        why=r.why,
        good_looks_like=r.good_looks_like,
        still_needed=r.still_needed,
        na_note=r.na_note,
        period_start=r.period_start,
        period_end=r.period_end,
        client_visible=r.client_visible,
    )


_P10_TOOLS: Final = (
    ToolDecl(
        "requests.list_items", "read", READ, "confidential", ItemsIn, ItemsOut, list_items,
        records_read="request_item",
    ),
    ToolDecl(
        "requests.read_item", "read", READ, "confidential", ItemIn, ItemOut, read_item,
        untrusted=("still_needed", "na_note"), records_read="request_item",
    ),
)  # fmt: skip

# --- W-02-T11 (DEC-4716; S41 end pass DEC-4733): `binders.read`, a season's binders -----------

_NAMED_PAGES: Final = 10  # W-02-T19: pages read to find binders named by id


class BindersIn(BaseModel):
    """The frozen workbench suite's arguments: a tax year, optionally some binders, a cursor."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tax_year: Annotated[int, Field(ge=2000, le=2100), Int]
    binder_ids: Annotated[list[UUID] | None, Field(max_length=MAX_ROWS), Int] = None
    cursor: Annotated[str | None, Field(max_length=500), Int] = None
    # W-02-T19 (AC-G4): a retry of only the binders an earlier read could not reach (set by the
    # runtime from the step's failure ledger, never by the model).
    only_refs: Annotated[list[UUID] | None, Field(max_length=MAX_ROWS), Int] = None


class BinderRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Int]
    name: Annotated[str, Conf]
    client_name: Annotated[str, Conf]
    kind: Annotated[str, Int]
    status: Annotated[str, Int]
    requests: Annotated[int, Int]
    done: Annotated[int, Int]
    last_client_activity_on: Annotated[date | None, Int] = None


class BindersOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    binders: Annotated[list[BinderRow], Conf]
    total: Annotated[int, Int]
    next_cursor: Annotated[str | None, Int] = None
    # S41 gaps (AC-A6, DEC-4734): the season's binders the viewer can see, counted by code over
    # BND-01's index (walls applied, nothing hidden is counted), and its tiles by status.
    season_total: Annotated[int, Int] = 0
    season_total_capped: Annotated[bool, Int] = False
    by_status: Annotated[dict[str, int], Int] = Field(default_factory=dict[str, int])
    # W-02-T19: the binders asked for by id that this read could not reach (walled, removed or
    # beyond the index's pages), by reference and code only.
    failed_items: Annotated[list[FailedItem], Field(max_length=MAX_ROWS), Int] = Field(
        default_factory=list[FailedItem]
    )


async def read_binders(caller: ToolCaller, args: BindersIn) -> BindersOut:
    """The season's tax binders as BND-01 lists them (`binder_index.list_binders`: `visible()`,
    walls, the done and total counts by code; never the items' client words). `binder_ids`
    narrows the page to those binders."""
    from abacus.modules.requests.binder_index import IndexFilters, list_binders

    filters = IndexFilters(service="tax_return", season=f"TY{args.tax_year}")
    page = await list_binders(
        caller,  # type: ignore[arg-type] -- the run's context reads as its initiator
        filters,
        args.cursor,
        MAX_ROWS,
    )
    named = args.only_refs if args.only_refs is not None else args.binder_ids
    wanted = None if named is None else set(named)
    items = list(page.items)
    cursor = page.next_cursor
    pages = 1
    while wanted is not None and cursor is not None and pages < _NAMED_PAGES:
        if wanted <= {r.id for r in items}:
            break
        more = await list_binders(caller, filters, cursor, MAX_ROWS)  # type: ignore[arg-type] -- as above
        items.extend(more.items)
        cursor, pages = more.next_cursor, pages + 1
    rows = [
        BinderRow(
            id=r.id, name=r.name, client_name=r.client_name, kind=r.kind, status=r.status,
            requests=r.total_count, done=r.done_count,
            last_client_activity_on=(
                None if r.last_client_activity_at is None else r.last_client_activity_at.date()
            ),
        )
        for r in items
        if wanted is None or r.id in wanted
    ][:MAX_ROWS]  # fmt: skip
    found = {r.id for r in rows}
    missing = [b for b in (named or []) if b not in found]
    return BindersOut(
        binders=rows,
        total=len(rows),
        next_cursor=page.next_cursor if wanted is None else None,
        season_total=page.total,
        season_total_capped=page.total_capped,
        by_status=dict(page.counts),
        failed_items=[
            FailedItem(
                ref_type="binder", ref_id=str(b), source="binders", error_code="not_readable"
            )
            for b in missing
        ],
    )


AGENT_TOOLS: Final = (
    *_P10_TOOLS,
    ToolDecl(
        "binders.read", "read", "binder.read", "confidential", BindersIn, BindersOut,
        read_binders, records_read="binder",
    ),
)  # fmt: skip
