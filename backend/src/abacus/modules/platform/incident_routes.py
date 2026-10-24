"""Security incident routes (Q-02-T33; Q-02 §4.3; contract `docs/contracts/security-incidents.md`).

Behind `compliance.incidents` (off: 404). A firm's QI records an incident and gets the computed
FTC clock back; platform staff propagate an Accrued incident into the firms it touched (RB-27),
answered 202 while `IncidentPropagation` writes each entry. G-02 builds the read side.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import (
    STAFF,
    AbacusRouter,
    AuthContext,
    Staff,
    current_context,
    current_staff,
)
from abacus.modules.platform.incidents import (
    CLOCK_DAYS,
    EventKind,
    IncidentFacts,
    IncidentView,
    Refusal,
    Source,
    propagation_log,
    record_incident,
    start_propagation,
)
from abacus.modules.platform.workflow_types import IncidentFactsInput

router = AbacusRouter(prefix="/v1/firm/security/incidents", tags=["security incidents"])
platform_router = AbacusRouter(prefix="/v1/platform/incidents", tags=["security incidents"])

Title = Annotated[SingleLineText, Field(min_length=1, max_length=200), classified("confidential")]
Consumers = Annotated[
    int | None, Field(default=None, ge=0, le=1_000_000_000), classified("internal")
]
AccruedRef = Annotated[str, Field(pattern=r"^[A-Z0-9][A-Z0-9-]{2,39}$")]


class IncidentIn(BaseModel):
    """What the QI knows when recording; counts and encryption may be unknown yet."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    title: Title
    event_kind: Annotated[EventKind, classified("internal")]
    discovered_at: Annotated[AwareDatetime, classified("internal")]
    consumers_affected: Consumers
    unencrypted: Annotated[bool | None, classified("internal")] = None


class IncidentOut(BaseModel):
    """One register entry with its clock: notify by `ftc_notify_by` when `notification_event`;
    `clock_day` of `clock_days` have passed in the firm's time zone."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    ref: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    event_kind: Annotated[EventKind, classified("internal")]
    discovered_at: Annotated[datetime, classified("internal")]
    consumers_affected: Annotated[int | None, classified("internal")] = None
    unencrypted: Annotated[bool | None, classified("internal")] = None
    notification_event: Annotated[bool, classified("internal")]
    ftc_notify_by: Annotated[date, classified("internal")]
    clock_day: Annotated[int, classified("internal")]
    clock_days: Annotated[int, classified("internal")]
    source: Annotated[Source, classified("internal")]
    accrued_ref: Annotated[str | None, classified("internal")] = None
    accrued_confirmed_at: Annotated[datetime | None, classified("internal")] = None
    dpa_notice_at: Annotated[datetime | None, classified("internal")] = None
    created_at: Annotated[datetime, classified("internal")]


def _out(view: IncidentView) -> IncidentOut:
    return IncidentOut(
        id=view.id,
        ref=view.ref,
        title=view.title,
        event_kind=view.event_kind,
        discovered_at=view.discovered_at,
        consumers_affected=view.consumers_affected,
        unencrypted=view.unencrypted,
        notification_event=view.notification_event,
        ftc_notify_by=view.ftc_notify_by,
        clock_day=view.clock_day,
        clock_days=CLOCK_DAYS,
        source=view.source,
        accrued_ref=view.accrued_ref,
        accrued_confirmed_at=view.accrued_confirmed_at,
        dpa_notice_at=view.dpa_notice_at,
        created_at=view.created_at,
    )


@router.post("", action="incident.manage", response_model=IncidentOut, status_code=201)
async def record_incident_route(
    body: IncidentIn, ctx: Annotated[AuthContext, Depends(current_context)]
) -> IncidentOut:
    """The QI records an incident (AC-38). 422 `discovered_in_future`."""
    view = await record_incident(
        ctx,
        IncidentFacts(
            title=body.title,
            event_kind=body.event_kind,
            discovered_at=body.discovered_at,
            consumers_affected=body.consumers_affected,
            unencrypted=body.unencrypted,
        ),
    )
    return _out(view)


# --- platform staff (RB-27) -------------------------------------------------------------------


class AccruedIncidentFactsIn(BaseModel):
    """Accrued's facts, the same for every firm it touched."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    title: Title
    event_kind: Annotated[EventKind, classified("internal")]
    discovered_at: Annotated[AwareDatetime, classified("internal")]
    confirmed_at: Annotated[AwareDatetime, classified("internal")]
    consumers_affected: Consumers
    unencrypted: Annotated[bool | None, classified("internal")] = None


class IncidentPropagationIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    tenant_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), classified("internal")]
    facts: Annotated[AccruedIncidentFactsIn, classified("confidential")]
    reason: Annotated[
        SingleLineText, Field(min_length=1, max_length=500), classified("confidential")
    ]


class IncidentPropagationOut(BaseModel):
    """`started`: the firms the run will write. `identical`: firms that already have this
    incident with these same facts, skipped rather than written again."""

    model_config = ConfigDict(frozen=True)

    accrued_ref: Annotated[str, classified("internal")]
    started: Annotated[list[UUID], classified("internal")]
    identical: Annotated[list[UUID], classified("internal")]


class IncidentPropagationEventOut(BaseModel):
    """One staff request (`requested`, `refused` with its reason code) or one run's end
    (`completed`, with the firms that failed every attempt)."""

    model_config = ConfigDict(frozen=True)

    recorded_at: Annotated[datetime, classified("internal")]
    event: Annotated[Literal["requested", "refused", "completed"], classified("internal")]
    staff_id: Annotated[UUID, classified("internal")]
    firms: Annotated[int, classified("internal")]
    written: Annotated[int, classified("internal")]
    identical: Annotated[int, classified("internal")]
    failed_tenant_ids: Annotated[list[UUID], classified("internal")]
    refusal: Annotated[Refusal | None, classified("internal")] = None


class IncidentPropagationLogOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[IncidentPropagationEventOut], classified("internal")]


@platform_router.post(
    "/{accrued_ref}/propagate",
    action=STAFF,
    response_model=IncidentPropagationOut,
    status_code=202,
    errors=(409,),
)
async def propagate_incident_route(
    accrued_ref: AccruedRef,
    body: IncidentPropagationIn,
    staff: Annotated[Staff, Depends(current_staff)],
) -> IncidentPropagationOut:
    """Staff only (`platform.incident.propagate`, DEC-227): start writing Accrued's facts into
    each named firm's register (AC-39). 404 when a firm doesn't exist or has the register off;
    409 `incident_facts_changed` when a firm already has it with other facts, or
    `incident_propagation_running`; 422 `confirmed_out_of_order`. Every request is recorded,
    refused ones included (`GET …/propagations`)."""
    facts = body.facts
    outcome = await start_propagation(
        staff.id,
        accrued_ref,
        body.tenant_ids,
        IncidentFactsInput(
            title=facts.title,
            event_kind=facts.event_kind,
            discovered_at=facts.discovered_at.isoformat(),
            consumers_affected=facts.consumers_affected,
            unencrypted=facts.unencrypted,
            confirmed_at=facts.confirmed_at.isoformat(),
        ),
        body.reason,
    )
    return IncidentPropagationOut(
        accrued_ref=accrued_ref, started=outcome.started, identical=outcome.identical
    )


@platform_router.get(
    "/{accrued_ref}/propagations", action=STAFF, response_model=IncidentPropagationLogOut
)
async def incident_propagation_log_route(
    accrued_ref: AccruedRef, staff: Annotated[Staff, Depends(current_staff)]
) -> IncidentPropagationLogOut:
    """Staff: every request and run end for this Accrued incident, oldest first, with the
    firms a run could not write (RB-27 follows up each by its manual step)."""
    return IncidentPropagationLogOut(
        items=[
            IncidentPropagationEventOut(
                recorded_at=e.recorded_at,
                event=e.event,
                staff_id=e.staff_id,
                firms=e.firms,
                written=e.written,
                identical=e.identical,
                failed_tenant_ids=list(e.failed_tenant_ids),
                refusal=e.refusal,
            )
            for e in await propagation_log(accrued_ref)
        ]
    )
