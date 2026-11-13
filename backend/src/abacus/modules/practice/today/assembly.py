"""The Today brief's read model (I-02-T10; I-02 F1, F2, §4.3; SPEC-654; C13; DEC-4722). Amber.

Everything here is code over C13 (ADR-050): the same gates HOME-01/02 count
(`review.api.gates_waiting_on`, the viewer's own context, walls applied) with their presenters'
titles, context lines and routes (`review.api.resolve_gate_facts`).

- **Cells** (HOME-02 band order): `decision`, `sign_off`, `approval_send`, `signature`,
  `needs_attention`, then `overdue` (due before the firm's today). A gate's cell is its C13 band;
  a signature kind (envelope countersign or signature) is `signature`; agent outputs are
  `needs_attention`.
- **Urgency** orders rows: overdue first, then blocked, then by due date (undated last), then
  kind. **Cards** group rows by engagement, engagements ordered by their most urgent row, then
  by how many of their rows are blocked; up to three rows a card, `more` counts the rest.
  **Needs you first** is the three most urgent rows overall.
- **Groups**: `late` (overdue), `due_tomorrow` (due on the next business day on the federal
  calendar, `practice.due_dates.add_business_days`), `ready_for_signoff` (sign-offs not
  blocked), `needs_attention` (blocked rows), `running` (the viewer's running runs count).
  `high_risk` arrives with the briefings' risk lines (I-02-T13).
- **Lead facts**: `lead.overdue`, `lead.due_tomorrow`, `lead.blocked_signoffs`,
  `lead.decisions_blocking`, as integers and gate refs; never model text.
- **Briefings**: a card shows today's ready engagement briefing for the viewer (its summary
  blocks), else no summary; `status` is `ready` when every card's briefing is ready, else
  `building` with `needs_build` (the build is I-02-T13's route).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final
from uuid import UUID

from abacus.kernel import clock
from abacus.modules.identity.api import AuthContext, names_of
from abacus.modules.practice.today.contract import (
    Availability,
    Card,
    CountCell,
    DrillVM,
    DueChip,
    GateRow,
    Group,
    GroupItem,
    LeadFact,
    TodayVM,
)

CELLS: Final = ("decision", "sign_off", "approval_send", "signature", "needs_attention", "overdue")
ROWS_PER_CARD: Final = 3
FIRST: Final = 3
_SIGNATURE_KINDS: Final = frozenset({"envelope_countersign", "signature", "envelope_sign"})


def cell_of(kind: str) -> str:
    from abacus.modules.review.gates import band_of

    if kind in _SIGNATURE_KINDS or "signature" in kind or "countersign" in kind:
        return "signature"
    band = band_of(kind)
    return {
        "decisions": "decision",
        "sign_offs": "sign_off",
        "agent_outputs": "needs_attention",
    }.get(band, "approval_send")


def tone_of(days: int) -> str:
    if days < 0:
        return "red_tint"
    return "amber" if days <= 2 else "neutral"


@dataclass(frozen=True)
class Item:
    gate_id: UUID
    kind: str
    cell: str
    engagement_id: UUID | None
    work_item_id: UUID | None
    due_on: date | None
    blocked: bool
    state: str
    title: str
    context: str
    route: str


def urgency(item: Item, today: date) -> tuple[int, int, int, str]:
    overdue = item.due_on is not None and item.due_on < today
    due = (item.due_on - today).days if item.due_on is not None else 10_000
    return (0 if overdue else 1, 0 if item.blocked else 1, due, item.kind)


def row_of(item: Item, today: date) -> GateRow:
    due = None
    if item.due_on is not None:
        days = (item.due_on - today).days
        due = DueChip(due_on=item.due_on, days=days, tone=tone_of(days))  # type: ignore[arg-type]
    return GateRow(
        gate_id=item.gate_id,
        kind=item.cell,  # type: ignore[arg-type]
        title=item.title,
        due=due,
        state="blocked" if item.blocked else None,
        deep_link=item.route,
        context_line=item.context,
    )


def cards_of(
    items: Sequence[Item], today: date, labels: Mapping[UUID, str]
) -> list[tuple[UUID, list[Item]]]:
    by: dict[UUID, list[Item]] = defaultdict(list)
    for i in items:
        if i.engagement_id is not None:
            by[i.engagement_id].append(i)
    ordered = sorted(
        by.items(),
        key=lambda kv: (
            min(urgency(i, today) for i in kv[1]),
            -sum(1 for i in kv[1] if i.blocked),
            labels.get(kv[0], ""),
        ),
    )
    return [(e, sorted(rows, key=lambda i: urgency(i, today))) for e, rows in ordered]


async def _items(ctx: AuthContext) -> list[Item]:
    from abacus.modules.review.api import gates_waiting_on, resolve_gate_facts

    page = await gates_waiting_on(
        ctx, kind=None, engagement_id=None, cursor=None, limit=200, sort="deadline"
    )
    rows = list(page.items)
    facts = await resolve_gate_facts(ctx, rows)
    out: list[Item] = []
    for g in rows:
        f = facts.get(g.id)
        out.append(
            Item(
                gate_id=g.id,
                kind=g.kind,
                cell=cell_of(g.kind),
                engagement_id=g.engagement_id,
                work_item_id=g.work_item_id,
                due_on=g.due_on,
                blocked=g.blocked,
                state=g.state,
                title=(
                    f.title if f is not None and f.title else g.kind.replace("_", " ").capitalize()
                ),
                context=(f.context if f is not None and f.context else ""),
                route=(
                    f.subject_route if f is not None and f.subject_route else "/home/approvals"
                ),
            )
        )
    return out


async def _labels(ctx: AuthContext, ids: Sequence[UUID]) -> dict[UUID, str]:
    from abacus.modules.engagements.api import engagements_for

    wanted = set(ids)
    return {
        e.id: f"{e.client_entity_name} · {e.name}"
        for e in await engagements_for(ctx)
        if e.id in wanted
    }


async def _briefings(ctx: AuthContext, day: date, ids: Sequence[UUID]) -> dict[UUID, object]:
    from abacus.modules.agents.api import latest_briefings

    return dict(await latest_briefings(ctx.tenant, ctx.user_id, day, ids))


async def assemble(ctx: AuthContext, day: date | None = None) -> TodayVM:
    """The viewer's Today (module docstring). The route authorised `briefing.read`."""
    today = await clock.today(ctx.tenant)
    on = day or today
    items = await _items(ctx)
    engagement_ids = sorted(
        {i.engagement_id for i in items if i.engagement_id is not None}, key=str
    )
    labels = await _labels(ctx, engagement_ids)
    from abacus.modules.practice.due_dates import add_business_days

    tomorrow = await add_business_days(today, 1)
    overdue = [i for i in items if i.due_on is not None and i.due_on < today]
    due_tomorrow = [i for i in items if i.due_on == tomorrow]
    counts = {c: sum(1 for i in items if i.cell == c) for c in CELLS[:-1]}
    counts["overdue"] = len(overdue)
    cells = [CountCell(kind=c, count=counts[c], href=f"/home/approvals?band={c}") for c in CELLS]  # type: ignore[arg-type]
    ranked = sorted(items, key=lambda i: urgency(i, today))
    briefings = await _briefings(ctx, on, engagement_ids)
    cards: list[Card] = []
    for engagement_id, rows in cards_of(items, today, labels):
        b = briefings.get(engagement_id)
        status = getattr(b, "status", None)
        blocks = getattr(b, "blocks", None) if status == "ready" else None
        summary = []
        if isinstance(blocks, dict) and isinstance(blocks.get("summary"), dict):
            summary = list(blocks["summary"].get("parts", []))
        cards.append(
            Card(
                engagement_id=engagement_id,
                work_item_id=rows[0].work_item_id,
                label=labels.get(engagement_id, ""),
                rows=[row_of(i, today) for i in rows[:ROWS_PER_CARD]],
                more=max(0, len(rows) - ROWS_PER_CARD),
                briefing_id=getattr(b, "id", None),
                briefing_status=status,
                unavailable_reason=getattr(b, "unavailable_reason", None),
                summary_blocks=summary,
            )
        )
    blocked_signoffs = [i for i in items if i.cell == "sign_off" and i.blocked]
    decisions_blocking = [i for i in items if i.cell == "decision" and i.blocked]
    lead = [
        LeadFact(
            key="lead.overdue",
            values={"count": len(overdue)},
            refs=[i.gate_id for i in overdue][:10],
        ),
        LeadFact(
            key="lead.due_tomorrow",
            values={"due": len(due_tomorrow), "total": len(items), "date": tomorrow.isoformat()},
            refs=[i.gate_id for i in due_tomorrow][:10],
        ),
        LeadFact(
            key="lead.blocked_signoffs",
            values={"count": len(blocked_signoffs)},
            refs=[i.gate_id for i in blocked_signoffs][:10],
        ),
        LeadFact(
            key="lead.decisions_blocking",
            values={"count": len(decisions_blocking)},
            refs=[i.gate_id for i in decisions_blocking][:10],
        ),
    ]
    groups = [
        Group(key="late", count=len(overdue), items=[_group_item(i) for i in overdue[:10]]),
        Group(
            key="due_tomorrow",
            count=len(due_tomorrow),
            items=[_group_item(i) for i in due_tomorrow[:10]],
        ),
        Group(
            key="ready_for_signoff",
            count=sum(1 for i in items if i.cell == "sign_off" and not i.blocked),
            items=[_group_item(i) for i in items if i.cell == "sign_off" and not i.blocked][:10],
        ),
        Group(
            key="needs_attention",
            count=sum(1 for i in items if i.blocked),
            items=[_group_item(i) for i in items if i.blocked][:10],
        ),
    ]
    first = (await names_of([ctx.user_id])).get(ctx.user_id, "").split(" ")[0]
    ready = bool(cards) and all(c.briefing_status == "ready" for c in cards)
    return TodayVM(
        brief_date=on,
        first_name=first,
        items=len(items),
        engagements=len(cards),
        cells=cells,
        lead_facts=lead,
        layout="focus",
        needs_you_first=[row_of(i, today) for i in ranked[:FIRST]],
        cards=cards,
        groups=groups,
        availability=Availability(narrative=True, ask=False, ask_reason="ask_binding_pending"),
        status="ready" if ready or not cards else "building",
        needs_build=not ready and bool(cards),
        building_counts={
            "items": len(items),
            "deadlines": sum(1 for i in items if i.due_on),
            "engagements": len(cards),
        },
    )


