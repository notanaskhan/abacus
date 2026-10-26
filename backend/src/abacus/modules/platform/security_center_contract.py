"""The security-center contract, v1: ADM-06's platform half (G-02-T11 stub; SPEC-349 §5.7, §5.9;
ADR-139, P-36). Contract: `docs/contracts/security-center.md`.

Behind `security_center.v1`: off, every route here answers 404; on, 501 `not_implemented` until
G-02-T18 (the incident register's read side, timeline and decisions, on Q-02's kernel) and
G-02-T20 (the safeguards program). Q-02's `POST /v1/firm/security/incidents` (record an
incident, `compliance.incidents`) is unchanged and not repeated here.

Rules the shapes carry (INV-1, INV-5, DEC-72):

- **Two people decide an incident**: one partner and the Qualified Individual
  (`security_admin`), distinct, each with a fresh second factor. The first decider names the
  other (`second_decider_user_id`), and the incident reads "Waiting for" that person until they
  decide the same way; anyone else, or the same person twice, answers 409 `decider_must_differ`;
  a decided incident answers 409 `already_decided`.
- **The timeline is append-only and attributed**: no route edits or removes an entry. An Accrued
  entry (RB-27) carries `source: accrued` and no author.
- **The FTC clock is the kernel's**: `clock_day`, `ftc_notify_by` and the reminder dates come
  from `kernel.clock` in the firm's time zone (Q-02's `incident_clock`).
- **Safeguards edits are the QI's** (`security.manage`, `security_admin` only); partners read.
- **Authorisation comes first** (security review L1): a client principal gets 404 (INV-4); the
  agent, the system and anyone without the action get 403, before the flag is read.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Path, Query
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from abacus.kernel._flags import SECURITY_CENTER_V1
from abacus.kernel._statuses import SecurityIncidentStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

# Q-02's incident kinds and sources (`platform/incidents.py`), as the register returns them.
IncidentEventKind = Literal[
    "unauthorized_access",
    "credential_attack",
    "data_exposure",
    "lost_device",
    "vendor_incident",
    "other",
]
IncidentSource = Literal["firm", "accrued"]
DecisionKind = Literal["close_not_reportable", "start_notification"]
# Which seat a decider fills: a partner (`firm_partner`) or the QI (`security_admin`).
DeciderSeat = Literal["partner", "qualified_individual"]
TimelineSource = Literal["firm", "accrued", "system"]
TimelineCode = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{1,63}$")]
Fact = str | int | bool | None
ControlStatus = Literal["evidenced", "open"]
AccessReviewStatus = Literal["not_started", "in_progress", "complete"]
WispFormat = Literal["irs_pub_5708"]
WispPackStatus = Literal["preparing", "ready"]
ControlKey = Annotated[str, Path(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$")]


class GovernancePersonOut(BaseModel):
    """A person named on an incident or the safeguards record; the id links to ADM-02."""

    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]


class IncidentDecisionOut(BaseModel):
    """One decider's decision ("Close as not reportable" by Felix Andersen, QI)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[DecisionKind, classified("internal")]
    decided_by: Annotated[GovernancePersonOut, classified("internal")]
    seat: Annotated[DeciderSeat, classified("internal")]
    decided_at: Annotated[datetime, classified("internal")]


class IncidentPendingDecisionOut(BaseModel):
    """One of two decisions recorded: "Waiting for Margaret Okonkwo" (AC-22)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[DecisionKind, classified("internal")]
    first: Annotated[IncidentDecisionOut, classified("internal")]
    waiting_for: Annotated[GovernancePersonOut, classified("internal")]
    waiting_for_seat: Annotated[DeciderSeat, classified("internal")]


class SecurityIncidentOut(BaseModel):
    """A register row (ADM-06 a fieldset C): Q-02's entry with its clock, plus the status and
    the two-person decision. "Day 4 of 30 · notify by Oct 10 if ≥ 500" is `clock_day`,
    `clock_days` and `ftc_notify_by`; "Not a notification event" a closed entry whose
    `notification_event` is false."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    ref: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    event_kind: Annotated[IncidentEventKind, classified("internal")]
    discovered_at: Annotated[datetime, classified("internal")]
    consumers_affected: Annotated[int | None, Field(ge=0), classified("internal")] = None
    unencrypted: Annotated[bool | None, classified("internal")] = None
    notification_event: Annotated[bool, classified("internal")]
    ftc_notify_by: Annotated[date, classified("internal")]
    clock_day: Annotated[int, classified("internal")]
    clock_days: Annotated[int, classified("internal")]
    status: Annotated[SecurityIncidentStatus, classified("internal")]
    source: Annotated[IncidentSource, classified("internal")]
    accrued_ref: Annotated[str | None, classified("internal")] = None
    created_at: Annotated[datetime, classified("internal")]
    pending_decision: Annotated[IncidentPendingDecisionOut | None, classified("internal")] = None
    # Both decisions, once the second distinct decider has decided.
    decisions: Annotated[list[IncidentDecisionOut], classified("internal")] = Field(
        default_factory=list[IncidentDecisionOut]
    )
    notification_started_at: Annotated[datetime | None, classified("internal")] = None


