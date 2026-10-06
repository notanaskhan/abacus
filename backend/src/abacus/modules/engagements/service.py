"""Engagement rules (TASK-008 design §3).

Authorise before any write: the route guard can hide a response but can't undo a commit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID, uuid4

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, uow
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.repository import (
    get_engagement,
    insert_engagement,
    list_engagements,
)
from abacus.modules.identity.api import (
    AuthContext,
    Resource,
    TeamMember,
    add_engagement_member,
    authorise,
    engagement_team,
)
from abacus.modules.organisations.api import ClientNames, client_names, create_client

# The creator becomes the engagement partner (AC-4; TASK-008 Q2).
CREATOR_ROLE = "engagement_partner"


@dataclass(frozen=True)
class EngagementRef:
    """Enough to authorise an action on an engagement. `archived` comes from the row
    (AUTHZ-003)."""

    tenant_id: UUID
    id: UUID
    archived: bool

    def resource(self) -> Resource:
        return Resource.engagement(self.tenant_id, self.id, archived=self.archived)


@dataclass(frozen=True)
class NewEngagement:
    name: str
    client_name: str
    client_entity_name: str
    fiscal_period_start: date
    fiscal_period_end: date


@dataclass(frozen=True)
class EngagementMetadata:
    engagement: Engagement
    names: ClientNames
    team: list[TeamMember]


def _ref(engagement: Engagement) -> EngagementRef:
    return EngagementRef(engagement.tenant_id, engagement.id, engagement.status == "archived")


async def get_ref(ctx: AuthContext, engagement_id: UUID) -> EngagementRef:
    """Raises `NotFound` when the engagement doesn't exist in the active tenant."""
    async with tenant_session(ctx.tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    if engagement is None:
        raise NotFound("engagement")
    return _ref(engagement)


async def create_engagement(ctx: AuthContext, new: NewEngagement) -> EngagementMetadata:
    await authorise(ctx, "engagement.create", Resource.firm(ctx.tenant_id))
    engagement_id = uuid4()
    async with uow(ctx.tenant) as tx:
        client = await create_client(tx, ctx.tenant_id, new.client_name, new.client_entity_name)
        await insert_engagement(
            tx.session,
            engagement_id=engagement_id,
            tenant_id=ctx.tenant_id,
            client_id=client.client_id,
            client_entity_id=client.client_entity_id,
            name=new.name,
            fiscal_period_start=new.fiscal_period_start,
            fiscal_period_end=new.fiscal_period_end,
            created_by=ctx.user_id,
        )
        tx.record("engagement.created", target=Target("engagement", engagement_id))
        await add_engagement_member(tx, ctx, engagement_id, ctx.user_id, CREATOR_ROLE)
        tx.emit(EngagementCreated(engagement_id=engagement_id))
    return await _metadata(ctx, engagement_id)


async def engagement_metadata(ctx: AuthContext, engagement_id: UUID) -> EngagementMetadata:
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "engagement.read_metadata", ref.resource())
    return await _metadata(ctx, engagement_id)


async def _metadata(ctx: AuthContext, engagement_id: UUID) -> EngagementMetadata:
    async with tenant_session(ctx.tenant) as session:
        engagement = await get_engagement(session, engagement_id)
        if engagement is None:
            raise NotFound("engagement")
        names = await client_names(session, [engagement.client_entity_id])
    team = await engagement_team(ctx, engagement_id)
    return EngagementMetadata(engagement, names[engagement.client_entity_id], team)


@dataclass(frozen=True)
class EngagementSummary:
    engagement: Engagement
    names: ClientNames


async def engagements_for(ctx: AuthContext) -> Sequence[EngagementSummary]:
    async with tenant_session(ctx.tenant) as session:
        engagements = await list_engagements(session, ctx)
        names = await client_names(session, [e.client_entity_id for e in engagements])
    return [EngagementSummary(e, names[e.client_entity_id]) for e in engagements]
