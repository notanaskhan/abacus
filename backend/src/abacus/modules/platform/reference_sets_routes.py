"""C21 part A, the routes: `/v1/reference-sets` (K-02-T05; K-02 §4.4; rules-tables.md).

Each route answers 404 for a client principal before anything else (INV-4), then the matrix
(403), then 404 with `rules.reference_sets` off. A key with nothing published, or nothing in
effect on `as_of`, is 404. Read-only: the operator CLI (K-02-T06) is the only writer until PLT-01.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated

from fastapi import Depends, Path, Query

from abacus.kernel._flags import RULES_REFERENCE_SETS
from abacus.kernel.clock import today
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.platform import reference_sets
from abacus.modules.platform.reference_sets_contract import (
    ReferenceSetKind,
    ReferenceSetOut,
    ReferenceSetResolvedOut,
    ReferenceSetVersionOut,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
Key = Annotated[str, Path(pattern=r"^[a-z0-9_.]{3,80}$")]

router = AbacusRouter(prefix="/v1/reference-sets", tags=["reference-sets"])


async def _gate(ctx: AuthContext) -> None:
    """A client principal never reaches the rules tables (INV-4): 404. Then the matrix (403),
    then the flag (404)."""
    if ctx.client:
        raise NotFound("reference_set")
    await authorise(ctx, "reference_set.read", Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, RULES_REFERENCE_SETS):
        raise NotFound(RULES_REFERENCE_SETS.name)


@router.get("", action="reference_set.read", response_model=ListPage[ReferenceSetOut])
async def list_reference_sets_route(
    ctx: Ctx, kind: Annotated[ReferenceSetKind | None, Query()] = None
) -> ListPage[ReferenceSetOut]:
    """KNW-04 j: the published sets, by kind then key, each with the version in effect today."""
    await _gate(ctx)
    items = await reference_sets.list_sets(kind)
    return ListPage[ReferenceSetOut](items=items, total=len(items))


@router.get("/{key}", action="reference_set.read", response_model=ReferenceSetResolvedOut)
async def resolve_reference_set_route(
    key: Key, ctx: Ctx, as_of: Annotated[date | None, Query()] = None
) -> ReferenceSetResolvedOut:
    """The version in effect on `as_of` (today, in business time, when absent)."""
    await _gate(ctx)
    found = await reference_sets.resolve(key, as_of or await today(ctx.tenant))
    if found is None:
        raise NotFound("reference_set")
    return found


@router.get(
    "/{key}/versions",
    action="reference_set.read",
    response_model=ListPage[ReferenceSetVersionOut],
)
async def reference_set_versions_route(key: Key, ctx: Ctx) -> ListPage[ReferenceSetVersionOut]:
    """The published and withdrawn versions, newest first (never a draft)."""
    await _gate(ctx)
    items = await reference_sets.versions(key)
    if items is None:
        raise NotFound("reference_set")
    return ListPage[ReferenceSetVersionOut](items=items, total=len(items))
