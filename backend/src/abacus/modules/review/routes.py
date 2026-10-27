"""Review routes (SPEC-313; TASK-331): notes on any reviewable, and the sign-off matrix with
the G5 gate. Reads follow `workpaper.read`; notes `review_note.raise|respond|clear`."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.review.matrix import Matrix, matrix_for
from abacus.modules.review.notes import NoteView, add_event, notes_for, raise_note

router = AbacusRouter(prefix="/v1/engagements/{engagement_id}", tags=["review"])
Ctx = Annotated[AuthContext, Depends(current_context)]


class NoteEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[
        Literal["responded", "cleared", "reopened", "withdrawn"], classified("internal")
    ]
    body: Annotated[str | None, classified("confidential")]
    by_name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class ReviewNoteOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    target_code: Annotated[str | None, classified("internal")]
    anchor: Annotated[str | None, classified("confidential")]
    body: Annotated[str, classified("confidential")]
    status: Annotated[
        Literal["open", "responded", "cleared", "closed", "withdrawn"], classified("internal")
    ]
    raised_by_name: Annotated[str, classified("internal")]
    raised_at: Annotated[datetime, classified("internal")]
    raised_by_me: Annotated[bool, classified("internal")]
    events: Annotated[list[NoteEventOut], classified("confidential")]


class RaiseNoteBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_type: Annotated[str, Field(pattern=r"^[a-z][a-z_]{0,39}$"), classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    anchor: Annotated[str | None, Field(max_length=64), classified("confidential")] = None
    body: Annotated[str, Field(min_length=1, max_length=2000), classified("confidential")]


class NoteEventBody(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None


class MatrixLevelOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[int, classified("internal")]
    name: Annotated[
        Literal["preparer", "reviewer", "manager", "partner", "eqr"], classified("internal")
    ]
    signed_by_name: Annotated[str | None, classified("internal")]
    stale: Annotated[bool, classified("internal")]
    required: Annotated[bool, classified("internal")]


class MatrixRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    code: Annotated[str, classified("internal")]
    title: Annotated[str, classified("confidential")]
    levels: Annotated[list[MatrixLevelOut], classified("internal")]
    open_notes: Annotated[int, classified("internal")]
    status: Annotated[
        Literal[
            "not_started", "needs_sign_off", "changed_after_signoff", "open_notes", "complete"
        ],
        classified("internal"),
    ]
    missing: Annotated[list[int], classified("internal")]


class ReviewMatrixOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    rows: Annotated[list[MatrixRowOut], classified("confidential")]
    gate_met: Annotated[bool, classified("internal")]
    blockers: Annotated[list[str], classified("internal")]


def _notes_out(found: list[NoteView]) -> list[ReviewNoteOut]:
    return [ReviewNoteOut.model_validate(asdict(n)) for n in found]


def _matrix_out(m: Matrix) -> ReviewMatrixOut:
    return ReviewMatrixOut.model_validate(asdict(m))


@router.get("/review-notes", action="workpaper.read", response_model=list[ReviewNoteOut])
async def review_notes_route(
    engagement_id: UUID,
    ctx: Ctx,
    target_type: Annotated[str | None, Query(max_length=40)] = None,
    target_id: UUID | None = None,
) -> list[ReviewNoteOut]:
    """SPEC-313 AC-1: the engagement's notes, or one reviewable's."""
    return _notes_out(await notes_for(ctx, engagement_id, target_type, target_id))


@router.post(
    "/review-notes",
    action="review_note.raise",
    response_model=list[ReviewNoteOut],
    status_code=201,
)
async def raise_review_note_route(
    engagement_id: UUID, body: RaiseNoteBody, ctx: Ctx
) -> list[ReviewNoteOut]:
    """SPEC-313 AC-2: raise a note on a reviewable (optionally on a cell or an account)."""
    await raise_note(ctx, engagement_id, body.target_type, body.target_id, body.anchor, body.body)
    return _notes_out(await notes_for(ctx, engagement_id, body.target_type, body.target_id))


async def _event(
    ctx: AuthContext,
    engagement_id: UUID,
    note_id: UUID,
    kind: Literal["responded", "cleared", "reopened"],
    body: str | None,
) -> list[ReviewNoteOut]:
    await add_event(ctx, engagement_id, note_id, kind, body)
    return _notes_out(await notes_for(ctx, engagement_id))


@router.post(
    "/review-notes/{note_id}/respond",
    action="review_note.respond",
    response_model=list[ReviewNoteOut],
    status_code=201,
)
async def respond_review_note_route(
    engagement_id: UUID, note_id: UUID, body: NoteEventBody, ctx: Ctx
) -> list[ReviewNoteOut]:
    """SPEC-313 AC-3: answer a note."""
    return await _event(ctx, engagement_id, note_id, "responded", body.body)


@router.post(
    "/review-notes/{note_id}/clear",
    action="review_note.clear",
    response_model=list[ReviewNoteOut],
    status_code=201,
)
async def clear_review_note_route(
    engagement_id: UUID, note_id: UUID, body: NoteEventBody, ctx: Ctx
) -> list[ReviewNoteOut]:
    """SPEC-313 AC-3: the raiser (or the partner) clears a note."""
    return await _event(ctx, engagement_id, note_id, "cleared", body.body)


@router.post(
    "/review-notes/{note_id}/reopen",
    action="review_note.clear",
    response_model=list[ReviewNoteOut],
    status_code=201,
)
async def reopen_review_note_route(
    engagement_id: UUID, note_id: UUID, body: NoteEventBody, ctx: Ctx
) -> list[ReviewNoteOut]:
    """SPEC-313 AC-3: reopen a cleared note, with why."""
    return await _event(ctx, engagement_id, note_id, "reopened", body.body)


@router.get("/review-matrix", action="workpaper.read", response_model=ReviewMatrixOut)
async def review_matrix_route(engagement_id: UUID, ctx: Ctx) -> ReviewMatrixOut:
    """SPEC-313 AC-4, AC-5: every reviewable's levels and notes, and the G5 gate."""
    return _matrix_out(await matrix_for(ctx, engagement_id))
