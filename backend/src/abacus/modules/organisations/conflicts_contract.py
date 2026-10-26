"""The conflict-check and screening contract, v1: CLI-06 a and h, CLI-08 c (P-07-T29 stub;
ADR-139, P-36). Contract: `docs/contracts/acceptance-independence.md` §Conflicts; spec: SPEC-332
Story 7; DEC-326.

Behind `engagements.acceptance_v2`: off, every route here answers 404; on, live since P-07-T36
(migration 0164 and `organisations.conflicts`; DEC-373).

- A check runs synchronously over at most 50 names, searching clients, client entities, contacts,
  relationships and engagement counterparties as a system principal over metadata only; the
  names are stored sealed (AC-23).
- A match on a client the person running the check is walled from is `{redacted: true,
  match_kind}`: no name, no client id, no link, no count beyond that row. No model here has a
  hidden-by-wall field (AC-24; DEC-43, DEC-64).
- Clearing a hit is a person's, with an assessment code and a reason; it is an insert-only event
  (AC-25). Screening results are recorded by a person, never looked up (AC-26).
- The agent and the system are denied every action here at the matrix (INV-1); no client role
  holds any.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import ENGAGEMENTS_ACCEPTANCE_V2
from abacus.kernel._statuses import ConflictAssessmentStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.organisations import conflicts

Ctx = Annotated[AuthContext, Depends(current_context)]

# P-07 §4.2 M6 (P-07-T36).
SubjectKind = Literal["client", "client_entity", "engagement_draft", "client_intake_draft"]
CheckOutcome = Literal["pending", "clear", "hits"]
MatchKind = Literal["exact", "trigram", "relationship", "counterparty"]
# AC-25's clearance codes; `conflict` joined the `conflict_assessment` vocabulary with P-07-T36.
ClearAssessment = Literal[
    "clear", "same_family_not_adverse", "not_adverse", "counterparty_review", "conflict"
]
ScreeningList = Literal["ofac_sdn", "adverse_media", "restricted_entities"]
ScreeningResult = Literal["no_match", "match", "not_applicable"]
Name = Annotated[SingleLineText, Field(min_length=1, max_length=200)]
Reason = Annotated[MultiLineText, Field(min_length=1, max_length=4000)]


class SubjectRefIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[SubjectKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class SubjectRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[SubjectKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class ConflictCheckIn(BaseModel):
    """The intake names to search (at most 50, sealed at rest) and what they are for."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    subject: Annotated[SubjectRefIn, classified("internal")]
    names: Annotated[list[Name], Field(min_length=1, max_length=50), classified("confidential")]


