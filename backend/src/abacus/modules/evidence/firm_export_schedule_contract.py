"""The firm export's monthly schedule: the security-center contract, v1 (G-02-T11 stub; SPEC-349
AC-25; DEC-72). Contract: `docs/contracts/security-center.md` §3.

Behind `security_center.v1`: off, every route here answers 404. Live since G-02-T19
(`firm_export_schedule.py`). Q-02's routes (`compliance-kernel.md` §4:
the on-demand request, approve, decline, link, and `GET /v1/firm/data-exports`, whose last 12
exports with `origin: scheduled` are the History tray) are unchanged and not repeated here.

The schedule runs only once a `security_admin` and a partner have each approved it, two distinct
people (DEC-72); any change to it takes it back to `pending_approval`. A second approval from the
same person or for the same seat answers 409 `approver_must_differ`. Each run notifies both.

These routes are mounted before Q-02's router: its `POST /{export_id}/approve` would otherwise
match `schedule/approve` and answer 422 for a path that is not an export id.

Authorisation comes first (security review L1): a client principal gets 404 (INV-4); the agent,
the system and anyone without the action get 403, before the flag is read.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import SECURITY_CENTER_V1
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.modules.evidence.firm_export_contract import FirmExportPersonOut
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]

ScheduleStatus = Literal["pending_approval", "active", "paused"]
# "Clients, entities, files, workpapers, returns, closes, audit log" (ADM-06 a's Contents row).
ExportContent = Literal[
    "clients", "entities", "files", "workpapers", "returns", "closes", "audit_log"
]
ApprovalSeat = Literal["security_admin", "partner"]


class ScheduleApprovalOut(BaseModel):
    """One seat's approval; when it was given is the audit log's
    (`firm_export_schedule.approved`)."""

    model_config = ConfigDict(frozen=True)

    seat: Annotated[ApprovalSeat, classified("internal")]
    approved_by: Annotated[FirmExportPersonOut, classified("internal")]


class FirmExportScheduleOut(BaseModel):
    """ADM-06 a's Data export card: "Monthly · 1st at 2:00 AM CT", contents, next run, and the
    approvals ("Two people: Felix Andersen + Margaret Okonkwo"). v1 has one cadence."""

    model_config = ConfigDict(frozen=True)

    cadence: Annotated[Literal["monthly"], classified("internal")]
    day_of_month: Annotated[Literal[1], classified("internal")]
    local_time: Annotated[Literal["02:00"], classified("internal")]
    time_zone: Annotated[str, classified("internal")]
    contents: Annotated[list[ExportContent], classified("internal")]
    status: Annotated[ScheduleStatus, classified("internal")]
    approvals: Annotated[
        list[ScheduleApprovalOut], Field(max_length=2), classified("internal")
    ] = Field(default_factory=list[ScheduleApprovalOut])
    next_run_on: Annotated[date | None, classified("internal")] = None
    version: Annotated[int, Field(ge=0), classified("internal")]


class FirmExportScheduleIn(BaseModel):
    """Set the schedule (`security_admin`); it waits for both approvals again. 409
    `stale_version`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contents: Annotated[list[ExportContent], Field(min_length=1), classified("internal")]
    paused: Annotated[bool, classified("internal")] = False
    version: Annotated[int, Field(ge=0), classified("internal")]


schedule_router = AbacusRouter(prefix="/v1/firm/data-exports/schedule", tags=["firm export"])


async def _gate(ctx: AuthContext, action: str) -> None:
    """L1: the matrix first (client 404; agent, system, no right or a stale factor 403), then
    the flag."""
    if ctx.client:
        raise NotFound("security_center")
    if ctx.tenant.actor_kind not in ("human", "support"):
        raise Forbidden(action, "role")  # ED-182's pattern: the agent and the system, first
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, SECURITY_CENTER_V1):
        raise NotFound("security_center.v1")


@schedule_router.get("", action="firm_export.read", response_model=FirmExportScheduleOut)
async def firm_export_schedule_route(ctx: Ctx) -> FirmExportScheduleOut:
    """The card; read by everyone who reads the export history (Margaret approves from it). 404
    when the firm has no schedule."""
    from abacus.modules.evidence import firm_export_schedule

    await _gate(ctx, "firm_export.read")
    return await firm_export_schedule.read(ctx)


@schedule_router.put(
    "", action="firm_export.schedule", response_model=FirmExportScheduleOut, errors=(409,)
)
async def put_firm_export_schedule_route(
    body: FirmExportScheduleIn, ctx: Ctx
) -> FirmExportScheduleOut:
    """`pending_approval` (or `paused`) until both seats approve again; 409 `stale_version`.
    Audited `firm_export_schedule.updated`."""
    from abacus.modules.evidence import firm_export_schedule

    await _gate(ctx, "firm_export.schedule")
    return await firm_export_schedule.put(ctx, body)


@schedule_router.post(
    "/approve",
    action="firm_export.approve",
    response_model=FirmExportScheduleOut,
    errors=(409,),
)
async def approve_firm_export_schedule_route(ctx: Ctx) -> FirmExportScheduleOut:
    """A `security_admin` or a partner approves once; the second distinct approver in the other
    seat makes it `active` (the firm's Temporal Schedule through `kernel.dispatch`). 409
    `approver_must_differ`, `schedule_paused`. Audited `firm_export_schedule.approved`."""
    from abacus.modules.evidence import firm_export_schedule

    await _gate(ctx, "firm_export.approve")
    return await firm_export_schedule.approve(ctx)
