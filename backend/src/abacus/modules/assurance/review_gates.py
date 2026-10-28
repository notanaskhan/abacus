"""SPEC-004's review queue as C13 gates, registered by assurance, which may read requests, evidence
and review (ADR-008) (I-01-T08; I-01 OQ-2, DEC-403): an uploaded item's newest
live version waits on a person's review until a decision stands on it (an undo opens it again) or
it is withdrawn. Kind `evidence_review` (band Approvals & sends); one gate per version, assigned
to the reviewer who took it (`review_assignments`), else to everyone who may review the
engagement. Computed from requests' items and evidence's decisions, never from an event payload.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import NotFound
from abacus.modules.engagements.api import get_ref
from abacus.modules.evidence.api import decided_among, review_assignees, withdrawn_among
from abacus.modules.identity.api import AuthContext, Forbidden, authorise
from abacus.modules.requests.api import awaiting_review, review_hosts
from abacus.modules.review.api import (
    GateFacts,
    GateSource,
    GateView,
    OpenGate,
    register_gate_presenter,
    register_gate_source,
)

SUBJECT: Final = "evidence_version"
EVENTS: Final = frozenset(
    {
        "evidence.uploaded",  # a client upload fulfilled an item
        "review.assigned",  # a reviewer took it
        "review_decision.recorded",  # a decision, or its undo
        "evidence_version.withdrawn",
        "fulfilment.voided",
    }
)


async def open_reviews(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    rows = await awaiting_review(tenant, engagement_id)
    versions = list(dict.fromkeys(v for _, v, _ in rows))
    closed = await decided_among(tenant, versions) | await withdrawn_among(tenant, versions)
    taken = await review_assignees(tenant, versions)
    seen: set[UUID] = set()
    gates: list[OpenGate] = []
    for _item, version, engagement in rows:
        if version in closed or version in seen:
            continue  # a version fulfilling several items waits once
        seen.add(version)
        gates.append(OpenGate(version, engagement, assignee_user_id=taken.get(version)))
    return gates


SOURCE: Final = GateSource(SUBJECT, "evidence_review", "review.read", EVENTS, open_reviews)


def subject_route(list_kind: str, list_id: UUID, work_item_id: UUID, item_id: UUID) -> str:
    """The host a row opens while `home.approvals` is off (I-01-T13; I-01 AC2.4), as a screen code
    the SPA resolves through its manifest (`docs/contracts/home-and-gates.md` §6): an assurance
    PBC list is the audit's Source documents (AUD-03, the audit is the list's work item); every
    other list is a binder (BND-02, the list is the binder). Opaque ids only (ADR-031)."""
    if list_kind == "pbc":
        return f"AUD-03?auditId={work_item_id}&item={item_id}"
    return f"BND-02?binderId={list_id}&request={item_id}"


async def present_reviews(ctx: AuthContext, rows: Sequence[GateView]) -> Mapping[UUID, GateFacts]:
    """Each row's host route, for a caller who may read reviews on its engagement; a row the
    caller may not read there gets no facts (the projection already walled it; this re-checks)."""
    allowed: dict[UUID, bool] = {}
    for engagement_id in {r.engagement_id for r in rows if r.engagement_id is not None}:
        try:
            ref = await get_ref(ctx, engagement_id)
            await authorise(ctx, "review.read", ref.resource())
            allowed[engagement_id] = True
        except (Forbidden, NotFound):
            allowed[engagement_id] = False
    mine = [r for r in rows if r.engagement_id is not None and allowed.get(r.engagement_id)]
    hosts = {h.version_id: h for h in await review_hosts(ctx.tenant, [r.subject_id for r in mine])}
    facts: dict[UUID, GateFacts] = {}
    for row in mine:
        host = hosts.get(row.subject_id)
        if host is None:
            continue
        facts[row.id] = GateFacts(
            subject_route=subject_route(
                host.list_kind, host.list_id, host.work_item_id, host.item_id
            )
        )
    return facts


def register_review_gates() -> None:
    register_gate_source(SOURCE)
    register_gate_presenter(SUBJECT, present_reviews)


__all__ = ["SOURCE", "present_reviews", "register_review_gates", "subject_route"]
