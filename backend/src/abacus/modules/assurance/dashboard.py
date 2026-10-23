"""The engagement dashboard, first slice (SPEC-317; TASK-460; K-04 ENG-12).

One read model, every number computed by code from the owners' own facts: the gates, the
sign-off matrix (papers complete, ready for review, changed after sign-off), review notes,
requests (received, overdue), the trial balance (checks, mapping) and the progress the other
modules register (fieldwork: procedures, findings, entries). "Next up" lists what the signed-in
person can do now, decided by the permission matrix itself (`could`), never by role names.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final, Literal
from uuid import UUID

from abacus.kernel.clock import today
from abacus.modules.engagements.api import gate_fact, get_ref, progress_of
from abacus.modules.identity.api import AuthContext, TargetFacts, authorise, could
from abacus.modules.ledger.api import engagement_trial_balances, mapping_view
from abacus.modules.requests.api import overdue_for, request_items_for
from abacus.modules.review.api import (
    LevelState,
    notes_for,
    open_note_counts,
    reviewables_of,
    sign_off_states,
)
from abacus.modules.workpapers.api import checks_for

GATES: Final = tuple(f"G{n}" for n in (1, 2, 3, 5, 6, 7, 8, 9))
_REQUESTED: Final = frozenset({"requested", "uploaded", "received", "returned"})
Kind = Literal["prepare", "review", "answer_note", "clear_note", "chase_request"]


@dataclass(frozen=True)
class GateView:
    gate: str
    met: bool
    blockers: list[str]


@dataclass(frozen=True)
class Tile:
    key: str
    label: str
    value: int
    total: int | None
    attention: bool


@dataclass(frozen=True)
class NextItem:
    kind: Kind
    label: str
    target_type: str
    target_id: UUID
    code: str | None


@dataclass(frozen=True)
class Dashboard:
    gates: list[GateView]
    tiles: list[Tile]
    next_up: list[NextItem]


async def dashboard_for(ctx: AuthContext, engagement_id: UUID) -> Dashboard:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "dashboard.read", ref.resource())
    resource = ref.resource()
    gates = [
        GateView(g, f.met, list(f.blockers))
        for g in GATES
        for f in [await gate_fact(ctx.tenant, engagement_id, g)]
    ]

    # Review: every reviewable's levels on its current content, and open notes.
    found = await reviewables_of(ctx.tenant, engagement_id)
    states: dict[UUID, list[LevelState]] = {}
    for target_type in {r.target_type for r in found}:
        mine = [r for r in found if r.target_type == target_type]
        states.update(
            await sign_off_states(
                ctx.tenant,
                target_type,
                [r.target_id for r in mine],
                {r.target_id: r.content_hash for r in mine},
            )
        )
    notes = await open_note_counts(ctx.tenant, engagement_id)
    can_prepare = await could(ctx, ctx.user_id, "sign_off.prepare", resource)
    complete = ready = changed = 0
    next_up: list[NextItem] = []
    papers = [r for r in found if r.target_type == "workpaper"]
    for r in found:
        levels = states.get(r.target_id, [])
        current = {lv.level: lv.signed_by for lv in levels if lv.signed_by and not lv.stale}
        if any(lv.stale for lv in levels):
            changed += 1
        if 1 in current and 2 in current and not notes.get(r.target_id):
            complete += 1 if r.target_type == "workpaper" else 0
        if 1 in current and 2 not in current:
            ready += 1
            # P-04-T15: whether I may review this one (never a paper I prepared).
            mine = replace(resource, target=TargetFacts(preparer_user_ids=frozenset({current[1]})))
            if await could(ctx, ctx.user_id, "sign_off.review", mine):
                next_up.append(NextItem("review", r.title, r.target_type, r.target_id, r.code))
        if 1 not in current and r.has_content and can_prepare:
            next_up.append(NextItem("prepare", r.title, r.target_type, r.target_id, r.code))

    for n in await notes_for(ctx, engagement_id):
        if n.status == "open" and not n.raised_by_me:
            next_up.append(
                NextItem("answer_note", n.body[:120], n.target_type, n.target_id, n.target_code)
            )
        if n.status == "responded" and n.raised_by_me:
            next_up.append(
                NextItem("clear_note", n.body[:120], n.target_type, n.target_id, n.target_code)
            )

    # Requests: received of requested, and overdue ones to chase.
    items = await request_items_for(ctx, engagement_id)
    requested = [i for i in items if i.status in _REQUESTED]
    overdue = await overdue_for(ctx.tenant, engagement_id, await today(ctx.tenant))
    if await could(ctx, ctx.user_id, "request_item.update", resource):
        next_up.extend(
            NextItem("chase_request", o.description[:120], "request_item", o.id, None)
            for o in overdue[:5]
        )

    tiles = [
        Tile("papers_complete", "Working papers signed off", complete, len(papers), False),
        Tile("ready_for_review", "Ready for review", ready, None, ready > 0),
        Tile("changed", "Changed after sign-off", changed, None, changed > 0),
        Tile("open_notes", "Open review notes", sum(notes.values()), None, bool(notes)),
        Tile(
            "requests_received",
            "Requests received",
            sum(1 for i in requested if i.status == "received"),
            len(requested),
            False,
        ),
        Tile("requests_overdue", "Requests overdue", len(overdue), None, bool(overdue)),
    ]

    # The trial balance of record: checks and mapping.
    tbs = await engagement_trial_balances(ctx.tenant, engagement_id)
    if tbs:
        tb = max(tbs, key=lambda t: t.period_end)
        checks = await checks_for(ctx, engagement_id, tb.id)
        ties = sum(1 for c in checks if c.result.status == "tie")
        tiles.append(
            Tile(
                "tb_checks",
                "Trial balance checks tie",
                ties,
                len(checks),
                any(c.result.status == "off" for c in checks),
            )
        )
        mapped = await mapping_view(ctx.tenant, engagement_id, tb.id)
        if mapped is not None:
            tiles.append(
                Tile(
                    "accounts_mapped",
                    "Accounts mapped",
                    mapped.mapped,
                    mapped.mapped + mapped.unmapped,
                    mapped.unmapped > 0,
                )
            )

    tiles.extend(
        Tile(f.key, f.label, f.value, f.total, f.attention)
        for f in await progress_of(ctx.tenant, engagement_id)
    )
    return Dashboard(gates, tiles, next_up[:20])
