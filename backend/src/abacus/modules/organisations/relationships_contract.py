"""Relationships v1 stub (T-06-T08; SPEC-702 F8, §4, AC-34, AC-35; DEC-43, DEC-62, DEC-88;
`docs/contracts/relationships.md`). Screen family CLI-03 (the relationships map, TPL-14 a-f) and
its Add relationship sheet.

P-07's `GET /v1/clients/{id}/relationships` list stays as it is (live, `client.read`); the graph
is its own read so the live list never changes shape. Every route answers, in order: a client
principal 404 (the graph never reaches the portal, INV-4); `clients.relationship_map` off 404; a
write that is not a live person's 403 (INV-1); then 501 until T-06-T21 (service) and T40 (screen).

Walls (DEC-43): a walled client's node is absent with no placeholder and no count; a K-1 edge
between two clients needs read on both engagements (DEC-88). Relationships end, never delete.
Layouts are per user and never audited. Classification: names and percents are `confidential`;
TINs never appear (the inspector's Reveal is P-07's route).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import CLIENTS_RELATIONSHIP_MAP
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
Internal = classified("internal")
Confidential = classified("confidential")

# P-07's kinds (0103), unchanged; the K-1 edge is derived from T-02's packages, never stored.
RelationshipKind = Literal[
    "spouse", "owner_of", "trustee_of", "beneficiary_of", "sponsor_of", "upper_tier_of",
    "executor_of", "gp_of", "lp_of", "estate_of",
]  # fmt: skip
NodeKind = Literal["client", "entity", "return", "external_party"]
EdgeKind = Literal["relationship", "k1"]
EdgeState = Literal["draft", "released"]
RelationshipSource = Literal["person", "intake", "k1_package"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class RelationshipNodeOut(BaseModel):
    model_config = _cfg()

    node_id: Annotated[UUID, Internal]
    kind: Annotated[NodeKind, Internal]
    label: Annotated[str, Field(max_length=200), Confidential]
    sublabel: Annotated[str | None, Field(max_length=200), Confidential] = None
    external: Annotated[bool, Internal] = False  # "Not a Brightwater Hale client", dashed
    return_state: Annotated[str | None, Field(max_length=40), Internal] = None
    x: Annotated[Decimal | None, Internal] = None  # the viewer's saved position
    y: Annotated[Decimal | None, Internal] = None


class RelationshipEdgeOut(BaseModel):
    """ "38% LP"-style labels; K-1 edges draft until released, then solid olive."""

    model_config = _cfg()

    edge_id: Annotated[UUID, Internal]
    kind: Annotated[EdgeKind, Internal]
    relationship_kind: Annotated[RelationshipKind | None, Internal] = None
    from_node_id: Annotated[UUID, Internal]
    to_node_id: Annotated[UUID, Internal]
    percent: Annotated[Decimal | None, Field(gt=0, le=100), Confidential] = None
    label: Annotated[str, Field(max_length=60), Confidential]
    state: Annotated[EdgeState | None, Internal] = None
    since: Annotated[date | None, Internal] = None
    source: Annotated[RelationshipSource, Internal]
    version: Annotated[int, Field(ge=1), Internal] = 1


class RelationshipBannerOut(BaseModel):
    """CLI-03 a "Ridgeline 1065 → 2 K-1s at risk" (amber) or f "K-1s released Sep 15 · Feld and
    Shah 1040s updated" (green): the annotation slot."""

    model_config = _cfg()

    tone: Annotated[Literal["amber", "green"], Internal]
    text: Annotated[str, Field(max_length=200), Confidential]


class RelationshipGraphOut(BaseModel):
    model_config = _cfg()

    client_id: Annotated[UUID, Internal]
    nodes: Annotated[list[RelationshipNodeOut], Internal]
    edges: Annotated[list[RelationshipEdgeOut], Internal]
    banner: Annotated[RelationshipBannerOut | None, Internal] = None
    selected_node_id: Annotated[UUID | None, Internal] = None


