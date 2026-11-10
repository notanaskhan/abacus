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

from abacus.kernel.agent_tools import MAX_ROWS, ToolCaller, ToolDecl
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


AGENT_TOOLS: Final = (
    ToolDecl(
        "requests.list_items", "read", READ, "confidential", ItemsIn, ItemsOut, list_items,
        records_read="request_item",
    ),
    ToolDecl(
        "requests.read_item", "read", READ, "confidential", ItemIn, ItemOut, read_item,
        untrusted=("still_needed", "na_note"), records_read="request_item",
    ),
)  # fmt: skip
