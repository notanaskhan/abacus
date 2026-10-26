"""C13 home half, v1: `GET /v1/home` for HOME-01 (I-01-T02 stub; I-01 §4.3). Contract:
`docs/contracts/home-and-gates.md` part 2.

Behind `home.dashboard`: off, the route answers 404; on, 501 `not_implemented` until I-01-T10
(tiles, your work, deadlines, running count) and I-01-T12 (client activity). The queue and every
count of what waits on the viewer are not here: they are `review`'s C13 endpoints
(`GET /v1/human-gates`, `/counts`), so Home, HOME-02 and SHL-04 read one count source.

Rules the shapes carry:
- **Counts and identifiers.** Tiles come from owners through `platform.register_home_count`,
  already under `visible()`: counts, status codes, office ids and the filter a tile opens. An
  unregistered tile is absent, never zero.
- **Walls** leave a client out of every tile, row and activity item; nothing counts what was
  left out (DEC-43).
- **Offices filter, never authorise** (DEC-30): `office_id` narrows what the viewer may already
  see.
- **Client activity** rows carry codes, ids and counts (`facts`); labels are resolved at read time
  by their owners. No free text, no amounts (I-01 §4.2).
- **Risk** on a deadline is computed by code on `kernel.clock` (due-risk words in
  `status-vocabulary.yaml`, `due_risk`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import HOME_DASHBOARD
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
DueRisk = Literal["overdue", "due_soon", "approaching", "later"]
SegmentState = Literal["available", "planned", "entitlement_missing"]
ActorType = Literal["user", "contact", "agent_run", "system"]


class GreetingOut(BaseModel):
    """ "Good morning, Daniel" and the date, in the firm's time zone on `kernel.clock`."""

    model_config = ConfigDict(frozen=True)

    first_name: Annotated[str, classified("confidential")]
    date: Annotated[date, classified("internal")]


class TileStatusOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    n: Annotated[int, classified("internal")]
    filter: Annotated[str, classified("internal")]


class TileOfficeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    office_id: Annotated[UUID, classified("internal")]
    n: Annotated[int, classified("internal")]


class HomeTileOut(BaseModel):
    """One practice count tile ("Audits 27 · 17 Planning · 15 Fieldwork …"). `key` is the
    registered home count; `label` and `caption` are copy keys the SPA renders."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    caption: Annotated[str | None, classified("internal")]
    total: Annotated[int, classified("internal")]
    by_status: Annotated[list[TileStatusOut], classified("internal")]
    by_office: Annotated[list[TileOfficeOut], classified("internal")]
    target: Annotated[str, classified("internal")]


class WorkRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    client: Annotated[str, classified("confidential")]
    status: Annotated[str, classified("internal")]
    function: Annotated[str | None, classified("internal")]
    tags: Annotated[list[str], classified("internal")]


class YourWorkOut(BaseModel):
    """HOME-01 a2: the viewer's assigned work items; `label` is the band's copy key."""

    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("internal")]
    rows: Annotated[list[WorkRowOut], classified("confidential")]


class DeadlineRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    work_item_id: Annotated[UUID, classified("internal")]
    due_on: Annotated[date, classified("internal")]
    client: Annotated[str, classified("confidential")]
    filing_label: Annotated[str, classified("confidential")]
    status: Annotated[str, classified("internal")]
    risk: Annotated[DueRisk, classified("internal")]


class DeadlinesOut(BaseModel):
    """The viewer's next 14 days (interim source: work items' `due_on` and milestones; T-08 moves
    it to `filing_deadlines` without a shape change). `next` is the first one past the window."""

    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[DeadlineRowOut], classified("confidential")]
    next: Annotated[DeadlineRowOut | None, classified("confidential")]


class ActivityRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class ActivityActorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[ActorType, classified("internal")]
    id: Annotated[UUID | None, classified("internal")]
    label: Annotated[str | None, classified("confidential")]


class ClientActivityOut(BaseModel):
    """One timeline row: an allowlisted event about a client, with codes and counts only
    (`{"count": 2, "document_class": "health_insurance_form"}`)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    occurred_at: Annotated[datetime, classified("internal")]
    event_type: Annotated[str, classified("internal")]
    client_id: Annotated[UUID, classified("internal")]
    client_label: Annotated[str, classified("confidential")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    actor: Annotated[ActivityActorOut, classified("confidential")]
    subject: Annotated[ActivityRefOut, classified("internal")]
    facts: Annotated[dict[str, str | int | bool], classified("internal")]


class SegmentsOut(BaseModel):
    """DF-39: the Home segmented control's other options, each available, planned (hidden in
    production) or missing its entitlement (Insights, DEC-55)."""

    model_config = ConfigDict(frozen=True)

    deadlines: Annotated[SegmentState, classified("internal")]
    capacity: Annotated[SegmentState, classified("internal")]
    insights: Annotated[SegmentState, classified("internal")]


class HomeOut(BaseModel):
    """`HomeVM`: HOME-01 without the queue. The Approvals badge, the header count and the
    "Waiting on you" pane read `review`'s C13 counts and list."""

    model_config = ConfigDict(frozen=True)

    greeting: Annotated[GreetingOut, classified("confidential")]
    tiles: Annotated[list[HomeTileOut], classified("internal")]
    your_work: Annotated[YourWorkOut | None, classified("confidential")]
    deadlines: Annotated[DeadlinesOut, classified("confidential")]
    client_activity: Annotated[list[ClientActivityOut], classified("confidential")]
    running_count: Annotated[int | None, classified("internal")]
    segments: Annotated[SegmentsOut, classified("internal")]


router = AbacusRouter(prefix="/v1/home", tags=["practice"])


async def _stub(ctx: AuthContext) -> NoReturn:
    """The matrix first: a client principal answers 404 (INV-4); the agent, the system and any
    non-person are refused at the firm (403, INV-1). Then the flag, then 501."""
    if ctx.client:
        raise NotFound("home")
    await authorise(ctx, "home.read", Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, HOME_DASHBOARD):
        raise NotFound("home.dashboard")
    raise NotImplementedYet


@router.get("", action="home.read", response_model=HomeOut, errors=(501,))
async def home_route(ctx: Ctx, office_id: Annotated[UUID | None, Query()] = None) -> HomeOut:
    """HOME-01: the viewer's Home, optionally narrowed to one office (DEC-30)."""
    await _stub(ctx)
