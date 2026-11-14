"""The Today brief's routes, stubs (I-02-T03; SPEC-654; I-02 §4.3). Contract:
`docs/contracts/today.md`.

Every route answers, in order: its matrix action (the router), `today_brief.enabled` (off: 404),
then 501 until I-02-T10 (the read model), T13 (builds) and T16 (history). Each reads only the
caller's own brief (`viewer_user_id = caller`).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query

from abacus.kernel._flags import TODAY_BRIEF_ENABLED
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.practice.today.contract import (
    DrillVM,
    HistoryPage,
    TodayBuildAcceptedOut,
    TodayBuildIn,
    TodayVM,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

today_router = AbacusRouter(prefix="/v1/me/today", tags=["today"])


async def today_gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, TODAY_BRIEF_ENABLED):
        raise NotFound(TODAY_BRIEF_ENABLED.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@today_router.get("", action="briefing.read", response_model=TodayVM)
async def today_route(
    ctx: Ctx, brief_date: Annotated[date | None, Query(alias="date")] = None
) -> TodayVM:
    """The viewer's day; `status: building` with `needs_build` on the first open (§3.8).
    I-02-T10 (DEC-4722): assembled by code over C13."""
    from abacus.modules.practice.today.assembly import assemble

    await today_gate(ctx)
    return await assemble(ctx, brief_date)


@today_router.post(
    "/builds",
    action="briefing.rebuild",
    response_model=TodayBuildAcceptedOut,
    status_code=202,
    errors=(409, 429),
)
async def today_builds_route(
    body: TodayBuildIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TodayBuildAcceptedOut:
    """Records the day's snapshot and starts the missing (or, `force`, all) engagement briefings;
    429 `rebuild_limit` after three forced rebuilds a day; 409 `in_progress`. I-02-T13
    (DEC-4916): at most three engagement runs at once; unavailable ones recorded, no model call."""
    from abacus.modules.agents.api import ensure_briefings, write_briefing_snapshot
    from abacus.modules.practice.today.assembly import assemble

    await today_gate(ctx)
    vm = await assemble(ctx, body.brief_date)
    await write_briefing_snapshot(ctx, vm)
    cards = [(c.engagement_id, c.label) for c in vm.cards]
    if body.mode == "background":  # I-02-T13 rest: the stale engagements, debounced in dispatch
        stale = set(vm.stale_engagements)
        cards = [c for c in cards if c[0] in stale]
    mode = {"force": "force", "background": "background"}.get(body.mode, "interactive")
    done = await ensure_briefings(ctx, cards, mode, body.brief_date)  # type: ignore[arg-type] -- the three literals
    return TodayBuildAcceptedOut(
        status_url=f"/v1/me/today?date={body.brief_date.isoformat()}", started=len(done.started)
    )


@today_router.get("/work-items/{work_item_id}", action="briefing.read", response_model=DrillVM)
async def today_drill_route(
    work_item_id: UUID,
    ctx: Ctx,
    brief_date: Annotated[date | None, Query(alias="date")] = None,
) -> DrillVM:
    """The drill-in under `visible(work_item)`; 404 when walled or not the viewer's."""
    from abacus.modules.practice.today.assembly import drill

    await today_gate(ctx)
    return await drill(ctx, work_item_id, brief_date)


@today_router.get("/history", action="briefing.read", response_model=HistoryPage)
async def today_history_route(
    ctx: Ctx,
    before: Annotated[date | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=90)] = 30,
) -> HistoryPage:
    """Earlier briefs by day, the caller's own, 90 days at most (Q3). I-02-T17 (DEC-4938)."""
    from abacus.modules.practice.today.assembly import history

    await today_gate(ctx)
    return await history(ctx, before, limit)


@today_router.get(
    "/history/{brief_id}", action="briefing.read", response_model=TodayVM
)
async def today_history_brief_route(brief_id: UUID, ctx: Ctx) -> TodayVM:
    """A past brief, read-only; walls re-checked at read. I-02-T17 (DEC-4938)."""
    from abacus.modules.practice.today.assembly import past_brief

    await today_gate(ctx)
    return await past_brief(ctx, brief_id)
