"""The relationships slice (T-06-T08; TASK-8517; T-06 §5.3; SPEC-702 F8): CLI-03 a-f as the
TPL-14 specimen shows them, typed by the relationships v1 models. Ownership into Ridgeline foots
2 + 38 + 30 + 5 + 25 = 100% at year end. `walled=True` is the view of a user who cannot read the
Feld household: its node, its return and the K-1 edge into it are absent, with no placeholder and
no count (DEC-43, DEC-88). No database code."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Final

from abacus.modules.organisations.relationships_contract import (
    EdgeState,
    RelationshipBannerOut,
    RelationshipEdgeOut,
    RelationshipGraphOut,
    RelationshipKind,
    RelationshipNodeOut,
)

D = Decimal
_NS: Final = uuid.UUID("5f0c0608-0000-4000-8000-000000c11003")
FELD_HOUSEHOLD: Final = "Feld Household"


def _id(name: str) -> uuid.UUID:
    return uuid.uuid5(_NS, name)


def _node(label: str, kind: str = "entity", **extra: object) -> RelationshipNodeOut:
    return RelationshipNodeOut.model_validate(
        {"node_id": _id(label), "kind": kind, "label": label, **extra}
    )


def _edge(
    a: str, b: str, label: str, *, kind: RelationshipKind | None = None, pct: str | None = None,
    k1: EdgeState | None = None,
) -> RelationshipEdgeOut:  # fmt: skip
    return RelationshipEdgeOut(
        edge_id=_id(f"{a}->{b}:{label}"),
        kind="k1" if k1 else "relationship",
        relationship_kind=kind,
        from_node_id=_id(a),
        to_node_id=_id(b),
        percent=D(pct) if pct else None,
        label=label,
        state=k1,
        source="k1_package" if k1 else "person",
    )


OWNERSHIP: Final[tuple[tuple[str, str, RelationshipKind, str], ...]] = (
    ("Ridgeline GP LLC", "2% GP", "gp_of", "2"),
    ("Meera Shah", "38% LP", "lp_of", "38"),
    ("Pell Street Ventures LLC", "30% LP (35% to 6/30/2025)", "lp_of", "30"),
    ("Pell Street II LLC", "5% LP from 7/1/2025", "lp_of", "5"),
    ("Jonah Feld", "25% LP", "lp_of", "25"),
)


def ridgeline_graph(*, released: bool = False, walled: bool = False) -> RelationshipGraphOut:
    """CLI-03 a (draft K-1s, amber banner) or f (released, green banner)."""
    lp = "Ridgeline Property Partners, LP"
    nodes = [_node(lp), *(_node(n) for n, *_ in OWNERSHIP), _node("Owen Calder")]
    edges = [_edge(n, lp, label, kind=kind, pct=pct) for n, label, kind, pct in OWNERSHIP]
    edges.append(_edge("Owen Calder", "Ridgeline GP LLC", "Managing member"))
    state: EdgeState = "released" if released else "draft"
    nodes.append(_node("Meera Shah · 2025 Form 1040", "return", return_state="preparing"))
    edges.append(_edge(lp, "Meera Shah · 2025 Form 1040", "K-1", k1=state))
    if not walled:
        nodes.append(
            _node(f"{FELD_HOUSEHOLD} · 2025 Form 1040", "return", return_state="preparing")
        )
        edges.append(_edge(lp, f"{FELD_HOUSEHOLD} · 2025 Form 1040", "K-1", k1=state))
    banner = (
        RelationshipBannerOut(
            tone="green", text="K-1s released Sep 15 · Feld and Shah 1040s updated"
        )
        if released
        else RelationshipBannerOut(tone="amber", text="Ridgeline 1065 → 2 K-1s at risk")
    )
    return RelationshipGraphOut(
        client_id=_id(lp),
        nodes=nodes,
        edges=edges,
        banner=banner,
        selected_node_id=_id("Jonah Feld"),
    )


def calloway_graph() -> RelationshipGraphOut:
    """CLI-03 c: trustee, discretionary beneficiaries, custodian; K-1 (1041) prepared."""
    trust = "Calloway Family Trust"
    people = ("Eleanor Calloway", "Nora Calloway", "Theo Calloway")
    nodes = [_node(trust), *(_node(p) for p in people)]
    nodes.append(_node("Harborline Trust Company", external=True))
    edges = [
        _edge("Eleanor Calloway", trust, "Trustee", kind="trustee_of"),
        _edge("Nora Calloway", trust, "Beneficiary · discretionary", kind="beneficiary_of"),
        _edge("Theo Calloway", trust, "Beneficiary · discretionary", kind="beneficiary_of"),
        _edge("Harborline Trust Company", trust, "Custodian"),
    ]
    return RelationshipGraphOut(client_id=_id(trust), nodes=nodes, edges=edges)


def single_entity_graph(label: str) -> RelationshipGraphOut:
    """CLI-03 e: one node, "No relationships yet."."""
    return RelationshipGraphOut(client_id=_id(label), nodes=[_node(label)], edges=[])
