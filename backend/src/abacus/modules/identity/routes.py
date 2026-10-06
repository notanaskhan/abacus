"""Identity routes. PROTECTED. TASK-007."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.modules.identity.repository import FirmRole
from abacus.modules.identity.routing import SELF, AbacusRouter, current_signed_in
from abacus.modules.identity.service import SignedIn

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
