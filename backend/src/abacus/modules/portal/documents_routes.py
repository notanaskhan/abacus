"""C5 section `portal-pbc`, the documents reads (R-01-T07; contract `docs/contracts/portal-pbc.md`;
screens POR-03 and POR-04): the binder picker, one binder and one request, for every firm since
`portal.documents_v2` retired (R-01-T18, DEC-510). The read model is `documents.py`; the models are
the stub's (`pbc_contract.py`, R-01-T01)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import Depends, Query

from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member
from abacus.modules.portal import documents
from abacus.modules.portal.pbc_contract import (
    BinderFilter,
    PortalBinderListOut,
    PortalBinderOut,
    PortalRequestOut,
)

# A portal person themself, never a break-glass support context.
Member = Annotated[AuthContext, Depends(current_member)]

documents_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


@documents_router.get(
    "/binders", action="portal_documents.read", response_model=PortalBinderListOut
)
async def list_portal_binders_route(
    ctx: Member, scope_id: Annotated[UUID | None, Query()] = None
) -> PortalBinderListOut:
    """The binder picker: every binder the caller can see; closed ones read-only."""
    return await documents.list_binders(ctx, scope_id)


@documents_router.get(
    "/binders/{binder_id}", action="portal_documents.read", response_model=PortalBinderOut
)
async def get_portal_binder_route(
    binder_id: UUID,
    ctx: Member,
    filter: Annotated[BinderFilter, Query()] = "requested",
    category: Annotated[str | None, Query(max_length=64)] = None,
) -> PortalBinderOut:
    """POR-03. A binder outside the caller's grant, a draft or a forged id answers 404."""
    return await documents.read_binder(ctx, binder_id, filter, category)


@documents_router.get(
    "/request-items/{item_id}", action="portal_documents.read", response_model=PortalRequestOut
)
async def get_portal_request_route(item_id: UUID, ctx: Member) -> PortalRequestOut:
    """POR-04. Out of scope, internal-only, delegated to a third party or forged: 404."""
    return await documents.read_request(ctx, item_id)
