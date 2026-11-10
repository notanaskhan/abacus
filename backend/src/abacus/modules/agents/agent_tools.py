"""The agents module's own read tools (P-10-T28; C17; ADR-233): `knowledge.search` over the
firm's knowledge documents and `activity.read` over the engagement agent's activity log. Both
tables belong to `agents`. Knowledge text is a document someone uploaded: untrusted for the model.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from abacus.kernel.agent_tools import MAX_ROWS, ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.agents.models import AgentActivity, KnowledgeChunk, KnowledgeDocument

Int = classified("internal")
Conf = classified("confidential")
SNIPPET: Final = 600


class KnowledgeIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: Annotated[str, Field(min_length=2, max_length=120), Conf]
    limit: Annotated[int, Field(ge=1, le=20), Int] = 8


class PassageRow(BaseModel):
    id: Annotated[UUID, Int]  # the knowledge document
    position: Annotated[int, Int]
    title: Annotated[str, Conf]
    heading_path: Annotated[str, Conf]
    excerpt: Annotated[str, Conf]


class KnowledgeOut(BaseModel):
    passages: Annotated[list[PassageRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]


class ActivityIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    since: Annotated[datetime | None, Int] = None


class ActivityRow(BaseModel):
    id: Annotated[UUID, Int]
    policy: Annotated[str, Int]
    action: Annotated[str, Int]
    outcome: Annotated[str, Int]
    record_type: Annotated[str | None, Int] = None
    record_id: Annotated[UUID | None, Int] = None
    item_count: Annotated[int | None, Int] = None
    created_at: Annotated[datetime, Int]


class ActivityOut(BaseModel):
    activity: Annotated[list[ActivityRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]
    by_outcome: Annotated[dict[str, int], Int]


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


async def search_knowledge(caller: ToolCaller, args: KnowledgeIn) -> KnowledgeOut:
    """Passages of the firm's ready, not-withdrawn knowledge documents that hold the text."""
    match = (
        KnowledgeDocument.status == "ready",
        KnowledgeDocument.withdrawn_at.is_(None),
        KnowledgeChunk.text.ilike(_like(args.text), escape="\\"),
    )
    async with tenant_session(caller.tenant) as session:
        base = select(KnowledgeChunk, KnowledgeDocument.title).join(
            KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id
        )
        total = await session.scalar(
            select(func.count())
            .select_from(KnowledgeChunk)
            .join(KnowledgeDocument, KnowledgeDocument.id == KnowledgeChunk.document_id)
            .where(*match)
        )
        rows = (
            await session.execute(
                base.where(*match)
                .order_by(KnowledgeDocument.created_at.desc(), KnowledgeChunk.position)
                .limit(args.limit)
            )
        ).tuples()
        passages = [
            PassageRow(
                id=chunk.document_id,
                position=chunk.position,
                title=title,
                heading_path=chunk.heading_path,
                excerpt=chunk.text[:SNIPPET],
            )
            for chunk, title in rows
        ]
    return KnowledgeOut(passages=passages, total=int(total or 0))


async def read_activity(caller: ToolCaller, args: ActivityIn) -> ActivityOut:
    engagement = args.engagement_id or caller.engagement_id
    if engagement is None:
        raise NotFound("engagement")
    where = [AgentActivity.engagement_id == engagement]
    if args.since is not None:
        where.append(AgentActivity.created_at >= args.since)
    async with tenant_session(caller.tenant) as session:
        counted = (
            await session.execute(
                select(AgentActivity.outcome, func.count())
                .where(*where)
                .group_by(AgentActivity.outcome)
            )
        ).tuples()
        by_outcome = {outcome: int(n) for outcome, n in counted}
        rows = (
            await session.execute(
                select(AgentActivity)
                .where(*where)
                .order_by(AgentActivity.created_at.desc(), AgentActivity.id)
                .limit(MAX_ROWS)
            )
        ).scalars()
        activity = [
            ActivityRow(
                id=a.id,
                policy=a.policy,
                action=a.action,
                outcome=a.outcome,
                record_type=a.record_type,
                record_id=a.record_id,
                item_count=a.item_count,
                created_at=a.created_at,
            )
            for a in rows
        ]
    return ActivityOut(activity=activity, total=sum(by_outcome.values()), by_outcome=by_outcome)


AGENT_TOOLS: Final = (
    ToolDecl(
        "knowledge.search", "read", "knowledge.read", "confidential", KnowledgeIn, KnowledgeOut,
        search_knowledge, untrusted=("passages",), records_read="knowledge_document",
    ),
    ToolDecl(
        "activity.read", "read", "activity.read", "internal", ActivityIn, ActivityOut,
        read_activity, records_read="agent_activity",
    ),
)  # fmt: skip
