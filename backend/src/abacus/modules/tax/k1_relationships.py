"""The relationship graph's K-1 flows (T-06-T51; TASK-9009; SPEC-702 F8; CLI-03 a, f; DEC-88;
DEC-6015; amber).

Registered as organisations' K-1 flow provider. For the client's entities' returns that issue
K-1s (1065, 1120-S, 1041): each return is a node; each K-1 handed off to a receiving return is an
edge from the issuing return to that return, **draft** until the package is released (or the
hand-off replaced by the final values), **released** after. The receiving return may be another
client's (the Feld 1040).

- **Visibility (DEC-88).** An edge shows only when the viewer may read both returns'
  engagements (`tax_return.read`); otherwise the edge and the receiving return are absent and
  never counted (the banner counts visible edges only).
- **Banner.** Any visible draft edge: amber "Ridgeline 1065 → 2 K-1s at risk" (per issuing
  return, the first by name). All visible edges released: green "K-1s released Sep 15 · Feld and
  Shah 1040s updated". Code's text, never a model's.
- **Nudge.** `k1_package.released` invalidates the issuing return's work-item topic, so an open
  graph re-reads (SSE, identifiers only).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from datetime import date, datetime
from typing import Final, Literal, cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.api import engagement_resource_of
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.organisations.api import relationships as rel

ISSUING: Final = ("1065", "1120s", "1041")
RELEASED: Final = frozenset({"released", "viewed", "downloaded"})
_FORM_LABEL: Final = {"1065": "1065", "1120s": "1120-S", "1041": "1041", "1040": "1040"}

_ISSUERS: Final = text(
    "SELECT t.work_item_id, t.engagement_id, t.client_entity_id, t.form, t.tax_year, t.status, "
    "ce.name FROM tax_returns t JOIN client_entities ce ON ce.id = t.client_entity_id "
    "WHERE ce.client_id = :c AND t.form = ANY(:forms) AND t.tax_year <= :y "
    "ORDER BY ce.name, t.tax_year DESC"
)
_FLOWS: Final = text(
    "SELECT h.id, h.status AS handoff, h.target_work_item_id, p.work_item_id, p.status, "
    "p.released_at, t.engagement_id AS target_engagement, t.form AS target_form, "
    "t.status AS target_status, ce.name AS target_entity, ce.id AS target_entity_id "
    "FROM k1_handoffs h JOIN k1_packages p ON p.id = h.package_id "
    "JOIN tax_returns t ON t.work_item_id = h.target_work_item_id "
    "JOIN client_entities ce ON ce.id = t.client_entity_id "
    "WHERE p.work_item_id = ANY(:issuers) AND h.status <> 'withdrawn' "
    "ORDER BY ce.name, h.id"
)


async def _readable(ctx: AuthContext, engagement_id: UUID, return_id: UUID) -> bool:
    resource = await engagement_resource_of(ctx.tenant, engagement_id)
    try:
        await authorise(ctx, "tax_return.read", replace(resource, work_item_id=return_id))
    except Forbidden:
        return False
    return True


def _short(name: str) -> str:
    """ "Ridgeline Partners, LLC" → "Ridgeline" (the banner's subject)."""
    return name.split()[0].rstrip(",") if name.split() else name


def banner(
    issuer_names: dict[UUID, str],
    issuer_forms: dict[UUID, str],
    edges: list[rel.K1Edge],
    target_names: dict[UUID, str],
    released_on: date | None,
) -> tuple[Literal["amber", "green"], str] | None:
    """Code's text over the visible edges only."""
    if not edges:
        return None
    drafts: dict[UUID, int] = defaultdict(int)
    for e in edges:
        if e.state == "draft":
            drafts[e.from_return_id] += 1
    if drafts:
        first = min(drafts, key=lambda r: (issuer_names[r], str(r)))
        n = drafts[first]
        noun = "K-1" if n == 1 else "K-1s"
        return (
            "amber",
            f"{_short(issuer_names[first])} {issuer_forms[first]} → {n} {noun} at risk",
        )
    names = sorted({_short(target_names[e.to_return_id]) for e in edges})
    joined = names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"
    when = "" if released_on is None else f" {released_on:%b} {released_on.day}"
    return ("green", f"K-1s released{when} · {joined} 1040s updated"[:200])


async def flows(viewer: object, client_id: UUID, as_of: date) -> rel.K1Flows:
    ctx = cast(AuthContext, viewer)
    async with tenant_session(ctx.tenant) as session:
        issuers = list(
            await session.execute(
                _ISSUERS, {"c": client_id, "forms": list(ISSUING), "y": as_of.year}
            )
        )
        rows = (
            list(await session.execute(_FLOWS, {"issuers": [r.work_item_id for r in issuers]}))
            if issuers
            else []
        )
    visible = {
        r.work_item_id: r for r in issuers if await _readable(ctx, r.engagement_id, r.work_item_id)
    }
    nodes: dict[UUID, rel.ReturnNode] = {
        r.work_item_id: rel.ReturnNode(
            r.work_item_id, r.client_entity_id, f"{_short(str(r.name))} {_FORM_LABEL[r.form]}",
            str(r.tax_year), str(r.status),
        )
        for r in visible.values()
    }  # fmt: skip
    edges: list[rel.K1Edge] = []
    target_names: dict[UUID, str] = {}
    released: list[datetime] = []
    for f in rows:
        if f.work_item_id not in visible:
            continue
        if not await _readable(ctx, f.target_engagement, f.target_work_item_id):
            continue  # DEC-88: the edge and the receiving return are absent, never counted
        state: Literal["draft", "released"] = (
            "released" if f.status in RELEASED or f.handoff == "final_replaced" else "draft"
        )
        if state == "released" and f.released_at is not None:
            released.append(cast(datetime, f.released_at))
        target_names[f.target_work_item_id] = str(f.target_entity)
        nodes.setdefault(
            f.target_work_item_id,
            rel.ReturnNode(
                f.target_work_item_id, f.target_entity_id,
                f"{_short(str(f.target_entity))} {_FORM_LABEL.get(f.target_form, f.target_form)}",
                None, str(f.target_status),
            ),
        )  # fmt: skip
        edges.append(rel.K1Edge(f.id, f.work_item_id, f.target_work_item_id, state, "K-1"))
    found = banner(
        {k: str(v.name) for k, v in visible.items()},
        {k: _FORM_LABEL[v.form] for k, v in visible.items()},
        edges,
        target_names,
        max(released).date() if released else None,
    )
    return rel.K1Flows(tuple(nodes.values()), tuple(edges), found)


def register() -> None:
    from abacus.kernel import realtime

    rel.register_k1_flow_provider(flows)
    if realtime.invalidation_of("k1_package.released") is None:
        realtime.register_invalidation(
            "k1_package.released",
            realtime.Invalidation("k1_package", "package_id", (("work_item", "work_item_id"),)),
        )


__all__ = ["banner", "flows", "register"]
