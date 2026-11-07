"""Firm-level human gates in the C13 projection (I-01-T23; DEC-2613). PROTECTED.

Two subjects wait on a person and belong to no engagement, so their rows carry none
(`scope="firm"`, `review.gates`):

- `methodology_version_approval` (`decision`; methodology, K-01 AC3.7): a version in Needs
  review, waiting on the firm roles `methodology.approve` allows (quality partners, practice
  leaders).
- `wall_approval` (`decision`; identity, G-01 AC8.2): an active wall waiting on its named
  partner alone (`assigned_only`).

Review may depend on methodology and identity, never the reverse, so the registration lives here.
A row is a link: KNW-02 for the version, ADM-03's wall drawer for the wall. Approving stays the
owners' human-only routes with fresh MFA (INV-1, INV-5); nothing here can act. A wall's row also
never shows to someone walled from its client (INV-3).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.identity.api import AuthContext, walls_awaiting_approval
from abacus.modules.methodology.api import versions_in_review, versions_named
from abacus.modules.review.gate_actions import GateFacts, register_gate_presenter
from abacus.modules.review.gates import GateSource, GateView, OpenGate, register_gate_source

METHODOLOGY: Final = "methodology_version_approval"
WALL: Final = "wall_approval"
_METHODOLOGY_EVENTS: Final = frozenset(
    {
        "methodology.review_requested",
        "methodology_version.approved",
        "methodology_version.discarded",
    }
)
_WALL_EVENTS: Final = frozenset({"wall.created", "wall.approved", "wall.removed"})


async def methodology_open(tenant: TenantContext, _engagement_id: UUID | None) -> list[OpenGate]:
    """Versions in Needs review; unassigned, so each approver of the firm sees them."""
    return [OpenGate(v, None) for v in await versions_in_review(tenant)]


async def walls_open(tenant: TenantContext, _engagement_id: UUID | None) -> list[OpenGate]:
    """Active walls their named partner hasn't approved, each assigned to that partner."""
    return [
        OpenGate(w.wall_id, None, assignee_user_id=w.approver_user_id, client_id=w.client_id)
        for w in await walls_awaiting_approval(tenant)
    ]


async def present_methodology(
    ctx: AuthContext, rows: Sequence[GateView]
) -> Mapping[UUID, GateFacts]:
    named = await versions_named(ctx.tenant, [r.subject_id for r in rows])
    out: dict[UUID, GateFacts] = {}
    for row in rows:
        hit = named.get(row.subject_id)
        if hit is not None:
            out[row.id] = GateFacts(
                title=f"{hit.template_name} · {hit.label}",
                subject_route=f"KNW-02?versionId={hit.version_id}",
            )
    return out


async def present_walls(ctx: AuthContext, rows: Sequence[GateView]) -> Mapping[UUID, GateFacts]:
    """The drawer only: the wall's people and client are ADM-03's to show, under its own read."""
    return {row.id: GateFacts(subject_route=f"ADM-03?wallId={row.subject_id}") for row in rows}


def register_firm_gates() -> None:
    register_gate_source(
        GateSource(
            METHODOLOGY,
            "decision",
            "methodology.read",
            _METHODOLOGY_EVENTS,
            methodology_open,
            scope="firm",
            decides="methodology.approve",
        )
    )
    register_gate_source(
        GateSource(
            WALL,
            "decision",
            "wall.approve",
            _WALL_EVENTS,
            walls_open,
            assigned_only=True,
            scope="firm",
        )
    )
    register_gate_presenter(METHODOLOGY, present_methodology)
    register_gate_presenter(WALL, present_walls)
