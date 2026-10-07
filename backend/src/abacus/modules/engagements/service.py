"""Engagement rules (TASK-008 design §3).

Authorise before any write: the route guard can hide a response but can't undo a commit.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from uuid import UUID, uuid4

from sqlalchemy import ColumnElement
from sqlalchemy.orm import QueryableAttribute

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Target, UnitOfWork, uow
from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.models import Engagement
from abacus.modules.engagements.repository import (
    client_column as _client_column,
)
from abacus.modules.engagements.repository import (
    get_engagement,
    insert_engagement,
    list_engagements,
    lock_engagement,
)
from abacus.modules.identity.api import (
    Actor,
    AuthContext,
    Resource,
    TeamMember,
    add_creator_as_partner,
    authorise,
    engagement_team,
)
from abacus.modules.organisations.api import ClientNames, client_names, create_client


@dataclass(frozen=True)
class EngagementRef:
    """Enough to authorise an action on an engagement. `archived` comes from the row
    (AUTHZ-003)."""

    tenant_id: UUID
    id: UUID
    archived: bool
    client_entity_id: UUID
    # The client, for ethical walls (SPEC-002): carried on the resource, so `authorise` needn't
    # look it up.
    client_id: UUID

    def resource(self) -> Resource:
        return Resource.engagement(
            self.tenant_id, self.id, archived=self.archived, client_id=self.client_id
        )


@dataclass(frozen=True)
class NewEngagement:
    name: str
    client_name: str
    client_entity_name: str
    fiscal_period_start: date
    fiscal_period_end: date


@dataclass(frozen=True)
class EngagementView:
    """What routes may see of an engagement: plain data, never the ORM row (ADR-012)."""

    id: UUID
    name: str
    type: str
    status: str
    client_name: str
    client_entity_name: str
    fiscal_period_start: date
    fiscal_period_end: date
    created_at: datetime


def _view(engagement: Engagement, names: ClientNames) -> EngagementView:
    return EngagementView(
        id=engagement.id,
        name=engagement.name,
        type=engagement.type,
        status=engagement.status,
        client_name=names.client_name,
        client_entity_name=names.client_entity_name,
        fiscal_period_start=engagement.fiscal_period_start,
        fiscal_period_end=engagement.fiscal_period_end,
        created_at=engagement.created_at,
    )


@dataclass(frozen=True)
class EngagementMetadata:
    engagement: EngagementView
    team: list[TeamMember]


def _ref(engagement: Engagement) -> EngagementRef:
    return EngagementRef(
        engagement.tenant_id,
        engagement.id,
        engagement.status == "archived",
        engagement.client_entity_id,
        engagement.client_id,
    )


async def get_ref(ctx: Actor, engagement_id: UUID) -> EngagementRef:
    """Raises `NotFound` when the engagement doesn't exist in the active tenant."""
    async with tenant_session(ctx.tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    if engagement is None:
        raise NotFound("engagement")
    return _ref(engagement)


async def lock_ref(tx: UnitOfWork, engagement_id: UUID) -> EngagementRef:
    """For writes: resolve and share-lock the engagement inside the caller's unit of work, then
    authorise against it there, so the check and the write see the same row. `NotFound` (404)
    when it isn't in the active tenant."""
    engagement = await lock_engagement(tx.session, engagement_id)
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
        await add_creator_as_partner(tx, ctx, engagement_id)
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
        view = _view(engagement, names[engagement.client_entity_id])
    team = await engagement_team(ctx, engagement_id)
    return EngagementMetadata(view, team)


async def engagements_for(ctx: AuthContext) -> Sequence[EngagementView]:
    async with tenant_session(ctx.tenant) as session:
        engagements = await list_engagements(session, ctx)
        names = await client_names(session, [e.client_entity_id for e in engagements])
        return [_view(e, names[e.client_entity_id]) for e in engagements]


def client_subquery(
    engagement_id: ColumnElement[UUID] | QueryableAttribute[UUID],
) -> ColumnElement[UUID]:
    """The engagement's client, as a subquery per row (for walls in `visible()`)."""
    return _client_column(engagement_id)


async def client_of(tenant: TenantContext, engagement_id: UUID) -> UUID | None:
    """The engagement's client, or None outside the tenant (for walls in `authorise`)."""
    async with tenant_session(tenant) as session:
        engagement = await get_engagement(session, engagement_id)
    return engagement.client_id if engagement is not None else None
