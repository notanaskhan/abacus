"""R-01-T13: what the third-party room (POR-14; C5 section `portal-pbc`, DEC-387) reads of
requests. The portal composes it with evidence's files and the client words; this module answers
the requests' own facts only.

The room is the person's open delegations: requests the person holds an active `request_item`
grant on (a third party's or P-06's delegate's) whose delegation under that very grant is still
open, live and client-visible, in a binder a client may read at all. The caller passes the
request ids of its own grants and authorises `portal_documents.read` on each row through
`delegated_only` (the facts are returned with it); nothing else of the engagement is read.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.identity.api import (
    AuthContext,
    delegation_holders,
    drafted_guidance_to_clients,
)
from abacus.modules.requests.portal_documents import (
    PortalBinderRef,
    PortalCategory,
    PortalItem,
    portal_items_of,
)
from abacus.modules.requests.repository import (
    DelegatedRow,
    binder_categories,
    delegated_rows,
    get_request_item,
)
from abacus.modules.requests.service import delegated_to


@dataclass(frozen=True)
class RoomItem:
    item: PortalItem
    binder: PortalBinderRef
    binder_kind: str
    category: PortalCategory | None
    delegated_at: datetime  # when the caller's own delegation of it was made
    delegated_by: UUID
    delegated_to: frozenset[UUID]  # for `delegated_only` (the caller among them)
    client_visible: bool
    client_assignee_user_id: UUID | None


async def room_items(ctx: AuthContext, item_ids: Sequence[UUID]) -> list[RoomItem]:
    """The requests among `item_ids` delegated to the caller now, oldest delegation first."""
    async with tenant_session(ctx.tenant) as session:
        rows = await delegated_rows(session, item_ids)
        mine: dict[UUID, DelegatedRow] = {}
        holders: dict[UUID, set[UUID]] = {}
        for row in rows:
            under = await delegation_holders(ctx.tenant, row.item.id, [row.grant_id])
            holders.setdefault(row.item.id, set()).update(under)
            if ctx.user_id in under:
                mine[row.item.id] = row  # the newest of the caller's delegations of it
        if not mine:
            return []
        shown = await drafted_guidance_to_clients(ctx.tenant)
        out: list[RoomItem] = []
        categories: dict[UUID, dict[UUID, PortalCategory]] = {}
        for row in sorted(mine.values(), key=lambda r: (r.granted_at, str(r.item.id))):
            binder = row.binder
            if binder.id not in categories:
                categories[binder.id] = {
                    c.id: PortalCategory(c.id, c.name, c.position)
                    for c in await binder_categories(session, binder.id)
                }
            [item] = await portal_items_of(session, ctx, binder, [row.item], shown, delegate=True)
            out.append(
                RoomItem(
                    item=item,
                    binder=PortalBinderRef(
                        binder.id,
                        binder.engagement_id,
                        binder.work_item_id,
                        binder.name,
                        binder.status,
                    ),
                    binder_kind=binder.kind,
                    category=categories[binder.id].get(row.item.category_id)
                    if row.item.category_id is not None
                    else None,
                    delegated_at=row.granted_at,
                    delegated_by=row.granted_by,
                    delegated_to=frozenset(holders[row.item.id]),
                    client_visible=row.item.client_visible,
                    client_assignee_user_id=row.item.client_assignee_user_id,
                )
            )
    return out


@dataclass(frozen=True)
class DelegateUpload:
    """R-01-T13 (INV-5): a third party's upload to a request delegated to them, and who at the
    firm hears of it: the request's firm owner (None: the engagement's leads)."""

    engagement_id: UUID
    firm_owner_user_id: UUID | None


async def delegate_upload(
    tenant: TenantContext, item_id: UUID, uploader: UUID
) -> DelegateUpload | None:
    """Whether `uploader` holds a grant under one of the request's open delegations now."""
    async with tenant_session(tenant) as session:
        item = await get_request_item(session, item_id)
        if item is None or item.deleted_at is not None:
            return None
        if uploader not in await delegated_to(tenant, session, item.id):
            return None
    return DelegateUpload(item.engagement_id, item.firm_owner_user_id)


__all__ = ["DelegateUpload", "RoomItem", "delegate_upload", "room_items"]
