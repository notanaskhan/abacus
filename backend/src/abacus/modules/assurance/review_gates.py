"""SPEC-004's review queue as C13 gates, registered by assurance, which may read requests, evidence
and review (ADR-008) (I-01-T08; I-01 OQ-2, DEC-403): an uploaded item's newest
live version waits on a person's review until a decision stands on it (an undo opens it again) or
it is withdrawn. Kind `evidence_review` (band Approvals & sends); one gate per version, assigned
to the reviewer who took it (`review_assignments`), else to everyone who may review the
engagement. Computed from requests' items and evidence's decisions, never from an event payload.
"""

from __future__ import annotations

from typing import Final
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.modules.evidence.api import decided_among, review_assignees, withdrawn_among
from abacus.modules.requests.api import awaiting_review
from abacus.modules.review.api import GateSource, OpenGate, register_gate_source

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


def register_review_gates() -> None:
    register_gate_source(SOURCE)


__all__ = ["SOURCE", "register_review_gates"]
