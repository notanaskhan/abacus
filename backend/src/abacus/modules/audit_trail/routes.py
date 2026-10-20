"""Audit log explorer routes (SPEC-304; TASK-305)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel.classification import classified
from abacus.kernel.uow import AuditFilter
from abacus.modules.audit_trail.service import events, facets
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/firm/audit-events", tags=["audit_trail"])
Ctx = Annotated[AuthContext, Depends(current_context)]


class EventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, classified("internal")]
    occurred_at: Annotated[datetime, classified("internal")]
    actor_kind: Annotated[str, classified("internal")]
    actor_id: Annotated[str, classified("internal")]
    actor_name: Annotated[str | None, classified("internal")]
    action: Annotated[str, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[str, classified("internal")]
    before_ref: Annotated[dict[str, str | int] | None, classified("internal")]
    after_ref: Annotated[dict[str, str | int] | None, classified("internal")]
    trace_id: Annotated[str | None, classified("internal")]


class EventPageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    events: Annotated[list[EventOut], classified("internal")]
    next_before: Annotated[int | None, classified("internal")]


class FacetsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    actions: Annotated[list[str], classified("internal")]
    target_types: Annotated[list[str], classified("internal")]


Text = Annotated[str | None, Query(max_length=200)]


@router.get("", action="audit.read", response_model=EventPageOut)
async def audit_events_route(
    ctx: Ctx,
    action: Text = None,
    actor_kind: Annotated[Literal["human", "agent", "system", "support"] | None, Query()] = None,
    actor_id: Text = None,
    target_type: Text = None,
    target_id: Text = None,
    since: Annotated[datetime | None, Query()] = None,
    until: Annotated[datetime | None, Query()] = None,
    before: Annotated[int | None, Query(ge=1)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 100,
) -> EventPageOut:
    """SPEC-304 AC-1, AC-2: the firm's trail, newest first; `next_before` pages back."""
    where = AuditFilter(action, actor_kind, actor_id, target_type, target_id, since, until)
    return EventPageOut.model_validate(asdict(await events(ctx, where, before, limit)))


@router.get("/facets", action="audit.read", response_model=FacetsOut)
async def audit_facets_route(ctx: Ctx) -> FacetsOut:
    """SPEC-304 AC-3: what the explorer can filter by."""
    actions, target_types = await facets(ctx)
    return FacetsOut(actions=actions, target_types=target_types)