def _group_item(i: Item) -> GroupItem:
    return GroupItem(
        ref_id=i.gate_id,
        title=i.title,
        detail=i.context or None,
        pills=["blocked"] if i.blocked else [],
        deep_link=i.route,
    )


async def drill(ctx: AuthContext, work_item_id: UUID, day: date | None = None) -> DrillVM:
    """The drill-in on one work item: its blockers (the viewer's gates on it), most urgent first.
    A work item none of the viewer's gates name is 404 (walls and need-to-know hold)."""
    from abacus.kernel.errors import NotFound

    today = await clock.today(ctx.tenant)
    items = [i for i in await _items(ctx) if i.work_item_id == work_item_id]
    if not items:
        raise NotFound("work_item")
    ranked = sorted(items, key=lambda i: urgency(i, today))
    labels = await _labels(ctx, [i.engagement_id for i in items if i.engagement_id])
    label = labels.get(ranked[0].engagement_id, "") if ranked[0].engagement_id else ""
    return DrillVM(
        work_item_id=work_item_id,
        title=label,
        summary_fallback=f"{len(items)} items wait on you here.",
        blockers=[row_of(i, today) for i in ranked],
        open_href=ranked[0].route,
        select_refs=[i.gate_id for i in ranked],
    )


__all__ = [
    "CELLS",
    "Item",
    "assemble",
    "cards_of",
    "cell_of",
    "drill",
    "row_of",
    "tone_of",
    "urgency",
]