class ConflictResultOut(BaseModel):
    """One match. A redacted row (a client the caller is walled from) carries only `id`,
    `redacted`, `match_kind` and `assessment`: every other field is null."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    redacted: Annotated[bool, classified("internal")]
    match_kind: Annotated[MatchKind, classified("internal")]
    assessment: Annotated[ConflictAssessmentStatus, classified("internal")]  # C2
    matched_client_id: Annotated[UUID | None, classified("internal")] = None
    matched_name: Annotated[str | None, classified("confidential")] = None
    matched_ref_type: Annotated[str | None, classified("internal")] = None
    matched_ref_id: Annotated[UUID | None, classified("internal")] = None
    score: Annotated[float | None, classified("internal")] = None
    cleared_by: Annotated[UUID | None, classified("internal")] = None
    cleared_at: Annotated[datetime | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class ConflictCheckOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    subject: Annotated[SubjectRefOut, classified("internal")]
    names_count: Annotated[int, classified("internal")]
    outcome: Annotated[CheckOutcome, classified("internal")]
    run_by: Annotated[UUID, classified("internal")]
    run_at: Annotated[datetime, classified("internal")]
    results: Annotated[list[ConflictResultOut], classified("confidential")] = []
    # DEC-375: a match on a client this reader is walled from, as one flag (and one restricted
    # row), never a count or a kind.
    restricted_match: Annotated[bool, classified("internal")] = False


class ConflictClearIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    assessment: Annotated[ClearAssessment, classified("internal")]
    reason: Annotated[Reason, classified("confidential")]


class ScreeningRecordIn(BaseModel):
    """AC-26: a person records the result of a list they checked; nothing is looked up."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    subject: Annotated[SubjectRefIn, classified("internal")]
    screening_list: Annotated[ScreeningList, classified("internal")]
    result: Annotated[ScreeningResult, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    note: Annotated[Reason | None, classified("confidential")] = None


class ScreeningRecordOut(BaseModel):
    """Insert-only; reads "Recorded by {person}"."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    subject: Annotated[SubjectRefOut, classified("internal")]
    screening_list: Annotated[ScreeningList, classified("internal")]
    result: Annotated[ScreeningResult, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    recorded_by: Annotated[UUID, classified("internal")]
    recorded_at: Annotated[datetime, classified("internal")]


async def _gate(ctx: AuthContext, action: str) -> None:
    """Security review (DEC-326): authorise before the flag is read (the audits contract's
    order). Firm-level: no client principal, agent or system runs or reads a check. The service
    then requires a live person and authorises again."""
    if ctx.client or ctx.tenant.actor_kind != "human":
        raise Forbidden(action, "role")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, ENGAGEMENTS_ACCEPTANCE_V2):
        raise NotFound("engagements.acceptance_v2")


def _check_out(view: conflicts.CheckView) -> ConflictCheckOut:
    return ConflictCheckOut.model_validate(view, from_attributes=True)


conflict_checks_router = AbacusRouter(prefix="/v1/conflict-checks", tags=["conflicts"])
screening_records_router = AbacusRouter(prefix="/v1/screening-records", tags=["conflicts"])


@conflict_checks_router.post(
    "", action="conflict.run", response_model=ConflictCheckOut, status_code=201
)
async def run_conflict_check_route(body: ConflictCheckIn, ctx: Ctx) -> ConflictCheckOut:
    """AC-23, AC-24: synchronous, bounded (2-second statement timeout); `conflict_check.run`.
    A client or client-entity subject the caller cannot see answers 404."""
    await _gate(ctx, "conflict.run")
    view = await conflicts.run_conflict_check(
        ctx, subject_kind=body.subject.kind, subject_id=body.subject.id, names=body.names
    )
    return _check_out(view)


@conflict_checks_router.get("/{check_id}", action="conflict.run", response_model=ConflictCheckOut)
async def get_conflict_check_route(check_id: UUID, ctx: Ctx) -> ConflictCheckOut:
    """The check and its results, walled matches redacted for this reader."""
    await _gate(ctx, "conflict.run")
    return _check_out(await conflicts.conflict_check(ctx, check_id))


@conflict_checks_router.post(
    "/{check_id}/results/{result_id}/clear",
    action="conflict.clear",
    response_model=ConflictResultOut,
    errors=(409,),
)
async def clear_conflict_result_route(
    check_id: UUID, result_id: UUID, body: ConflictClearIn, ctx: Ctx
) -> ConflictResultOut:
    """Human-only (AC-25): an insert-only event; `conflict.cleared`. A result on a client the
    caller is walled from answers 404 like an unknown one."""
    await _gate(ctx, "conflict.clear")
    result = await conflicts.clear_conflict_result(
        ctx, check_id, result_id, assessment=body.assessment, reason=body.reason
    )
    return ConflictResultOut.model_validate(result, from_attributes=True)


@screening_records_router.post(
    "", action="screening.record", response_model=ScreeningRecordOut, status_code=201
)
async def record_screening_route(body: ScreeningRecordIn, ctx: Ctx) -> ScreeningRecordOut:
    """AC-26: insert-only; `screening.recorded`."""
    await _gate(ctx, "screening.record")
    recorded = await conflicts.record_screening(
        ctx,
        subject_kind=body.subject.kind,
        subject_id=body.subject.id,
        screening_list=body.screening_list,
        result=body.result,
        evidence_version_id=body.evidence_version_id,
        note=body.note,
    )
    return ScreeningRecordOut.model_validate(recorded, from_attributes=True)