class IncidentTimelineEntryOut(BaseModel):
    """One timeline entry (ADM-06 d), as a code and facts: "1,812 failed sign-ins from
    203.0.113.0/24 blocked" is `sign_ins_blocked` with `failed` and `network`. The SPA composes
    the words. Never edited or removed."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    occurred_at: Annotated[datetime, classified("internal")]
    code: Annotated[TimelineCode, classified("internal")]
    facts: Annotated[dict[str, Fact], classified("confidential")] = Field(
        default_factory=dict[str, Fact]
    )
    note: Annotated[str | None, classified("confidential")] = None
    source: Annotated[TimelineSource, classified("internal")]
    # Null for system and Accrued entries.
    author: Annotated[GovernancePersonOut | None, classified("internal")] = None
    recorded_at: Annotated[datetime, classified("internal")]


class SecurityIncidentDetailOut(SecurityIncidentOut):
    """The O2 480 drawer (ADM-06 d): the row plus its timeline, oldest first, and the reminder
    dates (days 20, 25 and 29 of the clock, to the QI and the partners)."""

    timeline: Annotated[list[IncidentTimelineEntryOut], classified("internal")] = Field(
        default_factory=list[IncidentTimelineEntryOut]
    )
    reminders_on: Annotated[list[date], classified("internal")] = Field(default_factory=list[date])


class SecurityIncidentPageOut(ListPage[SecurityIncidentOut]):
    """The P-36 envelope, newest discovery first; `counts` holds `open` and `closed`."""


class IncidentTimelineEntryIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    occurred_at: Annotated[AwareDatetime, classified("internal")]
    code: Annotated[TimelineCode, classified("internal")]
    facts: Annotated[dict[str, Fact], Field(max_length=20), classified("confidential")] = Field(
        default_factory=dict[str, Fact]
    )
    note: Annotated[
        SingleLineText | None, Field(default=None, max_length=500), classified("confidential")
    ]


class IncidentDecisionIn(BaseModel):
    """ "Close as not reportable…" or "Start notification…". The first decider names the second
    (a partner if the QI decides first, the QI if a partner does); the second decides the same
    `kind` and leaves `second_decider_user_id` out."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    kind: Annotated[DecisionKind, classified("internal")]
    second_decider_user_id: Annotated[UUID | None, classified("internal")] = None
    note: Annotated[
        SingleLineText | None, Field(default=None, max_length=500), classified("confidential")
    ]


class WispOut(BaseModel):
    """ "BH WISP v4 (IRS Pub 5708 format) · approved by Margaret Okonkwo Jan 15, 2026"; the
    document is an evidence item (FIL-01's drawer)."""

    model_config = ConfigDict(frozen=True)

    name: Annotated[str, classified("confidential")]
    format: Annotated[WispFormat, classified("internal")]
    evidence_item_id: Annotated[UUID | None, classified("internal")] = None
    approved_by: Annotated[GovernancePersonOut | None, classified("internal")] = None
    approved_on: Annotated[date | None, classified("internal")] = None


