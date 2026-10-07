"""Identity routes. PROTECTED. TASK-007."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.identity.context import AuthContext
from abacus.modules.identity.repository import FirmRole
from abacus.modules.identity.routing import SELF, AbacusRouter, current_context, current_signed_in
from abacus.modules.identity.service import (
    SignedIn,
    WallView,
    create_wall,
    list_walls,
    remove_wall_by_id,
)

router = AbacusRouter(prefix="/v1", tags=["identity"])


class MembershipOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    tenant_id: Annotated[UUID, classified("internal")]
    firm_name: Annotated[str, classified("confidential")]
    firm_role: Annotated[FirmRole | None, classified("internal")]


class MeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    email: Annotated[str, classified("confidential")]
    display_name: Annotated[str, classified("confidential")]
    memberships: Annotated[list[MembershipOut], classified("internal")]
    # Set when the user has exactly one membership; otherwise the client picks one and sends it
    # as X-Abacus-Tenant.
    active_tenant_id: Annotated[UUID | None, classified("internal")]


@router.get("/me", action=SELF, response_model=MeOut)
async def me(signed_in: Annotated[SignedIn, Depends(current_signed_in)]) -> MeOut:
    memberships = signed_in.memberships
    return MeOut(
        user_id=signed_in.user.id,
        email=signed_in.user.email,
        display_name=signed_in.user.display_name,
        memberships=[
            MembershipOut(tenant_id=m.tenant_id, firm_name=m.firm_name, firm_role=m.firm_role)
            for m in memberships
        ],
        active_tenant_id=memberships[0].tenant_id if len(memberships) == 1 else None,
    )


# --- Ethical walls (SPEC-002): firm admins, fresh MFA; the matrix decides ---------------------

Ctx = Annotated[AuthContext, Depends(current_context)]


class WallIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    user_id: Annotated[UUID, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]


class WallOut(BaseModel):
    """Who is walled off from which client is itself sensitive (conflicts of interest)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    user_id: Annotated[UUID, classified("confidential")]
    client_id: Annotated[UUID, classified("confidential")]
    status: Annotated[Literal["active", "removed"], classified("internal")]
    created_by: Annotated[UUID, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    removed_by: Annotated[UUID | None, classified("internal")]
    removed_at: Annotated[datetime | None, classified("internal")]


def _wall_out(wall: WallView) -> WallOut:
    return WallOut.model_validate(wall, from_attributes=True)


@router.post("/walls", action="wall.create", response_model=WallOut, status_code=201)
async def create_wall_route(body: WallIn, ctx: Ctx) -> WallOut:
    return _wall_out(await create_wall(ctx, user_id=body.user_id, client_id=body.client_id))


@router.post("/walls/{wall_id}/remove", action="wall.remove", response_model=WallOut)
async def remove_wall_route(wall_id: UUID, ctx: Ctx) -> WallOut:
    """Walls are never deleted: removing one returns it, marked removed."""
    return _wall_out(await remove_wall_by_id(ctx, wall_id))


@router.get("/walls", action="wall.list", response_model=list[WallOut])
async def list_walls_route(ctx: Ctx) -> list[WallOut]:
    return [_wall_out(wall) for wall in await list_walls(ctx)]
