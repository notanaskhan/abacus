"""Workbench context: the picker's options and a session's context items (W-02-T10; W-02 §3.3;
SPEC-653 AC-C3 to AC-C5; DEC-43; DEC-4715). Amber.

- **Options** (WB-02 b) come only from engagements the viewer can open (`engagements.api
  .engagements_for`, `visible()`): on `client_record` the engagement's client entity, on
  `documents` its PBC (`request_set`), on `workpapers` its workpapers (`workpaper_set`). Nothing
  says how many records were left out (DEC-43). `q` filters titles; rows already attached are
  marked.
- **Attach** (owner only, `session.manage`): each ref must be one of the viewer's options (else
  404, no existence leak); the session's `context_refs` gains it and its client joins
  `client_scope` (so a later reader without that client sees the session locked, DEC-87); one
  insert-only `context_added` item and one `workbench_session.context_added` audit event per
  record. The card's summary lines are computed by code from the owning modules (AC-C4):
  requests' PBC counts, workpapers' papers, the engagement's period, an EBP plan's number, year
  and BOY participants, the Trial Balance's L1, materiality and the Internal Control exception
  count (each only where the viewer may read it); never by a model.
- **Remove**: `context_removed`; the ref leaves `context_refs` and later turns leave its client
  out of `client_scope` unless another ref still names it (AC-C5). Earlier items stay.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import engagements_for, work_item_ids_of
from abacus.modules.identity.api import AuthContext
from abacus.modules.workbench.session_list import NotSessionOwner

Tab = Literal["client_record", "documents", "workpapers"]
Kind = Literal["client_entity", "request_set", "workpaper_set"]
TAB_KIND: Final[dict[str, str]] = {
    "client_record": "client_entity",
    "documents": "request_set",
    "workpapers": "workpaper_set",
}
CARD: Final[dict[str, str]] = {
    "client_entity": "Client record",
    "request_set": "Documents",
    "workpaper_set": "Workpapers",
}


@dataclass(frozen=True)
class Option:
    kind: str
    ref_id: UUID
    title: str
    detail: str
    engagement_id: UUID
    client_id: UUID


@dataclass(frozen=True)
class Item:
    id: UUID
    kind: str
    ref_id: UUID
    card_title: str
    chip_label: str
    summary_lines: tuple[str, ...]


async def all_options(ctx: AuthContext) -> list[Option]:
    """Every option the viewer may pick, over the engagements they can open."""
    out: list[Option] = []
    seen: set[tuple[str, UUID]] = set()
    for e in await engagements_for(ctx):
        start, end = e.fiscal_period_start, e.fiscal_period_end
        period = f"{start:%b} {start.day}, {start.year}–{end:%b} {end.day}, {end.year}"  # noqa: RUF001 -- the handoff's en dash
        for kind, ref, title, detail in (
            ("client_entity", e.client_entity_id, e.client_entity_name, f"{e.name} · {period}"),
            ("request_set", e.id, f"PBC · {e.client_entity_name}", e.name),
            ("workpaper_set", e.id, f"Workpapers · {e.client_entity_name}", e.name),
        ):
            if (kind, ref) in seen:
                continue
            seen.add((kind, ref))
            out.append(Option(kind, ref, title, detail, e.id, e.client_id))
    return out


async def options(
    ctx: AuthContext, tab: Tab, q: str | None, attached: set[tuple[str, UUID]]
) -> list[tuple[Option, bool]]:
    kind = TAB_KIND[tab]
    needle = (q or "").casefold()
    return [
        (o, (o.kind, o.ref_id) in attached)
        for o in await all_options(ctx)
        if o.kind == kind and needle in o.title.casefold()
    ]


async def summary(ctx: AuthContext, option: Option) -> tuple[str, tuple[str, ...]]:
    """(chip label, summary lines) by code from the owning modules (AC-C4)."""
    if option.kind == "client_entity":
        plan = await _plan_line(ctx, option)
        return option.title, (plan or option.title, option.detail)
    work_items = await work_item_ids_of(ctx.tenant, option.engagement_id)
    if option.kind == "request_set":
        from abacus.modules.requests.api import pbc_counts

        counts = await pbc_counts(ctx, work_items)
        received = sum(r for r, _t in counts.values())
        total = sum(t for _r, t in counts.values())
        return (
            f"PBC · {received} of {total}",
            (f"{total} requests · {received} received", option.detail),
        )
    from abacus.modules.workpapers.api import work_item_papers

    papers = [p for wi in work_items for p in await work_item_papers(ctx.tenant, wi)]
    titles = " · ".join(str(getattr(p, "title", "")) for p in papers[:4])
    lines = (f"{len(papers)} workpapers", titles) if titles else (f"{len(papers)} workpapers",)
    # AC-C4's one line: "Trial Balance · Prepared · MD · Materiality v2 · $252,200 · Internal
    # Control · 7 exceptions", each part present only when the viewer may read it.
    parts = [
        part
        for part in (
            await _trial_balance_part(ctx, option.engagement_id),
            await _materiality_line(ctx, option.engagement_id),
            await _control_part(ctx, option.engagement_id),
        )
        if part
    ]
    return "Workpapers", (*lines, " · ".join(parts)) if parts else lines


def _plan_year(start: date, end: date) -> str:
    return f"{start:%b} {start.day}–{end:%b} {end.day}"  # noqa: RUF001 -- the handoff's en dash


async def _plan_line(ctx: AuthContext, option: Option) -> str | None:
    """AC-C4's client record line (S41 leftovers, DEC-4738): the plan's number, plan year and
    participants with balances at BOY when the engagement is an EBP audit the viewer may read
    (`ebp.read`); None otherwise, and nothing says why."""
    from abacus.modules.assurance.api import ebp_plan_facts
    from abacus.modules.identity.api import Forbidden, authorise, engagement_resource
    from abacus.modules.organisations.api import entity_plan_number

    try:
        await authorise(
            ctx, "ebp.read", await engagement_resource(ctx.tenant, option.engagement_id)
        )
    except (Forbidden, NotFound):
        return None
    plan = await ebp_plan_facts(ctx.tenant, option.engagement_id)
    if plan is None:
        return None
    number = await entity_plan_number(ctx.tenant, option.ref_id)
    parts = [
        option.title,
        f"PN {number}" if number else None,
        f"plan year {_plan_year(plan.plan_year_start, plan.plan_year_end)}",
        (
            f"{plan.participants_boy_with_balances:,} participants with balances at BOY"
            if plan.participants_boy_with_balances is not None
            else None
        ),
    ]
    return " · ".join(p for p in parts if p)


async def _trial_balance_part(ctx: AuthContext, engagement_id: UUID) -> str | None:
    """ "Trial Balance · Prepared · MD": the engagement's trial balance (assurance's
    `trial_balance` reviewable) and its L1 signer's initials, when the viewer may read the ladder
    (`sign_off.read`); "Trial Balance" alone before a current L1."""
    from abacus.modules.identity.api import Forbidden
    from abacus.modules.review.api import reviewables_of, sign_off_ladder

    found = [
        r
        for r in await reviewables_of(ctx.tenant, engagement_id)
        if r.target_type == "trial_balance"
    ]
    if not found:
        return None
    try:
        ladder = await sign_off_ladder(ctx, "trial_balance", found[-1].target_id)
    except (Forbidden, NotFound):
        return None
    l1 = next((lv.latest for lv in ladder.levels if lv.level == 1), None)
    if l1 is None or l1.stale:
        return "Trial Balance"
    return f"Trial Balance · Prepared · {l1.initials}"


async def _control_part(ctx: AuthContext, engagement_id: UUID) -> str | None:
    """ "Internal Control · 7 exceptions" when the viewer may read controls (`control.read`)."""
    from abacus.modules.assurance.api import control_exceptions
    from abacus.modules.identity.api import Forbidden, authorise, engagement_resource

    try:
        await authorise(ctx, "control.read", await engagement_resource(ctx.tenant, engagement_id))
        found = await control_exceptions(ctx, engagement_id)
    except (Forbidden, NotFound):
        return None
    if not found:
        return None
    noun = "exception" if len(found) == 1 else "exceptions"
    return f"Internal Control · {len(found)} {noun}"


async def _materiality_line(ctx: AuthContext, engagement_id: UUID) -> str | None:
    """W-02-T10 gaps (AC-C4, DEC-4734): the decided materiality and its version, by code, when
    the viewer may read it (`materiality.read`); nothing otherwise, and nothing says why."""
    from abacus.modules.assurance.api import materiality_record
    from abacus.modules.identity.api import Forbidden, authorise, engagement_resource

    try:
        await authorise(
            ctx, "materiality.read", await engagement_resource(ctx.tenant, engagement_id)
        )
        found = await materiality_record(ctx, engagement_id)
    except (Forbidden, NotFound):
        return None
    if not found.versions:
        return None
    newest = found.versions[-1]
    return f"Materiality v{newest.version_no} · ${newest.overall:,.0f}"


_SESSION: Final = text(
    "SELECT owner_user_id, context_refs, client_scope, item_seq, deleted_at "
    "FROM workbench_sessions WHERE id = :id FOR UPDATE"
)
_ITEM: Final = text(
    "INSERT INTO session_items (tenant_id, session_id, seq, kind, payload, actor_kind, actor_id, "
    "classification) VALUES (:t, :s, :seq, :kind, CAST(:payload AS jsonb), 'human', :me, "
    "'confidential') RETURNING id"
)
_UPDATE: Final = text(
    "UPDATE workbench_sessions SET context_refs = CAST(:refs AS jsonb), client_scope = :clients, "
    "item_seq = :seq, last_item_at = clock_timestamp() WHERE id = :id"
)
_ITEMS: Final = text(
    "SELECT id, payload FROM session_items WHERE session_id = :s AND kind = 'context_added' "
    "ORDER BY seq"
)
_REMOVED: Final = text(
    "SELECT payload->>'item_id' AS item FROM session_items WHERE session_id = :s "
    "AND kind = 'context_removed'"
)


def _attached(refs: Sequence[dict[str, str]]) -> set[tuple[str, UUID]]:
    return {(r["kind"], UUID(r["id"])) for r in refs if r.get("kind") in CARD and r.get("id")}


async def attached_of(ctx: AuthContext, session_id: UUID) -> set[tuple[str, UUID]]:
    async with tenant_session(ctx.tenant) as session:
        refs = await session.scalar(
            text("SELECT context_refs FROM workbench_sessions WHERE id = :id"), {"id": session_id}
        )
    return _attached(cast(list[dict[str, str]], refs or []))


async def current_items(ctx: AuthContext, session_id: UUID) -> list[Item]:
    async with tenant_session(ctx.tenant) as session:
        added = (await session.execute(_ITEMS, {"s": session_id})).all()
        removed = {str(r.item) for r in (await session.execute(_REMOVED, {"s": session_id})).all()}
    out: list[Item] = []
    for row in added:
        if str(row.id) in removed:
            continue
        p = cast(dict[str, object], row.payload)
        out.append(
            Item(
                row.id, str(p["kind"]), UUID(str(p["ref_id"])), CARD[str(p["kind"])],
                str(p["chip_label"]), tuple(cast(list[str], p["summary_lines"])),
            )
        )  # fmt: skip
    return out


async def attach(
    ctx: AuthContext, session_id: UUID, refs: Sequence[tuple[str, UUID]]
) -> list[Item]:
    """The owner attaches records the viewer can open (module docstring)."""
    by_ref = {(o.kind, o.ref_id): o for o in await all_options(ctx)}
    chosen = [by_ref.get(r) for r in refs]
    if any(o is None for o in chosen):
        raise NotFound("context_record")  # a record the viewer can't open: no existence leak
    summaries = [await summary(ctx, cast(Option, o)) for o in chosen]
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_SESSION, {"id": session_id})).first()
        if row is None or row.deleted_at is not None:
            raise NotFound("session")
        if row.owner_user_id != ctx.user_id:
            raise NotSessionOwner(facts={"session_id": str(session_id)})
        context = cast(list[dict[str, str]], list(row.context_refs or []))
        clients = list(row.client_scope or [])
        seq = int(row.item_seq)
        present = _attached(context)
        for option, (chip, lines) in zip(chosen, summaries, strict=True):
            o = cast(Option, option)
            if (o.kind, o.ref_id) in present:
                continue
            added = o.client_id not in clients
            ref = {"kind": o.kind, "id": str(o.ref_id), "client": str(o.client_id)}
            context.append({**ref, "client_added": "1"} if added else ref)
            if added:
                clients.append(o.client_id)
            seq += 1
            item_id = await tx.session.scalar(
                _ITEM,
                {
                    "t": ctx.tenant_id, "s": session_id, "seq": seq, "kind": "context_added",
                    "me": str(ctx.user_id),
                    "payload": json.dumps({
                        "v": 1, "kind": o.kind, "ref_id": str(o.ref_id), "chip_label": chip,
                        "summary_lines": list(lines),
                    }),
                },
            )  # fmt: skip
            tx.record(
                "workbench_session.context_added",
                target=Target("workbench_session", session_id),
                after=Ref(item=item_id, kind=o.kind, ref=o.ref_id),
            )
        await tx.session.execute(
            _UPDATE,
            {"refs": json.dumps(context), "clients": clients, "seq": seq, "id": session_id},
        )
    return await current_items(ctx, session_id)


async def remove(ctx: AuthContext, session_id: UUID, item_id: UUID) -> list[Item]:
    """`context_removed` (module docstring); an unknown item is 404."""
    items = {i.id: i for i in await current_items(ctx, session_id)}
    gone = items.get(item_id)
    if gone is None:
        raise NotFound("context_item")
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_SESSION, {"id": session_id})).first()
        if row is None or row.deleted_at is not None:
            raise NotFound("session")
        if row.owner_user_id != ctx.user_id:
            raise NotSessionOwner(facts={"session_id": str(session_id)})
        refs = cast(list[dict[str, str]], list(row.context_refs or []))

        def named(r: dict[str, str]) -> bool:
            return r.get("kind") == gone.kind and r.get("id") == str(gone.ref_id)

        kept = [r for r in refs if not named(r)]
        nothing: dict[str, str] = {}
        dropped = next((r for r in refs if named(r)), nothing)
        still = {r.get("client") for r in kept}
        clients = list(row.client_scope or [])
        client = dropped.get("client")
        if dropped.get("client_added") == "1" and client and client not in still:
            clients = [c for c in clients if str(c) != client]
        seq = int(row.item_seq) + 1
        await tx.session.scalar(
            _ITEM,
            {
                "t": ctx.tenant_id, "s": session_id, "seq": seq, "kind": "context_removed",
                "me": str(ctx.user_id),
                "payload": json.dumps({"v": 1, "item_id": str(item_id), "kind": gone.kind,
                                       "ref_id": str(gone.ref_id)}),
            },
        )  # fmt: skip
        await tx.session.execute(
            _UPDATE, {"refs": json.dumps(kept), "clients": clients, "seq": seq, "id": session_id}
        )
        tx.record(
            "workbench_session.context_removed",
            target=Target("workbench_session", session_id),
            after=Ref(item=item_id, kind=gone.kind),
        )
    return await current_items(ctx, session_id)


__all__ = [
    "CARD",
    "TAB_KIND",
    "Item",
    "Option",
    "all_options",
    "attach",
    "attached_of",
    "current_items",
    "options",
    "remove",
    "summary",
]