class RelationshipIn(BaseModel):
    """Add relationship (O3 sheet): an entity or external party on either side; 422
    `relationship_self_edge` or `relationship_percent_exceeds`."""

    model_config = _cfg()

    from_node_id: Annotated[UUID, Internal]
    to_node_id: Annotated[UUID, Internal]
    kind: Annotated[RelationshipKind, Internal]
    percent: Annotated[Decimal | None, Field(gt=0, le=100), Confidential] = None
    effective_from: Annotated[date, Internal]
    note: Annotated[str | None, Field(max_length=500), Confidential] = None


class RelationshipPatchIn(BaseModel):
    model_config = _cfg()

    percent: Annotated[Decimal | None, Field(gt=0, le=100), Confidential] = None
    note: Annotated[str | None, Field(max_length=500), Confidential] = None
    effective_to: Annotated[date | None, Internal] = None
    expected_version: Annotated[int, Field(ge=1), Internal]


class RelationshipEndIn(BaseModel):
    model_config = _cfg()

    effective_to: Annotated[date, Internal]
    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class ExternalPartyIn(BaseModel):
    model_config = _cfg()

    display_name: Annotated[str, Field(min_length=1, max_length=200), Confidential]
    party_kind: Annotated[Literal["person", "organisation"], Internal]


class GraphLayoutIn(BaseModel):
    model_config = _cfg()

    positions: Annotated[dict[UUID, tuple[Decimal, Decimal]], Field(max_length=500), Internal]


class GraphLayoutOut(BaseModel):
    model_config = _cfg()

    saved: Annotated[int, Field(ge=0), Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

relationships_router = AbacusRouter(prefix="/v1", tags=["organisations"])


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, CLIENTS_RELATIONSHIP_MAP):
        raise NotFound(CLIENTS_RELATIONSHIP_MAP.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@relationships_router.get(
    "/clients/{client_id}/relationship-graph",
    action="client.read",
    response_model=RelationshipGraphOut,
    errors=(501,),
)
async def relationship_graph_route(client_id: UUID, ctx: Ctx) -> RelationshipGraphOut:
    """CLI-03 a-f: nodes, edges, the banner and the viewer's saved positions; walled nodes
    absent, no count."""
    await _on(ctx)
    raise NotImplementedYet


@relationships_router.post(
    "/clients/{client_id}/relationships",
    action="relationship.create",
    response_model=RelationshipEdgeOut,
    status_code=201,
    errors=(501,),
)
async def relationship_create_route(
    client_id: UUID, body: RelationshipIn, ctx: Ctx
) -> RelationshipEdgeOut:
    await _human(ctx, "relationship.create")
    raise NotImplementedYet


@relationships_router.patch(
    "/relationships/{rel_id}",
    action="relationship.update",
    response_model=RelationshipEdgeOut,
    errors=(409, 501),
)
async def relationship_update_route(
    rel_id: UUID, body: RelationshipPatchIn, ctx: Ctx
) -> RelationshipEdgeOut:
    await _human(ctx, "relationship.update")
    raise NotImplementedYet


@relationships_router.post(
    "/relationships/{rel_id}/end",
    action="relationship.end",
    response_model=RelationshipEdgeOut,
    errors=(409, 501),
)
async def relationship_end_route(
    rel_id: UUID, body: RelationshipEndIn, ctx: Ctx
) -> RelationshipEdgeOut:
    """Ended, never deleted."""
    await _human(ctx, "relationship.end")
    raise NotImplementedYet


@relationships_router.post(
    "/clients/{client_id}/external-parties",
    action="relationship.create",
    response_model=RelationshipNodeOut,
    status_code=201,
    errors=(501,),
)
async def external_party_route(
    client_id: UUID, body: ExternalPartyIn, ctx: Ctx
) -> RelationshipNodeOut:
    await _human(ctx, "relationship.create")
    raise NotImplementedYet


@relationships_router.put(
    "/users/me/graph-layouts/{client_id}",
    action="graph_layout.save",
    response_model=GraphLayoutOut,
    errors=(501,),
)
async def graph_layout_route(client_id: UUID, body: GraphLayoutIn, ctx: Ctx) -> GraphLayoutOut:
    """Own rows only; never audited."""
    await _human(ctx, "graph_layout.save")
    raise NotImplementedYet
