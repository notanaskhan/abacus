"""The agent's proposals as human gates (P-04-T16; C13; DEC-28): screening results, upload
reviews, inbox matches and guidance drafts each wait on a person until one decides. Each is a
`proposal` gate. What waits is computed from the records here and evidence's answers
(`decided_among`, `waiting_among`, `withdrawn_among`), never from an event's payload, and output
of a run in shadow is never a gate (SPEC-036 AC-5).

- `screening_result`: the newest result of each version, while the version has no standing review
  decision and was not withdrawn.
- `upload_review`: the newest review of each version that raised a concern, likewise.
- `inbox_match`: the newest run of each inbox file that showed a proposal, while the file waits.
- `guidance_draft`: the newest draft of each request item that passed the checks, undecided.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.agents.repository import (
    latest_matches_for_gates,
    latest_screenings_for_gates,
    latest_upload_reviews_for_gates,
    suggestion_engagement_of,
    undecided_drafts_for_gates,
)
from abacus.modules.evidence.api import decided_among, waiting_among, withdrawn_among
from abacus.modules.review.api import (
    GateSource,
    OpenGate,
    register_gate_source,
    register_suggestion_owner,
)

Rows = Sequence[tuple[UUID, UUID, UUID]]  # (subject, engagement, what it is about)


async def _rows(
    tenant: TenantContext,
    engagement_id: UUID | None,
    read: Callable[[AsyncSession, UUID | None], Awaitable[Rows]],
) -> Rows:
    async with tenant_session(tenant) as session:
        return await read(session, engagement_id)


async def _on_live_versions(tenant: TenantContext, rows: Rows) -> list[OpenGate]:
    versions = [r[2] for r in rows]
    closed = await decided_among(tenant, versions) | await withdrawn_among(tenant, versions)
    return [OpenGate(r[0], r[1]) for r in rows if r[2] not in closed]


async def open_screenings(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    return await _on_live_versions(
        tenant, await _rows(tenant, engagement_id, latest_screenings_for_gates)
    )


async def open_upload_reviews(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    return await _on_live_versions(
        tenant, await _rows(tenant, engagement_id, latest_upload_reviews_for_gates)
    )


async def open_matches(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    rows = await _rows(tenant, engagement_id, latest_matches_for_gates)
    waiting = await waiting_among(tenant, [r[2] for r in rows])
    return [OpenGate(r[0], r[1]) for r in rows if r[2] in waiting]


async def open_drafts(tenant: TenantContext, engagement_id: UUID | None) -> list[OpenGate]:
    rows = await _rows(tenant, engagement_id, undecided_drafts_for_gates)
    return [OpenGate(r[0], r[1]) for r in rows]


_ON_VERSIONS = frozenset(
    {"proposal.recorded", "review_decision.recorded", "evidence_version.withdrawn"}
    | {"fulfilment.voided"}  # R-01 Story 2.2: its version is retired, as a withdrawal is
)
SOURCES = (
    GateSource("screening_result", "proposal", "review.read", _ON_VERSIONS, open_screenings),
    GateSource(
        "upload_review", "proposal", "upload_review.read", _ON_VERSIONS, open_upload_reviews
    ),
    GateSource(
        "inbox_match",
        "proposal",
        "inbox_match.read",
        frozenset({"proposal.recorded", "inbox_file.sorted"}),
        open_matches,
    ),
    GateSource(
        "guidance_draft",
        "proposal",
        "guidance_draft.read",
        frozenset({"proposal.recorded", "guidance_draft.decided"}),
        open_drafts,
    ),
)


def register_gate_sources() -> None:
    for source in SOURCES:
        register_gate_source(source)


__all__ = ["SOURCES", "register_gate_sources"]


async def suggestion_owner(tenant: TenantContext, suggestion_id: UUID) -> UUID | None:
    """P-04-T23: which engagement an agent suggestion belongs to (a decision card's
    recommendation must be its own engagement's)."""
    async with tenant_session(tenant) as session:
        return await suggestion_engagement_of(session, suggestion_id)


def register_suggestion_lookup() -> None:
    register_suggestion_owner(suggestion_owner)
