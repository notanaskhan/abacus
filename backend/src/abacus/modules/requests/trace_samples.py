"""Request items as run-trace samples (P-09-T08; WB-09 a2; `docs/contracts/agent-runs.md`).

The items a run step read, for the reader who opens the step: only those on engagements the
reader may read requests on (`visible(request_item.read)`, walls apply), each with its title (or
the first line of its description) and the request's own route.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.modules.engagements.api import TraceSampleRow
from abacus.modules.identity.api import AuthContext, visible
from abacus.modules.requests.models import RequestItem

_LABEL_CHARS = 120


def _label(title: str | None, description: str) -> str:
    text = (title or "").strip() or (description.strip().splitlines() or ["Request"])[0]
    return text[:_LABEL_CHARS]


async def request_item_trace_samples(
    ctx: AuthContext, ids: Sequence[UUID]
) -> list[TraceSampleRow]:
    if not ids:
        return []
    async with tenant_session(ctx.tenant) as session:
        rows = await session.execute(
            select(
                RequestItem.id,
                RequestItem.engagement_id,
                RequestItem.title,
                RequestItem.description,
            ).where(
                RequestItem.id.in_(list(ids)),
                visible(ctx, "request_item.read", RequestItem.engagement_id),
            )
        )
        return [
            TraceSampleRow(i, _label(title, description), f"/engagements/{e}/items/{i}")
            for i, e, title, description in rows
        ]
