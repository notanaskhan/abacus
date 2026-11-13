"""Engagements as run-trace samples (P-09-T08; WB-09 a2; `docs/contracts/agent-runs.md`).

A run step that read engagements names up to five of them; when someone opens the step, the
trace asks this module which the reader may see and what each reads as. Walls and roles apply as
in the engagement list (`visible(engagement.read_metadata)`); an engagement the reader may not
see is left out, never named.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.models import Engagement
from abacus.modules.identity.api import AuthContext, visible


@dataclass(frozen=True)
class TraceSampleRow:
    id: UUID
    label: str
    open_route: str


async def engagement_trace_samples(ctx: AuthContext, ids: Sequence[UUID]) -> list[TraceSampleRow]:
    if not ids:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(Engagement.id, Engagement.name).where(
                Engagement.id.in_(list(ids)),
                visible(ctx, "engagement.read_metadata", Engagement.id),
            )
        )
        return [TraceSampleRow(i, name, f"/engagements/{i}") for i, name in rows]
