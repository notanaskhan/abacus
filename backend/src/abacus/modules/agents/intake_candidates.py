"""The matcher's intake proposals as INB-02's candidates (N-01-T22 follow-up; DEC-1287).

communications reads them through the slot agents fills at import
(`register_intake_candidates`): for each attachment, its newest intake run's shown proposals, best
first, as (destination kind, id, confidence, match id). A none-fit run has none; a shadow run's are
never offered (SPEC-036 D2; N-01-T26); hidden proposals
(unverified quotes, or below the confidence the spec routes to a person) are never offered.
Identifiers and numbers only; communications re-checks that the reader may file there.
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session
from abacus.modules.communications.api import IntakeCandidate

# N-01-T26 (SPEC-036 D2): a shadow run's proposals are recorded and scored, never offered.
_NEWEST = text(
    "SELECT DISTINCT ON (m.inbox_attachment_id) m.inbox_attachment_id, m.id, m.none_fit "
    "FROM inbox_match_runs m JOIN agent_runs r ON r.id = m.agent_run_id "
    "WHERE m.inbox_attachment_id = ANY(:ids) AND NOT r.shadow "
    "ORDER BY m.inbox_attachment_id, m.created_at DESC, m.id DESC"
)
_SHOWN = text(
    "SELECT match_id, destination_kind, destination_id, confidence FROM inbox_match_proposals "
    "WHERE match_id = ANY(:matches) AND shown AND destination_kind IS NOT NULL "
    "ORDER BY match_id, rank"
)


async def intake_candidates(
    tenant: TenantContext, attachment_ids: Sequence[UUID]
) -> dict[UUID, list[IntakeCandidate]]:
    async with tenant_session(tenant) as session:
        runs = {
            r.id: r.inbox_attachment_id
            for r in (await session.execute(_NEWEST, {"ids": list(attachment_ids)})).all()
            if not r.none_fit
        }
        if not runs:
            return {}
        rows = (await session.execute(_SHOWN, {"matches": list(runs)})).all()
    out: dict[UUID, list[IntakeCandidate]] = {}
    for r in rows:
        attachment = runs[r.match_id]
        out.setdefault(attachment, []).append(
            IntakeCandidate(
                str(r.destination_kind),
                cast(UUID, r.destination_id),
                Decimal(str(r.confidence)),
                cast(UUID, r.match_id),
            )
        )
    return out
