"""C15 v1 routes: `/v1/search` (P-02-T01 stubs; P-02-T08 implements them).

Every route declares exactly one matrix action (ROUTE-001). The matrix refuses client roles, the
agent, the system and break-glass support sessions first (403 `forbidden`; P-02 §3.2 story 2.4,
OQ-5), then `search.palette` off answers 404 named after the flag (the repository's flag-off
answer, DEC-4504), then the stub answers 501 `not_implemented`. Search text is only ever in the
POST body (ADR-241 decision 7); no route takes it as a query parameter.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Query

from abacus.kernel._flags import SEARCH_PALETTE
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.platform.search.contract import (
    RecentsLimit,
    SearchQueryIn,
    SearchRecentIn,
    SearchRecentRecordedOut,
    SearchRecentsOut,
    SearchResultsOut,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

router = AbacusRouter(prefix="/v1/search", tags=["search"])


async def gate(ctx: AuthContext, action: str) -> None:
    """The matrix first (403 for every principal it does not allow), then the flag (404)."""
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, SEARCH_PALETTE):
        raise NotFound(SEARCH_PALETTE.name)


@router.post(
    "",
    action="search.read",
    response_model=SearchResultsOut,
    errors=(429, 501, 503),
)
async def firm_search_route(body: SearchQueryIn, ctx: Ctx) -> SearchResultsOut:
    """Grouped, permission-filtered results in canonical order (SHL-02 a, c, d, e, f, g)."""
    del body
    await gate(ctx, "search.read")
    raise NotImplementedYet("search")


@router.get(
    "/recents",
    action="search.read",
    response_model=SearchRecentsOut,
    errors=(501,),
)
async def recents_route(ctx: Ctx, limit: Annotated[RecentsLimit, Query()] = 5) -> SearchRecentsOut:
    """The viewer's last opened records, re-filtered by `visible()` (SHL-02 b)."""
    del limit
    await gate(ctx, "search.read")
    raise NotImplementedYet("search_recents")


@router.post(
    "/recents",
    action="search_recent.record",
    response_model=SearchRecentRecordedOut,
    errors=(501,),
)
async def record_recent_route(body: SearchRecentIn, ctx: Ctx) -> SearchRecentRecordedOut:
    """A record route loaded: stored only if the viewer may read the object (404 otherwise).
    200 with the identifiers, not the plan's 204: every route declares a response model
    (DEC-4504)."""
    del body
    await gate(ctx, "search_recent.record")
    raise NotImplementedYet("search_recents")