class SafeguardsControlOut(BaseModel):
    """One Pub 4557 control's status. `title` is the imported control definition's (platform
    content, never committed); "scheduled Oct 6, 2026" is `scheduled_on`, "due Nov 30, 2026"
    `due_on`."""

    model_config = ConfigDict(frozen=True)

    control_key: Annotated[str, classified("internal")]
    title: Annotated[str, classified("internal")]
    status: Annotated[ControlStatus, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None
    scheduled_on: Annotated[date | None, classified("internal")] = None
    evidence_item_id: Annotated[UUID | None, classified("internal")] = None


class AccessReviewOut(BaseModel):
    """ "Q3 2026 · due Sep 30, 2026 · in progress"."""

    model_config = ConfigDict(frozen=True)

    quarter: Annotated[str, Field(pattern=r"^\d{4}-Q[1-4]$"), classified("internal")]
    due_on: Annotated[date, classified("internal")]
    status: Annotated[AccessReviewStatus, classified("internal")]


class SafeguardsOut(BaseModel):
    """ADM-06 fieldset D (AC-27): the safeguards record and the Pub 4557 counts, with the open
    controls listed."""

    model_config = ConfigDict(frozen=True)

    qualified_individual: Annotated[GovernancePersonOut | None, classified("internal")] = None
    wisp: Annotated[WispOut | None, classified("internal")] = None
    annual_report_last_on: Annotated[date | None, classified("internal")] = None
    # "next due Dec 2026": a month, as the handoff gives it.
    annual_report_next_due_month: Annotated[
        str | None, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), classified("internal")
    ] = None
    controls_evidenced: Annotated[int, Field(ge=0), classified("internal")]
    controls_total: Annotated[int, Field(ge=0), classified("internal")]
    open_controls: Annotated[list[SafeguardsControlOut], classified("internal")] = Field(
        default_factory=list[SafeguardsControlOut]
    )
    training_completed: Annotated[int | None, Field(ge=0), classified("internal")] = None
    training_total: Annotated[int | None, Field(ge=0), classified("internal")] = None
    ptin_attested: Annotated[int | None, Field(ge=0), classified("internal")] = None
    ptin_total: Annotated[int | None, Field(ge=0), classified("internal")] = None
    access_review: Annotated[AccessReviewOut | None, classified("internal")] = None
    updated_at: Annotated[datetime | None, classified("internal")] = None
    updated_by: Annotated[GovernancePersonOut | None, classified("internal")] = None
    version: Annotated[int, Field(ge=0), classified("internal")]


