"""Engagement read tools for the Accrued Agent (P-10-T28; C17; ADR-233, ADR-049, ADR-050).

Declared here as `ToolDecl` records (`kernel.agent_tools`, the ADR-106 slot) and registered by
`agents`. The runtime has authorised `engagement.read` on every engagement and client an argument
names (or the run's engagement), inside the run's pinned `client_scope`; each handler reads only
those rows. Rows carry ids; totals are counted here, never by the model.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from abacus.kernel.agent_tools import MAX_ROWS, ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.kernel.db import tenant_session
from abacus.kernel.errors import NotFound
from abacus.modules.engagements.models import Engagement
from abacus.modules.identity.api import ROLE_LABELS, names_of, team_of
from abacus.modules.methodology.api import StepIn, StepOut, step_of_version
from abacus.modules.organisations.api import client_names

Int = classified("internal")
Conf = classified("confidential")
READ: Final = "engagement.read"


def _in() -> ConfigDict:
    return ConfigDict(extra="forbid", frozen=True)


def _engagement(caller: ToolCaller, named: UUID | None) -> UUID:
    found = named or caller.engagement_id
    if found is None:
        raise NotFound("engagement")  # a firm-level run names its engagement
    return found


class EngagementIn(BaseModel):
    model_config = _in()

    engagement_id: Annotated[UUID | None, Int] = None


class ClientEngagementsIn(BaseModel):
    model_config = _in()

    client_id: Annotated[UUID | None, Int] = None


class EngagementRow(BaseModel):
    id: Annotated[UUID, Int]
    name: Annotated[str, Conf]
    type: Annotated[str, Int]
    status: Annotated[str, Int]
    fiscal_period_start: Annotated[date, Int]
    fiscal_period_end: Annotated[date, Int]
    period_label: Annotated[str | None, Conf] = None


class EngagementsOut(BaseModel):
    engagements: Annotated[list[EngagementRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]


class EngagementOut(BaseModel):
    id: Annotated[UUID, Int]
    name: Annotated[str, Conf]
    type: Annotated[str, Int]
    service_line: Annotated[str, Int]
    status: Annotated[str, Int]
    fiscal_period_start: Annotated[date, Int]
    fiscal_period_end: Annotated[date, Int]
    period_label: Annotated[str | None, Conf] = None
    client_id: Annotated[UUID, Int]
    client_entity_id: Annotated[UUID, Int]


class EntityRow(BaseModel):
    id: Annotated[UUID, Int]
    name: Annotated[str, Conf]


class EngagementGraphOut(BaseModel):
    """The engagement, its client and entity, and what it rolls from."""

    engagement_id: Annotated[UUID, Int]
    client_id: Annotated[UUID, Int]
    client_name: Annotated[str, Conf]
    entities: Annotated[list[EntityRow], Field(max_length=MAX_ROWS), Int]
    prior_engagement_id: Annotated[UUID | None, Int] = None
    methodology_version_id: Annotated[UUID | None, Int] = None


class MemberRow(BaseModel):
    id: Annotated[UUID, Int]  # the person's user id
    name: Annotated[str, Conf]
    role: Annotated[str, Int]
    role_label: Annotated[str, Int]


class TeamOut(BaseModel):
    members: Annotated[list[MemberRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]


async def _row(caller: ToolCaller, engagement_id: UUID) -> Engagement:
    async with tenant_session(caller.tenant) as session:
        found = await session.get(Engagement, engagement_id)
    if found is None:
        raise NotFound("engagement")
    return found


async def list_engagements(caller: ToolCaller, args: ClientEngagementsIn) -> EngagementsOut:
    """The client's engagements (the run engagement's client when none is named)."""
    client = args.client_id or (await _row(caller, _engagement(caller, None))).client_id
    async with tenant_session(caller.tenant) as session:
        total = await session.scalar(
            select(func.count()).select_from(Engagement).where(Engagement.client_id == client)
        )
        rows = (
            await session.execute(
                select(Engagement)
                .where(Engagement.client_id == client)
                .order_by(Engagement.fiscal_period_end.desc(), Engagement.id)
                .limit(MAX_ROWS)
            )
        ).scalars()
        found = [
            EngagementRow(
                id=e.id,
                name=e.name,
                type=e.type,
                status=e.status,
                fiscal_period_start=e.fiscal_period_start,
                fiscal_period_end=e.fiscal_period_end,
                period_label=e.period_label,
            )
            for e in rows
        ]
    return EngagementsOut(engagements=found, total=int(total or 0))


async def read_engagement(caller: ToolCaller, args: EngagementIn) -> EngagementOut:
    e = await _row(caller, _engagement(caller, args.engagement_id))
    return EngagementOut(
        id=e.id,
        name=e.name,
        type=e.type,
        service_line=e.service_line,
        status=e.status,
        fiscal_period_start=e.fiscal_period_start,
        fiscal_period_end=e.fiscal_period_end,
        period_label=e.period_label,
        client_id=e.client_id,
        client_entity_id=e.client_entity_id,
    )


async def read_graph(caller: ToolCaller, args: EngagementIn) -> EngagementGraphOut:
    e = await _row(caller, _engagement(caller, args.engagement_id))
    async with tenant_session(caller.tenant) as session:
        names = await client_names(session, [e.client_entity_id])
    found = names.get(e.client_entity_id)
    entities = [EntityRow(id=e.client_entity_id, name=found.client_entity_name)] if found else []
    return EngagementGraphOut(
        engagement_id=e.id,
        client_id=e.client_id,
        client_name=found.client_name if found else "",
        entities=entities,
        prior_engagement_id=e.prior_engagement_id,
        methodology_version_id=e.methodology_version_id,
    )


async def read_team(caller: ToolCaller, args: EngagementIn) -> TeamOut:
    engagement = _engagement(caller, args.engagement_id)
    members = [
        (u, r)
        for u, r in await team_of(caller.tenant.tenant_id, engagement)
        if r != "client_service"
    ]
    names = await names_of([u for u, _ in members])
    rows = [
        MemberRow(id=u, name=names.get(u, ""), role=r, role_label=ROLE_LABELS.get(r, r))
        for u, r in sorted(members, key=lambda m: (names.get(m[0], "").casefold(), str(m[0])))
    ]
    return TeamOut(members=rows[:MAX_ROWS], total=len(rows))


async def read_step(caller: ToolCaller, args: StepIn) -> StepOut:
    """`methodology.read_step`: a step of the engagement's pinned methodology version."""
    e = await _row(caller, _engagement(caller, args.engagement_id))
    if e.methodology_version_id is None:
        raise NotFound("program_step")  # no methodology pinned yet
    return await step_of_version(caller, e.methodology_version_id, args.step_key)


AGENT_TOOLS: Final = (
    ToolDecl(
        "engagements.list", "read", READ, "confidential", ClientEngagementsIn, EngagementsOut,
        list_engagements, records_read="engagement",
    ),
    ToolDecl(
        "engagements.read", "read", READ, "confidential", EngagementIn, EngagementOut,
        read_engagement, records_read="engagement",
    ),
    ToolDecl(
        "engagements.read_graph", "read", READ, "confidential", EngagementIn,
        EngagementGraphOut, read_graph, records_read="engagement",
    ),
    ToolDecl(
        "engagements.read_team", "read", READ, "confidential", EngagementIn, TeamOut, read_team,
        records_read="engagement_member",
    ),
    ToolDecl(
        "methodology.read_step", "read", "methodology.read", "internal", StepIn, StepOut,
        read_step, records_read="program_step",
    ),
)  # fmt: skip
