"""Completion, release and archive routes (SPEC-314; TASK-332)."""

from __future__ import annotations

from dataclasses import asdict
from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.assurance.completion import (
    CompletionView,
    approve_report,
    completion_for,
    concur,
    decide_going_concern,
    lock_archive,
    record_rep_letter,
    record_report,
    release,
)
from abacus.modules.assurance.dashboard import dashboard_for
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}/completion", tags=["completion"])
Ctx = Annotated[AuthContext, Depends(current_context)]


class DigestCardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    title: Annotated[str, classified("internal")]
    facts: Annotated[list[tuple[str, str]], classified("confidential")]
    decided: Annotated[bool, classified("internal")]


class ConcurrenceOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    by_name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    current: Annotated[bool, classified("internal")]


class EqrOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    required: Annotated[bool, classified("internal")]
    eqr_names: Annotated[list[str], classified("internal")]
    is_me: Annotated[bool, classified("internal")]
    digest: Annotated[list[DigestCardOut], classified("confidential")]
    digest_hash: Annotated[str, classified("internal")]
    concurrence: Annotated[ConcurrenceOut | None, classified("internal")]
    open_notes: Annotated[int, classified("internal")]


class CompletionRecordOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    choice: Annotated[str | None, classified("internal")]
    emphasis: Annotated[bool | None, classified("internal")]
    document_date: Annotated[date | None, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    rationale: Annotated[str | None, classified("confidential")]
    by_name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class ReportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    record: Annotated[CompletionRecordOut, classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]


class ReleaseOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    report_date: Annotated[date, classified("internal")]
    documentation_due: Annotated[date, classified("internal")]
    released_by_name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class ArchiveOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    seal: Annotated[str, classified("internal")]
    leaf_count: Annotated[int, classified("internal")]
    locked_by_name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class ChecklistItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[
        Literal[
            "accepted",
            "independence",
            "engagement_letter",
            "review_complete",
            "eqr_concurred",
            "going_concern",
            "report_approved",
            "rep_letter",
            "released",
            "archived",
        ],
        classified("internal"),
    ]
    done: Annotated[bool, classified("internal")]
    applicable: Annotated[bool, classified("internal")]
    gate: Annotated[str | None, classified("internal")]
    blockers: Annotated[list[str], classified("internal")]


class CompletionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    checklist: Annotated[list[ChecklistItemOut], classified("internal")]
    eqr: Annotated[EqrOut, classified("confidential")]
    going_concern: Annotated[CompletionRecordOut | None, classified("internal")]
    report: Annotated[ReportOut | None, classified("internal")]
    rep_letter: Annotated[CompletionRecordOut | None, classified("internal")]
    release: Annotated[ReleaseOut | None, classified("internal")]
    archive: Annotated[ArchiveOut | None, classified("internal")]
    can_release: Annotated[bool, classified("internal")]
    release_blockers: Annotated[list[str], classified("internal")]
    can_lock: Annotated[bool, classified("internal")]
    lock_blockers: Annotated[list[str], classified("internal")]


class ConcurBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    not_involved: Annotated[bool, classified("internal")]


class GoingConcernBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    choice: Annotated[
        Literal["no_substantial_doubt", "doubt_alleviated", "doubt_exists"], classified("internal")
    ]
    rationale: Annotated[str | None, Field(max_length=1000), classified("confidential")] = None


class ReportBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    opinion: Annotated[
        Literal["unmodified", "qualified", "adverse", "disclaimer"], classified("internal")
    ]
    emphasis: Annotated[bool, classified("internal")] = False
    report_date: Annotated[date, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]


class RepLetterBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    letter_date: Annotated[date, classified("internal")]
    evidence_version_id: Annotated[UUID, classified("internal")]


class AttestBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    attest: Annotated[bool, classified("internal")]


def _out(v: CompletionView) -> CompletionOut:
    return CompletionOut.model_validate(asdict(v))


@router.get("", action="completion.read", response_model=CompletionOut)
async def completion_state_route(engagement_id: UUID, ctx: Ctx) -> CompletionOut:
    """SPEC-314 AC-1: the checklist, the EQR digest, the records and what blocks release."""
    return _out(await completion_for(ctx, engagement_id))


@router.post("/eqr/concur", action="eqr.concur", response_model=CompletionOut, status_code=201)
async def concur_eqr_route(engagement_id: UUID, body: ConcurBody, ctx: Ctx) -> CompletionOut:
    """SPEC-314 AC-2: the engagement quality reviewer concurs (G6)."""
    await concur(ctx, engagement_id, body.not_involved)
    return _out(await completion_for(ctx, engagement_id))


@router.post(
    "/going-concern", action="completion.decide", response_model=CompletionOut, status_code=201
)
async def going_concern_route(
    engagement_id: UUID, body: GoingConcernBody, ctx: Ctx
) -> CompletionOut:
    """SPEC-314 AC-3: the partner decides going concern."""
    await decide_going_concern(ctx, engagement_id, body.choice, body.rationale)
    return _out(await completion_for(ctx, engagement_id))


@router.post("/report", action="completion.record", response_model=CompletionOut, status_code=201)
async def record_report_route(engagement_id: UUID, body: ReportBody, ctx: Ctx) -> CompletionOut:
    """SPEC-314 AC-4: record the report: opinion form, date and the final document."""
    await record_report(
        ctx, engagement_id, body.opinion, body.emphasis, body.report_date, body.evidence_version_id
    )
    return _out(await completion_for(ctx, engagement_id))


@router.post(
    "/report/approve", action="report.approve", response_model=CompletionOut, status_code=201
)
async def approve_report_route(engagement_id: UUID, ctx: Ctx) -> CompletionOut:
    """SPEC-314 AC-4: the partner approves the report record."""
    await approve_report(ctx, engagement_id)
    return _out(await completion_for(ctx, engagement_id))


@router.post(
    "/rep-letter", action="completion.record", response_model=CompletionOut, status_code=201
)
async def rep_letter_route(engagement_id: UUID, body: RepLetterBody, ctx: Ctx) -> CompletionOut:
    """SPEC-314 AC-5: record the signed representation letter (G7 needs the report date)."""
    await record_rep_letter(ctx, engagement_id, body.letter_date, body.evidence_version_id)
    return _out(await completion_for(ctx, engagement_id))


@router.post("/release", action="report.release", response_model=CompletionOut, status_code=201)
async def release_report_route(engagement_id: UUID, body: AttestBody, ctx: Ctx) -> CompletionOut:
    """SPEC-314 AC-6: the partner releases the report (G8)."""
    await release(ctx, engagement_id, body.attest)
    return _out(await completion_for(ctx, engagement_id))


@router.post("/archive/lock", action="archive.lock", response_model=CompletionOut, status_code=201)
async def lock_archive_route(engagement_id: UUID, body: AttestBody, ctx: Ctx) -> CompletionOut:
    """SPEC-314 AC-7: lock and seal the archive (G9)."""
    await lock_archive(ctx, engagement_id, body.attest)
    return _out(await completion_for(ctx, engagement_id))


# --- The engagement dashboard (SPEC-317; TASK-346) --------------------------------------------

dashboard_router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["dashboard"])


class GateFactOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    gate: Annotated[str, classified("internal")]
    met: Annotated[bool, classified("internal")]
    blockers: Annotated[list[str], classified("internal")]


class TileOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    value: Annotated[int, classified("internal")]
    total: Annotated[int | None, classified("internal")]
    attention: Annotated[bool, classified("internal")]


class NextItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[
        Literal["prepare", "review", "answer_note", "clear_note", "chase_request"],
        classified("internal"),
    ]
    label: Annotated[str, classified("confidential")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    code: Annotated[str | None, classified("internal")]


class DashboardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    gates: Annotated[list[GateFactOut], classified("internal")]
    tiles: Annotated[list[TileOut], classified("internal")]
    next_up: Annotated[list[NextItemOut], classified("confidential")]


@dashboard_router.get("/dashboard", action="dashboard.read", response_model=DashboardOut)
async def engagement_dashboard_route(engagement_id: UUID, ctx: Ctx) -> DashboardOut:
    """SPEC-317 AC-1: gates, progress tiles and what the caller can do next, all by code."""
    return DashboardOut.model_validate(asdict(await dashboard_for(ctx, engagement_id)))