class SafeguardsIn(BaseModel):
    """Fieldset D's Save (the QI only); 409 `stale_version`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    qualified_individual_user_id: Annotated[UUID | None, classified("internal")] = None
    wisp_evidence_item_id: Annotated[UUID | None, classified("internal")] = None
    wisp_approved_by_user_id: Annotated[UUID | None, classified("internal")] = None
    wisp_approved_on: Annotated[date | None, classified("internal")] = None
    annual_report_last_on: Annotated[date | None, classified("internal")] = None
    annual_report_next_due_month: Annotated[
        str | None, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$"), classified("internal")
    ] = None
    access_review_quarter: Annotated[
        str | None, Field(pattern=r"^\d{4}-Q[1-4]$"), classified("internal")
    ] = None
    access_review_due_on: Annotated[date | None, classified("internal")] = None
    access_review_status: Annotated[AccessReviewStatus | None, classified("internal")] = None
    training_completed: Annotated[int | None, Field(ge=0), classified("internal")] = None
    ptin_attested: Annotated[int | None, Field(ge=0), classified("internal")] = None
    ptin_total: Annotated[int | None, Field(ge=0), classified("internal")] = None
    version: Annotated[int, Field(ge=0), classified("internal")]


class SafeguardsControlIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    status: Annotated[ControlStatus, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None
    scheduled_on: Annotated[date | None, classified("internal")] = None
    evidence_item_id: Annotated[UUID | None, classified("internal")] = None
    note: Annotated[
        SingleLineText | None, Field(default=None, max_length=500), classified("confidential")
    ]


class WispPackOut(BaseModel):
    """ "WISP evidence pack prepared · 14 documents": one zip of the linked documents. The link is
    Restricted (it opens the firm's security documents) and never logged."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    status: Annotated[WispPackStatus, classified("internal")]
    document_count: Annotated[int | None, Field(ge=0), classified("internal")] = None
    file_name: Annotated[str | None, classified("internal")] = None
    requested_by: Annotated[GovernancePersonOut, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    download_url: Annotated[str | None, classified("restricted")] = None
    expires_at: Annotated[datetime | None, classified("internal")] = None


incident_reads_router = AbacusRouter(
    prefix="/v1/firm/security/incidents", tags=["security incidents"]
)
safeguards_router = AbacusRouter(prefix="/v1/firm/safeguards", tags=["security center"])


async def _authorised(ctx: AuthContext, action: str) -> None:
    """L1: the matrix first. A client principal gets 404 (INV-4); everyone else is authorised at
    the firm, so the agent, the system, a person without the action and a stale second factor
    are refused (403) whatever the flag."""
    if ctx.client:
        raise NotFound("security_center")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    await _authorised(ctx, action)
    if not await flag_enabled(ctx.tenant, SECURITY_CENTER_V1):
        raise NotFound("security_center.v1")
    raise NotImplementedYet


@incident_reads_router.get(
    "", action="incident.read", response_model=SecurityIncidentPageOut, errors=(501,)
)
async def list_security_incidents_route(
    ctx: Ctx,
    status: Annotated[SecurityIncidentStatus | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=1024)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> SecurityIncidentPageOut:
    """ADM-06 a fieldset C (AC-21): newest discovery first, each with its clock at today's date
    in the firm's time zone."""
    await _stub(ctx, "incident.read")


@incident_reads_router.get(
    "/{incident_id}",
    action="incident.read",
    response_model=SecurityIncidentDetailOut,
    errors=(501,),
)
async def security_incident_route(incident_id: UUID, ctx: Ctx) -> SecurityIncidentDetailOut:
    """ADM-06 d: the drawer; 404 for another firm's or an unknown incident."""
    await _stub(ctx, "incident.read")


@incident_reads_router.post(
    "/{incident_id}/timeline",
    action="incident.manage",
    response_model=IncidentTimelineEntryOut,
    status_code=201,
    errors=(501,),
)
async def append_incident_timeline_route(
    incident_id: UUID, body: IncidentTimelineEntryIn, ctx: Ctx
) -> IncidentTimelineEntryOut:
    """AC-23: append one attributed entry (the QI). Audited `incident.timeline_appended`."""
    await _stub(ctx, "incident.manage")


@incident_reads_router.post(
    "/{incident_id}/decisions",
    action="incident.decide",
    response_model=SecurityIncidentOut,
    errors=(409, 501),
)
async def decide_security_incident_route(
    incident_id: UUID, body: IncidentDecisionIn, ctx: Ctx
) -> SecurityIncidentOut:
    """AC-22: the first decider's call leaves `pending_decision` waiting for the person named;
    that person's same call completes it (`close_not_reportable` closes the incident;
    `start_notification` starts the notification). 409 `decider_must_differ` for the same
    person, the same seat or anyone not named; 409 `already_decided`; 422 when the first call
    names no second decider or names someone who cannot fill the other seat. Audited
    `incident.decision_recorded` per decider and `incident.decided` once complete."""
    await _stub(ctx, "incident.decide")


@safeguards_router.get("", action="security.read", response_model=SafeguardsOut, errors=(501,))
async def safeguards_route(ctx: Ctx) -> SafeguardsOut:
    """ADM-06 h fieldset D (AC-27)."""
    await _stub(ctx, "security.read")


@safeguards_router.put(
    "", action="security.manage", response_model=SafeguardsOut, errors=(409, 501)
)
async def put_safeguards_route(body: SafeguardsIn, ctx: Ctx) -> SafeguardsOut:
    """The QI saves the record; 409 `stale_version`. Audited `safeguards.updated`."""
    await _stub(ctx, "security.manage")


@safeguards_router.put(
    "/controls/{control_key}",
    action="security.manage",
    response_model=SafeguardsControlOut,
    errors=(501,),
)
async def put_safeguards_control_route(
    control_key: ControlKey, body: SafeguardsControlIn, ctx: Ctx
) -> SafeguardsControlOut:
    """One Pub 4557 control's status; 404 for a key the imported definitions don't have.
    Audited `safeguards_control.updated`."""
    await _stub(ctx, "security.manage")


@safeguards_router.post(
    "/wisp-pack",
    action="security.manage",
    response_model=WispPackOut,
    status_code=202,
    errors=(501,),
)
async def wisp_pack_route(ctx: Ctx) -> WispPackOut:
    """ "Export WISP pack": a zip of the WISP and its linked evidence (202). Audited
    `wisp_pack.prepared`."""
    await _stub(ctx, "security.manage")
