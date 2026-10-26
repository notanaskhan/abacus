"""C5 section `portal-pbc`, the third-party room (R-01-T13; contract
`docs/contracts/portal-pbc.md`; screen POR-14): the room and its code-only suggest, behind
`portal.third_party_room` (off: 404). The read model is `rooms.py`; the models are the stub's
(`pbc_contract.py`, R-01-T01)."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member
from abacus.modules.portal import rooms
from abacus.modules.portal.pbc_contract import PortalRoomOut, RoomSuggestIn, RoomSuggestOut

# A portal person themself, never a break-glass support context.
Member = Annotated[AuthContext, Depends(current_member)]

rooms_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


@rooms_router.get("/room", action="portal_documents.read", response_model=PortalRoomOut)
async def get_portal_room_route(ctx: Member) -> PortalRoomOut:
    """POR-14: the caller's delegated request items, by band. No delegation, or any request
    outside it: 404."""
    return await rooms.read_room(ctx)


@rooms_router.post("/room/suggest", action="portal_documents.read", response_model=RoomSuggestOut)
async def suggest_room_request_route(body: RoomSuggestIn, ctx: Member) -> RoomSuggestOut:
    """ "Which request is this for?": code-only file-name scoring among the caller's delegated
    items. Writes nothing."""
    return await rooms.suggest_request(ctx, body.file_names)
