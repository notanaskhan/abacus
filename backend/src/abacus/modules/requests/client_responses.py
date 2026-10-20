"""The client's responses on requests (SPEC-042; TASK-106).

A client says a request doesn't apply (with a reason, and a note if they like), or withdraws that;
the client admin marks their list done once every request they see is done or doesn't apply. Both
are appended, never edited (ADR-004), and neither changes a request's status: the firm decides
(ADR-005). Firm and client read them with the items' own visibility.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Final
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import get_ref, lock_ref
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    authorise,
    authorise_items,
    names_of,
)
from abacus.modules.requests.repository import (
    client_responses,
    insert_client_response,
    insert_list_done,
    newest_list_done,
)
from abacus.modules.requests.service import read_item, request_items_for

REASONS: Final = ("not_this_year", "sent_another_way", "dont_have")
_DONE_STATUSES: Final = frozenset({"uploaded", "received"})


class ResponseInvalid(DomainInvalid):
    code = "response_invalid"


class ListNotDone(DomainConflict):
    """AC-4: every request is done or doesn't apply first."""

    code = "list_not_done"


@dataclass(frozen=True)
class ClientResponse:
    request_item_id: UUID
    reason: str
    note: str | None
    by: UUID
    name: str
    at: datetime


@dataclass(frozen=True)
class ListDone:
    by: UUID
    name: str
    at: datetime


async def responses(ctx: AuthContext, engagement_id: UUID) -> list[ClientResponse]:
    """AC-3: the requests a client says don't apply (withdrawn ones left out)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise_items(ctx, "request_item.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        newest = await client_responses(session, ctx, engagement_id)
    live = [r for r in newest.values() if r.kind == "not_applicable" and r.reason is not None]
    names = await names_of([r.by_user for r in live])
    return [
        ClientResponse(
            r.request_item_id,
            r.reason or "",
            r.note,
            r.by_user,
            names.get(r.by_user, ""),
            r.created_at,
        )
        for r in live
    ]


async def respond(
    ctx: AuthContext,
    engagement_id: UUID,
    item_id: UUID,
    reason: str | None,
    note: str | None,
) -> None:
    """AC-1 (a reason) and AC-2 (None: withdraw)."""
    if reason is not None and reason not in REASONS:
        raise ResponseInvalid("reason")
    kept = (note or "").strip()[:500] or None
    item = await read_item(ctx.tenant, engagement_id, item_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        resource = Resource.engagement(
            ref.tenant_id, ref.id, archived=ref.archived, client_id=ref.client_id, item=item.facts
        )
        await authorise(ctx, "client_item.respond", resource)
        await insert_client_response(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            request_item_id=item_id,
            kind="not_applicable" if reason is not None else "withdrawn",
            reason=reason,
            note=kept if reason is not None else None,
            by_user=ctx.user_id,
        )
        tx.record(
            "client_item.responded" if reason is not None else "client_item.response_withdrawn",
            target=Target("request_item", item_id),
            after=Ref(reason=REASONS.index(reason) if reason is not None else -1),
        )


async def list_done(ctx: AuthContext, engagement_id: UUID) -> ListDone | None:
    """AC-4: who marked the list done, and when (the newest)."""
    ref = await get_ref(ctx, engagement_id)
    await authorise_items(ctx, "request_item.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        found = await newest_list_done(session, engagement_id)
    if found is None:
        return None
    names = await names_of([found.by_user])
    return ListDone(found.by_user, names.get(found.by_user, ""), found.created_at)


async def mark_done(ctx: AuthContext, engagement_id: UUID) -> None:
    """AC-4: refused while any item the client admin sees is still to do."""
    seen = await request_items_for(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        newest = await client_responses(session, ctx, engagement_id)
    ignored = {i for i, r in newest.items() if r.kind == "not_applicable"}
    if any(i.status not in _DONE_STATUSES and i.id not in ignored for i in seen):
        raise ListNotDone(str(engagement_id))
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "client_list.mark_done", ref.resource())
        await insert_list_done(
            tx.session, tenant_id=ctx.tenant_id, engagement_id=engagement_id, by_user=ctx.user_id
        )
        tx.record("client_list.marked_done", target=Target("engagement", engagement_id))
