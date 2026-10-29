"""Files browser v1 routes (N-01-T02 stubs, live from N-01-T19; N-01 §4.3; ADR-158; FIL-01).
Contract: `docs/contracts/files-browser.md`. Shapes: `files_shapes`; read model: `files`.

Each route answers 404 for a client principal (portal Files is not in MVP-1), then the action at
the firm (403), then 404 with `files.browser` off. Read-only: `allowed_actions` never carries a
write in N-01 (DV-10). Metadata comes under `evidence.read_metadata`; content fields (page count,
thumbnail) need `evidence.read`, so a metadata-only viewer (firm admin, practice leader, security
admin) gets nulls there (DV-11). Walls answer 404 and no count reveals a hidden item (DEC-43).
Client-scoped files (the client's permanent file) sit beside its years (ADR-158).
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from abacus.kernel._flags import FILES_BROWSER
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.evidence import files as svc
from abacus.modules.evidence.files_shapes import (
    AccessLogRow,
    Channel,
    DrawerOut,
    FileRow,
    FileTreeOut,
    FileVersionOut,
    FolderItemsOut,
    FolderKind,
    LinkKind,
    LinkOut,
    NodeKind,
    RetentionOut,
    SignOffSlotOut,
    TieOut,
    TreeNode,
    VirtualChild,
)
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
    mask_tins_for,
)

Ctx = Annotated[AuthContext, Depends(current_context)]


async def _live(ctx: AuthContext, action: str) -> None:
    """A client principal never reaches Files (portal Files is not in MVP-1): 404. Then the
    action at the firm, then the flag."""
    if ctx.client:
        raise NotFound("files")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, FILES_BROWSER):
        raise NotFound(FILES_BROWSER.name)


files_router = AbacusRouter(prefix="/v1", tags=["files"])


@files_router.get(
    "/files/tree", action="evidence.read_metadata", response_model=FileTreeOut, errors=(501,)
)
async def file_tree_route(
    ctx: Ctx,
    client_id: UUID | None = None,
    expand: Annotated[list[str] | None, Query(max_length=20)] = None,
) -> FileTreeOut:
    """FIL-01 tree with counts over visible rows (N-01-T19)."""
    await _live(ctx, "evidence.read_metadata")
    return await svc.tree(ctx, client_id, expand or ())


@files_router.get(
    "/files/folders/{folder_ref}/items",
    action="evidence.read_metadata",
    response_model=FolderItemsOut,
    errors=(501,),
)
async def folder_items_route(
    folder_ref: str,
    ctx: Ctx,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> FolderItemsOut:
    """FIL-01 list (N-01-T19)."""
    await _live(ctx, "evidence.read_metadata")
    return await svc.folder_items(ctx, folder_ref, q=q, cursor=cursor, limit=limit)


@files_router.get(
    "/evidence-items/{item_id}/drawer",
    action="evidence.read_metadata",
    response_model=DrawerOut,
    errors=(501,),
)
async def drawer_route(item_id: UUID, ctx: Ctx) -> DrawerOut:
    """FIL-01 O2 drawer (N-01-T19). It carries a masked TIN, masked again for an offshore reader
    (review 6)."""
    await _live(ctx, "evidence.read_metadata")
    return await mask_tins_for(ctx, await svc.drawer(ctx, item_id))


@files_router.get(
    "/evidence-items/{item_id}/access-log",
    action="evidence.read_access_log",
    response_model=ListPage[AccessLogRow],
    errors=(501,),
)
async def access_log_route(
    item_id: UUID,
    ctx: Ctx,
    cursor: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ListPage[AccessLogRow]:
    """The drawer's access-log card (N-01-T19). The firm gate is metadata (every engagement role
    holds it there); `evidence.read_access_log` is checked on the item's own engagement or client
    by the read model's `visible()` (its relationship layer needs the engagement)."""
    await _live(ctx, "evidence.read_metadata")
    rows, next_cursor = await svc.access_log(ctx, item_id, cursor=cursor, limit=limit)
    return ListPage[AccessLogRow](items=rows, next_cursor=next_cursor, total=len(rows))


__all__ = [
    "AccessLogRow",
    "Channel",
    "DrawerOut",
    "FileRow",
    "FileTreeOut",
    "FileVersionOut",
    "FolderItemsOut",
    "FolderKind",
    "LinkKind",
    "LinkOut",
    "NodeKind",
    "RetentionOut",
    "SignOffSlotOut",
    "TieOut",
    "TreeNode",
    "VirtualChild",
    "files_router",
]
