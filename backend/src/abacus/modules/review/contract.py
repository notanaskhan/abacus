"""C3 v1, the review grammar (ADR-160; P-36 contract first). Stub PR 1 (P-04-T07): sign-offs,
review notes and the human-gate projection, the SHL-12 family.

Behind `review.grammar_api`: off, every route answers 404; on, 501 `not_implemented` until its
service lands (sign-offs P-04-T18, notes P-04-T21, the projection P-04-T16). Nothing here decides;
the shapes are what SHL-12, AUD-17 and HOME-02 read. `docs/contracts/review-grammar.md` part 1.

The level actions are the existing `sign_off.prepare|review|manager|partner|eqr` rows (L1 to L5);
`POST /v1/sign-offs` declares `sign_off.create` and the service also authorises the level's row.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import REVIEW_GRAMMAR_API
from abacus.kernel._statuses import ReviewNoteStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]

# ADR-160 clause 2: the level names are fixed; which levels a target requires is the firm's.
Level = Literal["L1_preparer", "L2_reviewer", "L3_manager", "L4_partner", "L5_eqr"]
SignOffKind = Literal["ladder", "field_tick", "final_approval"]
TargetType = Annotated[str, Field(pattern=r"^[a-z][a-z_]{0,39}$")]
# `sha256:` and the 64-hex digest of the target's canonical content (ADR-160 clause 3).
ContentHash = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
CheckCode = Literal[
    "open_review_notes",
    "independence",
    "segregation",
    "all_cited",
    "gate_g4",
    "open_issues",
    "eqr_limits",
]
CheckResult = Literal["pass", "fail", "warn"]
# Why a bulk item was left out (R-SO-7): the same fixed codes the single sign-off answers.
ExclusionCode = Literal[
    "content_changed",
    "segregation",
    "open_review_notes",
    "independence_pending",
    "incomplete",
    "uncited_change",
    "level_not_permitted",
]
AnchorKind = Literal["cell", "field", "section", "region"]
NoteEvent = Literal["raised", "responded", "cleared", "closed", "withdrawn", "reopened"]
GateKind = Literal[
    "decision", "sign_off_request", "proposal", "send", "final_approval", "export", "release"
]
GateState = Literal["open", "done", "voided"]


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, REVIEW_GRAMMAR_API):
        raise NotFound("review.grammar_api")
    raise NotImplementedYet


class ObjectRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: Annotated[str, classified("internal")]
    id: Annotated[UUID, classified("internal")]


# --- Sign-offs (SHL-12) ------------------------------------------------------------------------


class SignOffTargetOut(BaseModel):
    """What is being signed: the version and hash the signer sees (SHL-12 workpaper card)."""

    model_config = ConfigDict(frozen=True)

    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    context_label: Annotated[str, classified("confidential")]
    version_no: Annotated[int, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    cell_count: Annotated[int, classified("internal")]
    citation_count: Annotated[int, classified("internal")]


class SignOffOut(BaseModel):
    """One insert-only `sign_offs` row. `stale` is computed (its hash differs from the target's);
    no row is ever updated (ADR-160 clause 3)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    kind: Annotated[SignOffKind, classified("internal")]
    level: Annotated[Level, classified("internal")]
    signer_user_id: Annotated[UUID, classified("internal")]
    signer_name: Annotated[str, classified("internal")]
    initials: Annotated[str, classified("internal")]
    signed_at: Annotated[datetime, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    statement_version: Annotated[str, classified("internal")]
    # R-SO-8: an L1 on agent work records the run it adopted ("Performed by Agent run #4127
    # under the direction of <person> · adopted by <initials>").
    adopted_run_id: Annotated[UUID | None, classified("internal")]
    adopted_run_number: Annotated[int | None, classified("internal")]
    stale: Annotated[bool, classified("internal")]


class LadderLevelOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[Level, classified("internal")]
    required: Annotated[bool, classified("internal")]
    # Who the firm expects to sign this level, when it names someone (SHL-12 "Required ·
    # Margaret Okonkwo"); null when the level is open to any eligible person.
    expected_signer_user_id: Annotated[UUID | None, classified("internal")]
    expected_signer_name: Annotated[str | None, classified("internal")]
    # The newest sign-off at this level, or null; a stale one shows struck with only Re-sign.
    latest: Annotated[SignOffOut | None, classified("internal")]


class SignOffLadderOut(BaseModel):
    """`GET /v1/sign-offs`: the ladder per level on one target."""

    model_config = ConfigDict(frozen=True)

    target: Annotated[SignOffTargetOut, classified("confidential")]
    levels: Annotated[list[LadderLevelOut], classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class EligibilityCheckOut(BaseModel):
    """One "Before you sign" row. `facts` are counts, dates and names for the row's sentence;
    `refs` are what its link opens (the open notes, the issues)."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[CheckCode, classified("internal")]
    result: Annotated[CheckResult, classified("internal")]
    facts: Annotated[dict[str, str | int | bool | None], classified("confidential")]
    refs: Annotated[list[ObjectRefOut], classified("internal")]


class SignOffStatementOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    version: Annotated[str, classified("internal")]
    text: Annotated[str, classified("internal")]


class SignOffEligibilityOut(BaseModel):
    """`GET /v1/sign-offs/eligibility`: the SHL-12 sheet for one level."""

    model_config = ConfigDict(frozen=True)

    target: Annotated[SignOffTargetOut, classified("confidential")]
    level: Annotated[Level, classified("internal")]
    levels_allowed: Annotated[list[Level], classified("internal")]
    ladder: Annotated[list[LadderLevelOut], classified("internal")]
    checks: Annotated[list[EligibilityCheckOut], classified("confidential")]
    eligible: Annotated[bool, classified("internal")]
    statement: Annotated[SignOffStatementOut, classified("internal")]


class SignOffIn(BaseModel):
    """`POST /v1/sign-offs`: sign what was seen. A different current hash answers 409
    `content_changed` and nothing is written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_type: Annotated[TargetType, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    level: Annotated[Level, classified("internal")]
    kind: Annotated[SignOffKind, classified("internal")] = "ladder"
    seen_hash: Annotated[ContentHash, classified("internal")]
    statement_version: Annotated[str, Field(max_length=40), classified("internal")]


class BulkSignOffTargetIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_type: Annotated[TargetType, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    seen_hash: Annotated[ContentHash, classified("internal")]


class BulkSignOffIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    targets: Annotated[
        list[BulkSignOffTargetIn], Field(min_length=1, max_length=50), classified("internal")
    ]
    level: Annotated[Level, classified("internal")]
    statement_version: Annotated[str, Field(max_length=40), classified("internal")]


class BulkSignOffItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    ok: Annotated[bool, classified("internal")]
    sign_off_id: Annotated[UUID | None, classified("internal")]
    detail: Annotated[ExclusionCode | None, classified("internal")]


class BulkSignOffOut(BaseModel):
    """Each item decided on its own, atomically (R-SO-7). A replay with the same
    `Idempotency-Key` returns this stored result."""

    model_config = ConfigDict(frozen=True)

    results: Annotated[list[BulkSignOffItemOut], classified("internal")]
    signed: Annotated[int, classified("internal")]
    excluded: Annotated[int, classified("internal")]


sign_offs_router = AbacusRouter(prefix="/v1/sign-offs", tags=["review"])


@sign_offs_router.get("", action="sign_off.read", response_model=SignOffLadderOut, errors=(501,))
async def sign_off_ladder_route(
    ctx: Ctx,
    target_type: Annotated[str, Query(pattern=r"^[a-z][a-z_]{0,39}$")],
    target_id: Annotated[UUID, Query()],
) -> SignOffLadderOut:
    """SHL-12: the ladder per level, with computed staleness."""
    await _stub(ctx)


@sign_offs_router.get(
    "/eligibility", action="sign_off.read", response_model=SignOffEligibilityOut, errors=(501,)
)
async def sign_off_eligibility_route(
    ctx: Ctx,
    target_type: Annotated[str, Query(pattern=r"^[a-z][a-z_]{0,39}$")],
    target_id: Annotated[UUID, Query()],
    level: Annotated[Level, Query()],
) -> SignOffEligibilityOut:
    """SHL-12 a to h: target, levels allowed, checks and the statement for one level."""
    await _stub(ctx)


@sign_offs_router.post(
    "",
    action="sign_off.create",
    response_model=SignOffOut,
    status_code=201,
    errors=(409, 501),
)
async def sign_off_route(body: SignOffIn, ctx: Ctx) -> SignOffOut:
    """SHL-12 a-prime: record one sign-off (human only; the service also authorises the level)."""
    await _stub(ctx)


@sign_offs_router.post(
    ":bulk", action="sign_off.bulk", response_model=BulkSignOffOut, errors=(409, 501)
)
async def sign_off_bulk_route(
    body: BulkSignOffIn,
    ctx: Ctx,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> BulkSignOffOut:
    """SHL-12 f: sign several targets at one level; reviewers only."""
    await _stub(ctx)


# --- Review notes (AUD-17, SHL-12 b, SHL-09 a) -------------------------------------------------


class NoteAnchorIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[AnchorKind, classified("internal")]
    # A cell address ("RA!C14"), a field key, a section or a document region.
    ref: Annotated[SingleLineText, Field(min_length=1, max_length=120), classified("confidential")]


class NoteAnchorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[AnchorKind, classified("internal")]
    ref: Annotated[str, classified("confidential")]


class ReviewNoteItemOut(BaseModel):
    """A note in a list. Bodies are sealed and Restricted, so lists never carry them; the
    detail read does, as an access event."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    anchor: Annotated[NoteAnchorOut | None, classified("confidential")]
    status: Annotated[ReviewNoteStatus, classified("internal")]
    raised_by_user_id: Annotated[UUID, classified("internal")]
    raised_by_initials: Annotated[str, classified("internal")]
    raised_at: Annotated[datetime, classified("internal")]
    assignee_user_id: Annotated[UUID | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class ReviewNoteEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: Annotated[NoteEvent, classified("internal")]
    body: Annotated[str | None, classified("restricted")]
    actor_user_id: Annotated[UUID, classified("internal")]
    actor_name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class ReviewNoteOut(BaseModel):
    """One note with its sealed body and its insert-only events."""

    model_config = ConfigDict(frozen=True)

    note: Annotated[ReviewNoteItemOut, classified("confidential")]
    body: Annotated[str, classified("restricted")]
    events: Annotated[list[ReviewNoteEventOut], classified("restricted")]


class RaiseReviewNoteIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    target_type: Annotated[TargetType, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    anchor: Annotated[NoteAnchorIn | None, classified("confidential")] = None
    body: Annotated[MultiLineText, Field(min_length=1, max_length=2000), classified("restricted")]
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None


class ReviewNoteEventIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[MultiLineText | None, Field(max_length=2000), classified("restricted")] = None


review_notes_router = AbacusRouter(prefix="/v1/review-notes", tags=["review"])


@review_notes_router.get(
    "", action="review_note.read", response_model=ListPage[ReviewNoteItemOut], errors=(501,)
)
async def review_note_list_route(
    ctx: Ctx,
    target_type: Annotated[str | None, Query(pattern=r"^[a-z][a-z_]{0,39}$")] = None,
    target_id: Annotated[UUID | None, Query()] = None,
    engagement_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[ReviewNoteStatus | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> ListPage[ReviewNoteItemOut]:
    """Notes on a target or an engagement, on the list envelope with per-status counts."""
    await _stub(ctx)


@review_notes_router.get(
    "/{note_id}", action="review_note.read", response_model=ReviewNoteOut, errors=(501,)
)
async def review_note_route(note_id: UUID, ctx: Ctx) -> ReviewNoteOut:
    """One note with its body and events."""
    await _stub(ctx)


@review_notes_router.post(
    "",
    action="review_note.raise",
    response_model=ReviewNoteOut,
    status_code=201,
    errors=(501,),
)
async def review_note_raise_route(body: RaiseReviewNoteIn, ctx: Ctx) -> ReviewNoteOut:
    """Raise a note on a registered reviewable, optionally on an anchor."""
    await _stub(ctx)


@review_notes_router.post(
    "/{note_id}/respond",
    action="review_note.respond",
    response_model=ReviewNoteOut,
    errors=(409, 501),
)
async def review_note_respond_route(
    note_id: UUID, body: ReviewNoteEventIn, ctx: Ctx
) -> ReviewNoteOut:
    await _stub(ctx)


@review_notes_router.post(
    "/{note_id}/clear",
    action="review_note.clear",
    response_model=ReviewNoteOut,
    errors=(409, 501),
)
async def review_note_clear_route(
    note_id: UUID, body: ReviewNoteEventIn, ctx: Ctx
) -> ReviewNoteOut:
    """Clearing is a person's act (the event's CHECK requires a human)."""
    await _stub(ctx)


@review_notes_router.post(
    "/{note_id}/withdraw",
    action="review_note.withdraw",
    response_model=ReviewNoteOut,
    errors=(409, 501),
)
async def review_note_withdraw_route(
    note_id: UUID, body: ReviewNoteEventIn, ctx: Ctx
) -> ReviewNoteOut:
    """The raiser withdraws their own note."""
    await _stub(ctx)


# --- Human gates (C13 read; HOME-01/02) --------------------------------------------------------


class HumanGateOut(BaseModel):
    """One row of the rebuildable projection. Labels come from the subject's owner at read time."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[GateKind, classified("internal")]
    subject: Annotated[ObjectRefOut, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    work_item_id: Annotated[UUID | None, classified("internal")]
    client_id: Annotated[UUID | None, classified("internal")]
    assignee_user_id: Annotated[UUID | None, classified("internal")]
    role: Annotated[str | None, classified("internal")]
    due_on: Annotated[date | None, classified("internal")]
    state: Annotated[GateState, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


human_gates_router = AbacusRouter(prefix="/v1/human-gates", tags=["review"])


@human_gates_router.get(
    "", action="human_gate.read", response_model=ListPage[HumanGateOut], errors=(501,)
)
async def human_gate_list_route(
    ctx: Ctx,
    assignee: Annotated[Literal["me"], Query()] = "me",
    kind: Annotated[GateKind | None, Query()] = None,
    engagement_id: Annotated[UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> ListPage[HumanGateOut]:
    """What waits on the caller; `counts` are per kind ("3 decisions, 6 sign-offs, 2 exports")."""
    await _stub(ctx)
