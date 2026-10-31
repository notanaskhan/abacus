"""People's triage decisions on intake attachments, for scoring the matcher (N-01-T26).

`agents.shadow_score` scores `evidence.matcher`'s intake proposals against what a person decided
on the same attachment (SPEC-036 Q1, chapter 10 QD-10): its decision, and where it filed the
attachment. Identifiers and codes only; `triage_decisions` is insert-only and every row is a live
person's (its CHECK), so the latest row up to an instant is the person's decision then.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from uuid import UUID

from sqlalchemy import text

from abacus.kernel.db import TenantContext, tenant_session

_LATEST = text(
    "SELECT DISTINCT ON (attachment_id) attachment_id, decision, destination_kind, "
    "destination_id, created_at FROM triage_decisions "
    "WHERE attachment_id = ANY(:ids) AND created_at <= :until "
    "ORDER BY attachment_id, created_at DESC, id DESC"
)


@dataclass(frozen=True)
class TriageOutcome:
    """A person's latest decision on one attachment: `file` (with where), `ignore` or `hold`."""

    attachment_id: UUID
    decision: str
    destination_kind: str | None
    destination_id: UUID | None
    at: datetime


async def triage_outcomes(
    tenant: TenantContext, attachment_ids: Sequence[UUID], until: datetime
) -> dict[UUID, TriageOutcome]:
    """Each attachment's latest triage decision made by `until` (none: not decided yet). The
    caller scores the firm's own runs; it reads no content."""
    if not attachment_ids:
        return {}
    async with tenant_session(tenant) as session:
        rows = (
            await session.execute(_LATEST, {"ids": list(attachment_ids), "until": until})
        ).all()
    return {
        cast(UUID, r.attachment_id): TriageOutcome(
            cast(UUID, r.attachment_id),
            str(r.decision),
            None if r.destination_kind is None else str(r.destination_kind),
            cast(UUID | None, r.destination_id),
            cast(datetime, r.created_at),
        )
        for r in rows
    }


__all__ = ["TriageOutcome", "triage_outcomes"]
