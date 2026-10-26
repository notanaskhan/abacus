"""C3 v1, the review grammar (ADR-160; P-36 contract first). Stub PR 1 (P-04-T07): sign-offs,
review notes and the human-gate projection, the SHL-12 family. Stub PR 2 (P-04-T08): decision
cards, the SHL-11 family; proposals and suggestions are the agents module's (ADR-161). Stub PR 3
(P-04-T11): issues and fix instructions (SHL-15), checkpoints (SHL-16) and field provenance
(SHL-09), an additive extension of the C3 v1 schema.

Behind `review.grammar_api`: off, every route answers 404; on, 501 `not_implemented` until its
service lands (sign-offs P-04-T18, notes P-04-T21, the projection P-04-T16, decision cards
P-04-T23, issues P-04-T30 and T31, checkpoints P-04-T32, field values P-04-T35). Nothing here
decides; the shapes are what SHL-09, SHL-11, SHL-12, SHL-15, SHL-16, AUD-17 and HOME-02 read.
`docs/contracts/review-grammar.md` parts 1 to 3.

The level actions are the existing `sign_off.prepare|review|manager|partner|eqr` rows (L1 to L5);
`POST /v1/sign-offs` declares `sign_off.create` and the service also authorises the level's row.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import REVIEW_GRAMMAR_API
from abacus.kernel._statuses import (
    AgentRunStatus,
    CheckpointStatus,
    DecisionCardStatus,
    IssueSeverityStatus,
    IssueStatus,
    ReviewNoteStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.review.gates import gates_waiting_on
from abacus.modules.review.sign_offs import (
    LEVEL_CODES,
    LEVEL_OF,
    LadderLevel,
    SignOffView,
    eligibility,
    hash_out,
    ladder,
    sign_target,
)
from abacus.modules.review.slots import ReviewableFacts

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


async def _live(ctx: AuthContext) -> None:
    """A live route behind the same flag: off, it answers 404 like its stub did."""
    if not await flag_enabled(ctx.tenant, REVIEW_GRAMMAR_API):
        raise NotFound("review.grammar_api")


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


def _target_out(facts: ReviewableFacts) -> SignOffTargetOut:
    return SignOffTargetOut(
        target_type=facts.target_type,
        target_id=facts.target_id,
        label=facts.label or facts.target_type.replace("_", " ").capitalize(),
        context_label=facts.context_label,
        version_no=facts.version_no,
        content_hash=hash_out(facts.content_hash),
        cell_count=facts.cell_count,
        citation_count=facts.citation_count,
    )


def _sign_off_out(v: SignOffView) -> SignOffOut:
    return SignOffOut(
        id=v.id,
        target_type=v.target_type,
        target_id=v.target_id,
        kind=cast(SignOffKind, v.kind),
        level=LEVEL_CODES[v.level],
        signer_user_id=v.signer_user_id,
        signer_name=v.signer_name,
        initials=v.initials,
        signed_at=v.signed_at,
        content_hash=v.content_hash,
        version_no=v.version_no,
        statement_version=v.statement_version,
        adopted_run_id=v.adopted_run_id,
        adopted_run_number=v.adopted_run_number,
        stale=v.stale,
    )


def _ladder_out(levels: list[LadderLevel]) -> list[LadderLevelOut]:
    return [
        LadderLevelOut(
            level=LEVEL_CODES[lv.level],
            required=lv.required,
            expected_signer_user_id=None,
            expected_signer_name=None,
            latest=_sign_off_out(lv.latest) if lv.latest is not None else None,
        )
        for lv in levels
    ]


@sign_offs_router.get("", action="sign_off.read", response_model=SignOffLadderOut, errors=(501,))
async def sign_off_ladder_route(
    ctx: Ctx,
    target_type: Annotated[str, Query(pattern=r"^[a-z][a-z_]{0,39}$")],
    target_id: Annotated[UUID, Query()],
) -> SignOffLadderOut:
    """SHL-12: the ladder per level, with computed staleness (P-04-T18)."""
    await _live(ctx)
    found = await ladder(ctx, target_type, target_id)
    return SignOffLadderOut(
        target=_target_out(found.facts),
        levels=_ladder_out(found.levels),
        allowed_actions=found.allowed_actions,
    )


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
    await _live(ctx)
    found = await eligibility(ctx, target_type, target_id, LEVEL_OF[level])
    return SignOffEligibilityOut(
        target=_target_out(found.facts),
        level=level,
        levels_allowed=[LEVEL_CODES[n] for n in found.levels_allowed],
        ladder=_ladder_out(found.ladder),
        checks=[
            EligibilityCheckOut(
                code=cast(CheckCode, c.code),
                result=c.result,
                facts=c.facts,
                refs=[ObjectRefOut(type=t, id=i) for t, i in c.refs],
            )
            for c in found.checks
        ],
        eligible=found.eligible,
        statement=SignOffStatementOut(version=found.statement.version, text=found.statement.text),
    )


@sign_offs_router.post(
    "",
    action="sign_off.create",
    response_model=SignOffOut,
    status_code=201,
    errors=(409, 501),
)
async def sign_off_route(body: SignOffIn, ctx: Ctx) -> SignOffOut:
    """SHL-12 a-prime: record one sign-off (human only; the service also authorises the level)."""
    await _live(ctx)
    return _sign_off_out(
        await sign_target(
            ctx,
            body.target_type,
            body.target_id,
            LEVEL_OF[body.level],
            body.seen_hash,
            body.statement_version,
            body.kind,
        )
    )


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


class ReviewNoteDetailOut(BaseModel):
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
    "/{note_id}", action="review_note.read", response_model=ReviewNoteDetailOut, errors=(501,)
)
async def review_note_route(note_id: UUID, ctx: Ctx) -> ReviewNoteDetailOut:
    """One note with its body and events."""
    await _stub(ctx)


@review_notes_router.post(
    "",
    action="review_note.raise",
    response_model=ReviewNoteDetailOut,
    status_code=201,
    errors=(501,),
)
async def review_note_raise_route(body: RaiseReviewNoteIn, ctx: Ctx) -> ReviewNoteDetailOut:
    """Raise a note on a registered reviewable, optionally on an anchor."""
    await _stub(ctx)


@review_notes_router.post(
    "/{note_id}/respond",
    action="review_note.respond",
    response_model=ReviewNoteDetailOut,
    errors=(409, 501),
)
async def review_note_respond_route(
    note_id: UUID, body: ReviewNoteEventIn, ctx: Ctx
) -> ReviewNoteDetailOut:
    await _stub(ctx)


@review_notes_router.post(
    "/{note_id}/clear",
    action="review_note.clear",
    response_model=ReviewNoteDetailOut,
    errors=(409, 501),
)
async def review_note_clear_route(
    note_id: UUID, body: ReviewNoteEventIn, ctx: Ctx
) -> ReviewNoteDetailOut:
    """Clearing is a person's act (the event's CHECK requires a human)."""
    await _stub(ctx)


@review_notes_router.post(
    "/{note_id}/withdraw",
    action="review_note.withdraw",
    response_model=ReviewNoteDetailOut,
    errors=(409, 501),
)
async def review_note_withdraw_route(
    note_id: UUID, body: ReviewNoteEventIn, ctx: Ctx
) -> ReviewNoteDetailOut:
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
    """What waits on the caller; `counts` are per kind ("3 decisions, 6 sign-offs, 2 exports").
    P-04-T16: served from the projection behind `review.grammar_api`; a walled client's gates
    are never listed or counted."""
    if not await flag_enabled(ctx.tenant, REVIEW_GRAMMAR_API):
        raise NotFound("review.grammar_api")
    found = await gates_waiting_on(
        ctx, kind=kind, engagement_id=engagement_id, cursor=cursor, limit=limit
    )
    return ListPage[HumanGateOut](
        items=[
            HumanGateOut(
                id=g.id,
                kind=cast(GateKind, g.kind),
                subject=ObjectRefOut(type=g.subject_type, id=g.subject_id),
                engagement_id=g.engagement_id,
                work_item_id=g.work_item_id,
                client_id=g.client_id,
                assignee_user_id=g.assignee_user_id,
                role=g.role,
                due_on=g.due_on,
                state=cast(GateState, g.state),
                created_at=g.created_at,
            )
            for g in found.items
        ],
        next_cursor=found.next_cursor,
        total=found.total,
        total_capped=found.total_capped,
        counts=found.counts,
    )


# --- Decision cards (SHL-11; ADR-160 clause 8) -------------------------------------------------

ReservedRole = Literal["engagement_partner", "manager", "eqr_reviewer", "signer"]
CardEvent = Literal["proposed", "decided", "reassessed"]
ActorKind = Literal["human", "agent", "system"]


class DecisionContextOut(BaseModel):
    """One context row ("Benchmark", "Amount", "Firm range", "Prior year"), from the owner."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("internal")]
    value: Annotated[str, classified("restricted")]
    citation_id: Annotated[UUID | None, classified("internal")]


class DecisionOptionOut(BaseModel):
    """An option computed by the kind's provider in code, never by a model (ADR-050). Money is
    a decimal string; `figures` are what the label and detail line show."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    detail: Annotated[str | None, classified("confidential")]
    figures: Annotated[dict[str, str], classified("restricted")]
    # The agent's recommendation is a suggestion and a tag, never the decider (SHL-11 f/g).
    recommended: Annotated[bool, classified("internal")]


class DecisionFactorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    applicable: Annotated[bool, classified("internal")]
    checked: Annotated[bool, classified("internal")]


class DecisionRecommendationOut(BaseModel):
    """The agent's recommendation (`decision_cards.recommendation_suggestion_id`). `reasons` are
    agent text: the web app renders them only through AgentText."""

    model_config = ConfigDict(frozen=True)

    suggestion_id: Annotated[UUID, classified("internal")]
    option_key: Annotated[str, classified("internal")]
    reasons: Annotated[list[str], classified("restricted")]


class CardDecisionOut(BaseModel):
    """The insert-only, human-only `decisions` row. The rationale is sealed."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    option_key: Annotated[str, classified("internal")]
    factors: Annotated[list[str], classified("internal")]
    rationale: Annotated[str, classified("restricted")]
    seen_card_version: Annotated[int, classified("internal")]
    decided_by_user_id: Annotated[UUID, classified("internal")]
    decided_by_name: Annotated[str, classified("internal")]
    decided_at: Annotated[datetime, classified("internal")]


class DecisionCardVersionOut(BaseModel):
    """One history row: v1 proposed, v2 decided, v3 reassessed with no change (SHL-11 d)."""

    model_config = ConfigDict(frozen=True)

    version_no: Annotated[int, classified("internal")]
    event: Annotated[CardEvent, classified("internal")]
    actor_kind: Annotated[ActorKind, classified("internal")]
    actor_user_id: Annotated[UUID | None, classified("internal")]
    actor_initials: Annotated[str | None, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    option_key: Annotated[str | None, classified("internal")]
    changed: Annotated[bool | None, classified("internal")]
    figures: Annotated[dict[str, str], classified("restricted")]


class DecisionCardItemOut(BaseModel):
    """A card in a list (HOME-02, the AUD-02 rail). No question text, options or rationale."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID | None, classified("internal")]
    kind: Annotated[str, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    status: Annotated[DecisionCardStatus, classified("internal")]
    reserved_role: Annotated[ReservedRole, classified("internal")]
    reserved_user_id: Annotated[UUID | None, classified("internal")]
    reserved_user_name: Annotated[str | None, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]
    blocking_count: Annotated[int, classified("internal")]
    superseded_by_version: Annotated[int | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class DecisionCardOut(BaseModel):
    """One card: the question, context, code-computed options, factors and, once decided, the
    decision. A viewer outside the reserved role gets the same card with no decide action."""

    model_config = ConfigDict(frozen=True)

    card: Annotated[DecisionCardItemOut, classified("internal")]
    question: Annotated[str, classified("confidential")]
    context: Annotated[list[DecisionContextOut], classified("confidential")]
    options: Annotated[list[DecisionOptionOut], classified("confidential")]
    factors: Annotated[list[DecisionFactorOut], classified("confidential")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    note: Annotated[str | None, classified("confidential")]
    recommendation: Annotated[DecisionRecommendationOut | None, classified("confidential")]
    blocking_refs: Annotated[list[ObjectRefOut], classified("internal")]
    decision: Annotated[CardDecisionOut | None, classified("restricted")]
    history: Annotated[list[DecisionCardVersionOut], classified("confidential")]


class CardDecideIn(BaseModel):
    """`POST /v1/decision-cards/{id}/decide`. No rationale answers 422 `rationale_required`; a
    stale `seen_version` answers 409 `recommendation_changed`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    option_key: Annotated[
        str, Field(pattern=r"^[a-z0-9][a-z0-9_.]{0,39}$"), classified("internal")
    ]
    factors: Annotated[list[str], Field(max_length=40), classified("internal")] = []
    # Optional on the wire so the service answers the fixed 422 `rationale_required`.
    rationale: Annotated[
        MultiLineText | None, Field(max_length=4000), classified("restricted")
    ] = None
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class AnalysisRequestIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[MultiLineText, Field(min_length=1, max_length=2000), classified("restricted")]


class AnalysisRequestOut(BaseModel):
    """A recorded request for the run that raised the card (P-10 delivers it)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    card_id: Annotated[UUID, classified("internal")]
    requested_by_user_id: Annotated[UUID, classified("internal")]
    requested_at: Annotated[datetime, classified("internal")]


class DecisionNotifyOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    card_id: Annotated[UUID, classified("internal")]
    notified_user_id: Annotated[UUID, classified("internal")]
    notified_at: Annotated[datetime, classified("internal")]


decision_cards_router = AbacusRouter(prefix="/v1/decision-cards", tags=["review"])


@decision_cards_router.get(
    "", action="decision.read", response_model=ListPage[DecisionCardItemOut], errors=(501,)
)
async def decision_card_list_route(
    ctx: Ctx,
    engagement_id: Annotated[UUID | None, Query()] = None,
    state: Annotated[DecisionCardStatus | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> ListPage[DecisionCardItemOut]:
    """Cards on an engagement, on the list envelope with per-status counts."""
    await _stub(ctx)


@decision_cards_router.get(
    "/{card_id}", action="decision.read", response_model=DecisionCardOut, errors=(501,)
)
async def decision_card_route(card_id: UUID, ctx: Ctx) -> DecisionCardOut:
    """SHL-11 a to h: one card, its versions and the caller's allowed actions."""
    await _stub(ctx)


@decision_cards_router.post(
    "/{card_id}/decide",
    action="decision.decide",
    response_model=DecisionCardOut,
    errors=(409, 501),
)
async def decision_card_decide_route(
    card_id: UUID, body: CardDecideIn, ctx: Ctx
) -> DecisionCardOut:
    """SHL-11 a to c: the reserved role decides, with a rationale (human only)."""
    await _stub(ctx)


@decision_cards_router.post(
    "/{card_id}/analysis-requests",
    action="decision.request_analysis",
    response_model=AnalysisRequestOut,
    status_code=201,
    errors=(501,),
)
async def decision_card_analysis_request_route(
    card_id: UUID, body: AnalysisRequestIn, ctx: Ctx
) -> AnalysisRequestOut:
    """SHL-11 b: "Request more analysis" records a request for the run."""
    await _stub(ctx)


@decision_cards_router.post(
    "/{card_id}/notify",
    action="decision.notify",
    response_model=DecisionNotifyOut,
    errors=(501,),
)
async def decision_card_notify_route(card_id: UUID, ctx: Ctx) -> DecisionNotifyOut:
    """SHL-11 b: "Notify Margaret" sends the reserved person a mention notification."""
    await _stub(ctx)


@decision_cards_router.post(
    "/{card_id}/reassess",
    action="decision.reassess",
    response_model=DecisionCardOut,
    errors=(409, 501),
)
async def decision_card_reassess_route(card_id: UUID, ctx: Ctx) -> DecisionCardOut:
    """SHL-11 d, h: the owner's provider recomputes in code; no change is a new version, a
    changed outcome raises a superseding card."""
    await _stub(ctx)


# === C3 stub PR 3 (P-04-T11): issues, checkpoints, field provenance ===========================
# An additive extension of the C3 v1 schema: new models and routes beside the old, none changed.

# --- Issues and fix instructions (SHL-15; ADR-160 clause 7) -----------------------------------

IssueKind = Literal[
    "missing_information",
    "action_required",
    "review_point",
    "waiting_on_client",
    "exception",
    "engine_diagnostic",
]
IssueBlock = Literal["final_approval", "export", "release", "sign_off"]
IssueLinkKind = Literal["cell_range", "form_field", "file", "request_item", "finding"]
IssueEvent = Literal[
    "created",
    "assigned",
    "status_changed",
    "fix_instructions_set",
    "sent_to_client",
    "explained",
    "resolved",
    "verified",
    "reopened",
    "marked_not_applicable",
]
FixScope = Literal["this_issue", "all_of_class"]
# Why one issue of a bulk instruction was left out (SHL-15 e).
FixExclusionCode = Literal["issue_changed", "fix_runner_unavailable", "level_not_permitted"]
SealedTitle = Annotated[MultiLineText, Field(min_length=1, max_length=400)]
SealedText = Annotated[MultiLineText, Field(min_length=1, max_length=4000)]


class CitedSourceOut(BaseModel):
    """A verified citation (C4) as its chip reads ("K-1 box 18A", "K-1 statement p. 3")."""

    model_config = ConfigDict(frozen=True)

    citation_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]


class IssueLinkOut(BaseModel):
    """A linked target: a cell range ("EBP-04 Participant data!F12:F15"), a form field ("Form
    1040 · line 2a"), a file, a request item or a finding. The chip lights its target."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[IssueLinkKind, classified("internal")]
    label: Annotated[str, classified("confidential")]
    target_type: Annotated[str | None, classified("internal")]
    target_id: Annotated[UUID | None, classified("internal")]
    anchor: Annotated[str | None, classified("confidential")]


class IssueLinkIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[IssueLinkKind, classified("internal")]
    target_type: Annotated[TargetType | None, classified("internal")] = None
    target_id: Annotated[UUID | None, classified("internal")] = None
    # A cell range or a field key on the target ("F12:F15", a form line code).
    anchor: Annotated[
        SingleLineText | None, Field(min_length=1, max_length=120), classified("confidential")
    ] = None


class IssueItemOut(BaseModel):
    """An issue in a list (TAX-06, TXP-10, AUD-15). The title, notes and client wording are
    sealed and Restricted, so lists never carry them; the detail does."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID | None, classified("internal")]
    work_item_id: Annotated[UUID | None, classified("internal")]
    record: Annotated[ObjectRefOut, classified("internal")]
    kind: Annotated[IssueKind, classified("internal")]
    priority: Annotated[IssueSeverityStatus, classified("internal")]
    status: Annotated[IssueStatus, classified("internal")]
    # The "Instructions required" sub-state of an open issue.
    instructions_required: Annotated[bool, classified("internal")]
    assignee_user_id: Annotated[UUID | None, classified("internal")]
    assignee_name: Annotated[str | None, classified("internal")]
    # "Assigned to · Accrued Agent": enables fix instructions; a person disables them.
    assignee_agent: Annotated[bool, classified("internal")]
    blocks: Annotated[list[IssueBlock], classified("internal")]
    link_count: Annotated[int, classified("internal")]
    version: Annotated[int, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class IssueClientContactOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    role_label: Annotated[str | None, classified("confidential")]


class IssueFixSuggestionOut(BaseModel):
    """ "Suggested by Accrued Agent": agent text, rendered only through AgentText."""

    model_config = ConfigDict(frozen=True)

    text: Annotated[str, classified("restricted")]
    agent_run_id: Annotated[UUID | None, classified("internal")]
    suggested_at: Annotated[datetime, classified("internal")]


class IssueFixInstructionsOut(BaseModel):
    """The sealed instructions a person set. Fix runs always propose (DF-13): there is no
    direct-edit mode, so the "Propose changes for my approval" box is not a wire field."""

    model_config = ConfigDict(frozen=True)

    text: Annotated[str, classified("restricted")]
    scope: Annotated[FixScope, classified("internal")]
    set_by_user_id: Annotated[UUID, classified("internal")]
    set_by_name: Annotated[str, classified("internal")]
    set_at: Annotated[datetime, classified("internal")]


class IssueFixRunOut(BaseModel):
    """The run fixing the issue (SHL-15 a-prime: "Adding 1,550 to Form 1040 line 2a · Running"),
    then its proposal (a-double-prime: the ghost values; Accept opens SHL-10 b). `label` is
    agent text."""

    model_config = ConfigDict(frozen=True)

    agent_run_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("restricted")]
    status: Annotated[AgentRunStatus, classified("internal")]
    proposal_id: Annotated[UUID | None, classified("internal")]


class IssueExplanationOut(BaseModel):
    """SHL-15 d, "Explain…": read-only agent text with its citations; it decides nothing."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    text: Annotated[str, classified("restricted")]
    agent_run_id: Annotated[UUID, classified("internal")]
    explained_at: Annotated[datetime, classified("internal")]
    citations: Annotated[list[CitedSourceOut], classified("confidential")]
    pinned: Annotated[bool, classified("internal")]


class IssueEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    event: Annotated[IssueEvent, classified("internal")]
    actor_kind: Annotated[ActorKind, classified("internal")]
    actor_user_id: Annotated[UUID | None, classified("internal")]
    actor_name: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]


class IssueDetailOut(BaseModel):
    """One issue with its sealed title, internal note and client wording. Only `client_wording`
    ever reaches the client, as a request item through `send-to-client` (INV-4)."""

    model_config = ConfigDict(frozen=True)

    issue: Annotated[IssueItemOut, classified("internal")]
    record_label: Annotated[str, classified("confidential")]
    title: Annotated[str, classified("restricted")]
    internal_note: Annotated[str | None, classified("restricted")]
    client_wording: Annotated[str | None, classified("restricted")]
    client_contact: Annotated[IssueClientContactOut | None, classified("confidential")]
    links: Annotated[list[IssueLinkOut], classified("confidential")]
    suggestion: Annotated[IssueFixSuggestionOut | None, classified("restricted")]
    fix_instructions: Annotated[IssueFixInstructionsOut | None, classified("restricted")]
    fix_run: Annotated[IssueFixRunOut | None, classified("restricted")]
    explanations: Annotated[list[IssueExplanationOut], classified("restricted")]
    request_item_id: Annotated[UUID | None, classified("internal")]
    events: Annotated[list[IssueEventOut], classified("internal")]


class IssueCreateIn(BaseModel):
    """`POST /v1/issues`. "Create & send to client" is this, then `send-to-client`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    record_type: Annotated[TargetType, classified("internal")]
    record_id: Annotated[UUID, classified("internal")]
    kind: Annotated[IssueKind, classified("internal")]
    priority: Annotated[IssueSeverityStatus, classified("internal")] = IssueSeverityStatus.MEDIUM
    title: Annotated[SealedTitle, classified("restricted")]
    internal_note: Annotated[SealedText | None, classified("restricted")] = None
    client_wording: Annotated[SealedText | None, classified("restricted")] = None
    client_contact_id: Annotated[UUID | None, classified("internal")] = None
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    assignee_agent: Annotated[bool, classified("internal")] = False
    links: Annotated[list[IssueLinkIn], Field(max_length=20), classified("confidential")] = []
    blocks: Annotated[list[IssueBlock], Field(max_length=4), classified("internal")] = []


class IssueUpdateIn(BaseModel):
    """`PATCH /v1/issues/{id}`: title, class, priority and assignee. A stale `seen_version`
    answers 409 `issue_changed`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    title: Annotated[SealedTitle | None, classified("restricted")] = None
    kind: Annotated[IssueKind | None, classified("internal")] = None
    priority: Annotated[IssueSeverityStatus | None, classified("internal")] = None
    assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    assignee_agent: Annotated[bool | None, classified("internal")] = None


class IssueResolutionIn(BaseModel):
    """Resolve, verify, reopen or mark not applicable: a person's act (ISSUE-001)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    note: Annotated[SealedText | None, classified("restricted")] = None


class IssueSendToClientIn(BaseModel):
    """One request item through `requests.api` (P-06) carrying only the client wording."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    client_wording: Annotated[SealedText, classified("restricted")]
    contact_id: Annotated[UUID, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None


class FixInstructionsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]
    text: Annotated[SealedText, classified("restricted")]
    scope: Annotated[FixScope, classified("internal")] = "this_issue"


class FixInstructionsAcceptedOut(BaseModel):
    """202: the instructions are recorded and the registered fix runner started a run."""

    model_config = ConfigDict(frozen=True)

    issue_id: Annotated[UUID, classified("internal")]
    agent_run_id: Annotated[UUID, classified("internal")]
    status: Annotated[IssueStatus, classified("internal")]


class BulkFixIssueIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    issue_id: Annotated[UUID, classified("internal")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class BulkFixInstructionsIn(BaseModel):
    """SHL-15 e: one shared editor; the scope is locked to the selection, so each issue gets
    its own sealed instruction with scope `this_issue`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    issues: Annotated[
        list[BulkFixIssueIn], Field(min_length=1, max_length=50), classified("internal")
    ]
    text: Annotated[SealedText, classified("restricted")]


class BulkFixItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    issue_id: Annotated[UUID, classified("internal")]
    ok: Annotated[bool, classified("internal")]
    agent_run_id: Annotated[UUID | None, classified("internal")]
    detail: Annotated[FixExclusionCode | None, classified("internal")]


class BulkFixInstructionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    results: Annotated[list[BulkFixItemOut], classified("internal")]
    accepted: Annotated[int, classified("internal")]
    excluded: Annotated[int, classified("internal")]


class ExplainAcceptedOut(BaseModel):
    """202: the explanation run started; its text arrives on the issue's detail."""

    model_config = ConfigDict(frozen=True)

    issue_id: Annotated[UUID, classified("internal")]
    agent_run_id: Annotated[UUID, classified("internal")]


issues_router = AbacusRouter(prefix="/v1/issues", tags=["review"])


@issues_router.get("", action="issue.read", response_model=ListPage[IssueItemOut], errors=(501,))
async def issue_list_route(
    ctx: Ctx,
    record_type: Annotated[str | None, Query(pattern=r"^[a-z][a-z_]{0,39}$")] = None,
    record_id: Annotated[UUID | None, Query()] = None,
    engagement_id: Annotated[UUID | None, Query()] = None,
    status: Annotated[IssueStatus | None, Query()] = None,
    kind: Annotated[IssueKind | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> ListPage[IssueItemOut]:
    """Issues on a record or an engagement; `counts` per status and `facets` by kind."""
    await _stub(ctx)


@issues_router.get(
    "/{issue_id}", action="issue.read", response_model=IssueDetailOut, errors=(501,)
)
async def issue_route(issue_id: UUID, ctx: Ctx) -> IssueDetailOut:
    """One issue with its sealed texts (each read is an access event)."""
    await _stub(ctx)


@issues_router.post(
    "", action="issue.create", response_model=IssueDetailOut, status_code=201, errors=(501,)
)
async def issue_create_route(body: IssueCreateIn, ctx: Ctx) -> IssueDetailOut:
    """SHL-15 b, c: a new issue, from cells or a field flag."""
    await _stub(ctx)


@issues_router.patch(
    "/{issue_id}", action="issue.update", response_model=IssueDetailOut, errors=(409, 501)
)
async def issue_update_route(issue_id: UUID, body: IssueUpdateIn, ctx: Ctx) -> IssueDetailOut:
    """Title, class, priority and assignee."""
    await _stub(ctx)


@issues_router.post(
    "/{issue_id}/resolve", action="issue.resolve", response_model=IssueDetailOut, errors=(409, 501)
)
async def issue_resolve_route(issue_id: UUID, body: IssueResolutionIn, ctx: Ctx) -> IssueDetailOut:
    """Human only; the agent never resolves its own issue (ISSUE-001)."""
    await _stub(ctx)


@issues_router.post(
    "/{issue_id}/verify", action="issue.verify", response_model=IssueDetailOut, errors=(409, 501)
)
async def issue_verify_route(issue_id: UUID, body: IssueResolutionIn, ctx: Ctx) -> IssueDetailOut:
    """A reviewer verifies a resolved issue."""
    await _stub(ctx)


@issues_router.post(
    "/{issue_id}/reopen", action="issue.reopen", response_model=IssueDetailOut, errors=(409, 501)
)
async def issue_reopen_route(issue_id: UUID, body: IssueResolutionIn, ctx: Ctx) -> IssueDetailOut:
    await _stub(ctx)


@issues_router.post(
    "/{issue_id}/mark-not-applicable",
    action="issue.resolve",
    response_model=IssueDetailOut,
    errors=(409, 501),
)
async def issue_not_applicable_route(
    issue_id: UUID, body: IssueResolutionIn, ctx: Ctx
) -> IssueDetailOut:
    """Not applicable is a resolution, so it shares `issue.resolve`."""
    await _stub(ctx)


@issues_router.post(
    "/{issue_id}/send-to-client",
    action="issue.send_to_client",
    response_model=IssueDetailOut,
    errors=(409, 501),
)
async def issue_send_to_client_route(
    issue_id: UUID,
    body: IssueSendToClientIn,
    ctx: Ctx,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
) -> IssueDetailOut:
    """SHL-15 b: one request item with only the client wording; G3 is checked (ADR-111)."""
    await _stub(ctx)


@issues_router.post(
    "/fix-instructions:bulk",
    action="fix_instruction.set",
    response_model=BulkFixInstructionsOut,
    status_code=202,
    errors=(409, 501),
)
async def fix_instructions_bulk_route(
    body: BulkFixInstructionsIn, ctx: Ctx
) -> BulkFixInstructionsOut:
    """SHL-15 e: one instruction per selected issue, each decided on its own."""
    await _stub(ctx)


@issues_router.post(
    "/{issue_id}/fix-instructions",
    action="fix_instruction.set",
    response_model=FixInstructionsAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def fix_instructions_route(
    issue_id: UUID, body: FixInstructionsIn, ctx: Ctx
) -> FixInstructionsAcceptedOut:
    """SHL-15 a: sealed instructions; 409 `fix_runner_unavailable` when no runner is registered."""
    await _stub(ctx)


@issues_router.post(
    "/{issue_id}/explanations",
    action="issue.explain",
    response_model=ExplainAcceptedOut,
    status_code=202,
    errors=(409, 501),
)
async def issue_explain_route(issue_id: UUID, ctx: Ctx) -> ExplainAcceptedOut:
    """SHL-15 d, "Explain…": a person asks the agent to explain; nothing is decided."""
    await _stub(ctx)


# --- Checkpoints (SHL-16; ADR-160 clause 9) ----------------------------------------------------

CheckpointAuthorKind = Literal["agent", "person", "import"]
CheckpointCause = Literal[
    "agent_run", "engine_import", "human_edit", "restore", "amendment", "manual_save"
]
CheckpointDecisionKind = Literal["approved", "rejected", "restored"]
CheckpointFilter = Literal["agent", "named", "all"]
CheckpointCompare = Literal["current", "previous"]
# The step rows' icons: ScanSearch, ListPlus, ListX, and the self-check and import steps.
CheckpointStepKind = Literal[
    "analyzed",
    "updated_worksheet",
    "created_worksheet",
    "skipped_worksheet",
    "self_check",
    "imported",
]


class CheckpointDecisionOut(BaseModel):
    """The insert-only, human-only `checkpoint_decisions` row (SHL-16 b, e)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    decision: Annotated[CheckpointDecisionKind, classified("internal")]
    reason: Annotated[str | None, classified("restricted")]
    decided_by_user_id: Annotated[UUID, classified("internal")]
    decided_by_name: Annotated[str, classified("internal")]
    decided_at: Annotated[datetime, classified("internal")]
    # Approving Checkpoint 6 here equals approving the SHL-10 proposal it came from.
    proposal_decision_id: Annotated[UUID | None, classified("internal")]


class CheckpointItemOut(BaseModel):
    """One checkpoint card. "Checkpoint {seq}" is its title unless it is named; `current` is
    derived (ADR-160 clause 9) and never stored. `summary` may carry return figures
    ("Corrected Halvard 1099-INT (2,190 → 2,310)"), so it is Restricted and appears only in
    one target's history read."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    seq: Annotated[int, classified("internal")]
    name: Annotated[str | None, classified("confidential")]
    starred: Annotated[bool, classified("internal")]
    author_kind: Annotated[CheckpointAuthorKind, classified("internal")]
    author_user_id: Annotated[UUID | None, classified("internal")]
    # "Accrued Agent", "Kevin Osei" or "Imported Return".
    author_name: Annotated[str, classified("internal")]
    cause: Annotated[CheckpointCause, classified("internal")]
    status: Annotated[CheckpointStatus, classified("internal")]
    current: Annotated[bool, classified("internal")]
    summary: Annotated[str | None, classified("restricted")]
    created_at: Annotated[datetime, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    proposal_id: Annotated[UUID | None, classified("internal")]
    restored_from_id: Annotated[UUID | None, classified("internal")]
    agent_run_id: Annotated[UUID | None, classified("internal")]
    decision: Annotated[CheckpointDecisionOut | None, classified("restricted")]
    allowed_actions: Annotated[list[str], classified("internal")]


class CheckpointHistoryOut(BaseModel):
    """`GET /v1/checkpoints`: one target's checkpoints, newest first, read like the sign-off
    ladder (one target, bounded) rather than as a cross-record list."""

    model_config = ConfigDict(frozen=True)

    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    filter: Annotated[CheckpointFilter, classified("internal")]
    items: Annotated[list[CheckpointItemOut], classified("restricted")]
    current_checkpoint_id: Annotated[UUID | None, classified("internal")]
    total: Annotated[int, classified("internal")]
    # An empty history (SHL-16 f) still offers `checkpoint.create` ("Save checkpoint…").
    allowed_actions: Annotated[list[str], classified("internal")]


class CheckpointStepOut(BaseModel):
    """One step of the run that made the checkpoint (C6 run steps, read through review)."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[CheckpointStepKind, classified("internal")]
    title: Annotated[str, classified("confidential")]
    detail: Annotated[str | None, classified("restricted")]
    at: Annotated[datetime, classified("internal")]


class CheckpointDiffRowOut(BaseModel):
    """One field's old and new value, computed by code (`checkpoint_diffs`). Values are strings
    and numbers are decimal strings; null is an empty cell ("—")."""

    model_config = ConfigDict(frozen=True)

    field_key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    old: Annotated[str | None, classified("restricted")]
    new: Annotated[str | None, classified("restricted")]
    cause: Annotated[str, classified("confidential")]
    citation_ids: Annotated[list[UUID], classified("internal")]


class CheckpointTotalOut(BaseModel):
    """The code-computed totals row ("Net change to total income · 0", a tie)."""

    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("confidential")]
    value: Annotated[str, classified("restricted")]
    ties: Annotated[bool, classified("internal")]


class CheckpointDetailOut(BaseModel):
    """`GET /v1/checkpoints/{id}?compare=`: the card, its steps and the diff against `compare`
    (the previous checkpoint, or current for an older one, SHL-16 c)."""

    model_config = ConfigDict(frozen=True)

    checkpoint: Annotated[CheckpointItemOut, classified("restricted")]
    compare: Annotated[CheckpointCompare, classified("internal")]
    compared_to_id: Annotated[UUID | None, classified("internal")]
    steps: Annotated[list[CheckpointStepOut], classified("restricted")]
    diff: Annotated[list[CheckpointDiffRowOut], classified("restricted")]
    totals: Annotated[list[CheckpointTotalOut], classified("restricted")]


class CheckpointCreateIn(BaseModel):
    """ "Save checkpoint…": a person's named checkpoint of the target as it is."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    target_type: Annotated[TargetType, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    name: Annotated[
        SingleLineText | None, Field(min_length=1, max_length=120), classified("confidential")
    ] = None


class CheckpointApproveIn(BaseModel):
    """A checkpoint that is no longer proposed, or whose hash differs, answers 409
    `checkpoint_changed`; nothing is written."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_hash: Annotated[ContentHash, classified("internal")]


class CheckpointRejectIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_hash: Annotated[ContentHash, classified("internal")]
    reason: Annotated[
        SingleLineText, Field(min_length=1, max_length=200), classified("restricted")
    ]


class CheckpointRestoreIn(BaseModel):
    """Restore creates a new checkpoint as a copy; nothing is deleted (SHL-16 c)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seen_hash: Annotated[ContentHash, classified("internal")]


class CheckpointRenameIn(BaseModel):
    """Rename and star change only `name` and `starred` (SHL-16 d)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    name: Annotated[
        SingleLineText | None, Field(min_length=1, max_length=120), classified("confidential")
    ] = None
    starred: Annotated[bool | None, classified("internal")] = None


checkpoints_router = AbacusRouter(prefix="/v1/checkpoints", tags=["review"])


@checkpoints_router.get(
    "", action="checkpoint.read", response_model=CheckpointHistoryOut, errors=(501,)
)
async def checkpoint_history_route(
    ctx: Ctx,
    target_type: Annotated[str, Query(pattern=r"^[a-z][a-z_]{0,39}$")],
    target_id: Annotated[UUID, Query()],
    filter: Annotated[CheckpointFilter, Query()] = "all",
) -> CheckpointHistoryOut:
    """SHL-16: the drawer's cards, filtered Agent only, Named only or All."""
    await _stub(ctx)


@checkpoints_router.get(
    "/{checkpoint_id}", action="checkpoint.read", response_model=CheckpointDetailOut, errors=(501,)
)
async def checkpoint_route(
    checkpoint_id: UUID,
    ctx: Ctx,
    compare: Annotated[CheckpointCompare, Query()] = "previous",
) -> CheckpointDetailOut:
    """SHL-16 a, c: steps and the code-computed diff."""
    await _stub(ctx)


@checkpoints_router.post(
    "",
    action="checkpoint.create",
    response_model=CheckpointItemOut,
    status_code=201,
    errors=(501,),
)
async def checkpoint_create_route(body: CheckpointCreateIn, ctx: Ctx) -> CheckpointItemOut:
    """SHL-16 f: "Save checkpoint…"."""
    await _stub(ctx)


@checkpoints_router.post(
    "/{checkpoint_id}/approve",
    action="checkpoint.approve",
    response_model=CheckpointItemOut,
    errors=(409, 501),
)
async def checkpoint_approve_route(
    checkpoint_id: UUID, body: CheckpointApproveIn, ctx: Ctx
) -> CheckpointItemOut:
    """SHL-16 b: human only; Current moves and `checkpoint.approved` carries the deltas."""
    await _stub(ctx)


@checkpoints_router.post(
    "/{checkpoint_id}/reject",
    action="checkpoint.reject",
    response_model=CheckpointItemOut,
    errors=(409, 501),
)
async def checkpoint_reject_route(
    checkpoint_id: UUID, body: CheckpointRejectIn, ctx: Ctx
) -> CheckpointItemOut:
    """SHL-16 e: "Reject…" with a reason (human only)."""
    await _stub(ctx)


@checkpoints_router.post(
    "/{checkpoint_id}/restore",
    action="checkpoint.restore",
    response_model=CheckpointItemOut,
    status_code=201,
    errors=(409, 501),
)
async def checkpoint_restore_route(
    checkpoint_id: UUID, body: CheckpointRestoreIn, ctx: Ctx
) -> CheckpointItemOut:
    """SHL-16 c: returns the new checkpoint (Checkpoint 7, a copy of Checkpoint 3); human only."""
    await _stub(ctx)


@checkpoints_router.patch(
    "/{checkpoint_id}",
    action="checkpoint.rename",
    response_model=CheckpointItemOut,
    errors=(501,),
)
async def checkpoint_rename_route(
    checkpoint_id: UUID, body: CheckpointRenameIn, ctx: Ctx
) -> CheckpointItemOut:
    """SHL-16 d: rename and star."""
    await _stub(ctx)


# --- Field provenance (SHL-09; ADR-160 clauses 5 and 10) --------------------------------------

FieldKey = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.!:-]{1,80}$")]
FieldTargetType = Annotated[str, Path(pattern=r"^[a-z][a-z_]{0,39}$")]
ValueType = Literal["decimal", "text", "date", "bool"]
ValueKind = Literal["exact", "estimate"]
# `policy` stays off the wire while `fvv_policy_dormant` holds (P-08).
ValueSource = Literal["agent_suggested", "human", "formula", "tb_linked", "engine_import"]
ValueCause = Literal[
    "edit", "suggestion_adopted", "recompute", "import", "restore", "template_update", "relink"
]
ReferenceKind = Literal["document", "engine_import", "workpaper", "prior_return"]


class FieldValueOut(BaseModel):
    """A typed value as `field_value_versions.value` stores it: `{t, v}`, decimals as strings."""

    model_config = ConfigDict(frozen=True)

    t: Annotated[ValueType, classified("internal")]
    v: Annotated[str | None, classified("restricted")]


class FieldValueIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    t: Annotated[ValueType, classified("internal")]
    v: Annotated[SingleLineText | None, Field(max_length=200), classified("restricted")]


class FieldReferenceOut(BaseModel):
    """A reference row: the imported return or the document page that proves the value."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[ReferenceKind, classified("internal")]
    label: Annotated[str, classified("confidential")]
    detail: Annotated[str | None, classified("restricted")]
    citation_id: Annotated[UUID | None, classified("internal")]
    document_id: Annotated[UUID | None, classified("internal")]
    page: Annotated[int | None, classified("internal")]


class FieldVersionOut(BaseModel):
    """One insert-only `field_value_versions` row. `unsupported` is computed: no verified
    citation, so the value cannot be ticked or approved. The pill (Updated, Edited, ≈,
    Unsupported) is derived from these fields and never stored."""

    model_config = ConfigDict(frozen=True)

    seq: Annotated[int, classified("internal")]
    value: Annotated[FieldValueOut, classified("restricted")]
    value_kind: Annotated[ValueKind, classified("internal")]
    value_source: Annotated[ValueSource, classified("internal")]
    cause: Annotated[ValueCause, classified("internal")]
    actor_kind: Annotated[ActorKind, classified("internal")]
    actor_user_id: Annotated[UUID | None, classified("internal")]
    # "Accrued Agent", "Kevin Osei" or "Imported Return"; "<person> via Agent" once adopted.
    actor_name: Annotated[str, classified("internal")]
    recorded_at: Annotated[datetime, classified("internal")]
    # The citation sentence (C4), or a person's required citation note on an edit.
    citation: Annotated[str | None, classified("restricted")]
    citation_ids: Annotated[list[UUID], classified("internal")]
    references: Annotated[list[FieldReferenceOut], classified("restricted")]
    unsupported: Annotated[bool, classified("internal")]
    suggestion_id: Annotated[UUID | None, classified("internal")]
    checkpoint_id: Annotated[UUID | None, classified("internal")]
    # An estimate links its open issue (SHL-09 b).
    issue_id: Annotated[UUID | None, classified("internal")]


class FieldTickOut(BaseModel):
    """A field tick: a `field_tick` sign-off bound to the value's hash. `stale` is computed
    ("✓ KO · Sep 8 (before this change)")."""

    model_config = ConfigDict(frozen=True)

    sign_off_id: Annotated[UUID, classified("internal")]
    level: Annotated[Level, classified("internal")]
    signer_user_id: Annotated[UUID, classified("internal")]
    signer_name: Annotated[str, classified("internal")]
    initials: Annotated[str, classified("internal")]
    signed_at: Annotated[datetime, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    stale: Annotated[bool, classified("internal")]


class FieldFlagOut(BaseModel):
    """A field flag ("⚑ SI · Sep 11"): a review note anchored on the field."""

    model_config = ConfigDict(frozen=True)

    note_id: Annotated[UUID, classified("internal")]
    raised_by_user_id: Annotated[UUID, classified("internal")]
    raised_by_initials: Annotated[str, classified("internal")]
    raised_at: Annotated[datetime, classified("internal")]
    body: Annotated[str, classified("restricted")]
    status: Annotated[ReviewNoteStatus, classified("internal")]


class FieldProvenanceOut(BaseModel):
    """`GET /v1/fields/{type}/{id}/{key}/provenance`: the tray behind ⓘ, newest version first.
    Every field write answers with it too."""

    model_config = ConfigDict(frozen=True)

    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]
    field_key: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    current_seq: Annotated[int, classified("internal")]
    content_hash: Annotated[str, classified("internal")]
    versions: Annotated[list[FieldVersionOut], classified("restricted")]
    ticks: Annotated[list[FieldTickOut], classified("internal")]
    flags: Annotated[list[FieldFlagOut], classified("restricted")]
    allowed_actions: Annotated[list[str], classified("internal")]


class FieldEditIn(BaseModel):
    """`PUT …/value`: a person's edit. The citation note is required (the `fvv_human_edits_cite`
    CHECK); a stale `seen_seq` answers 409 `field_changed`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    value: Annotated[FieldValueIn, classified("restricted")]
    value_kind: Annotated[ValueKind, classified("internal")] = "exact"
    citation_note: Annotated[SealedText, classified("restricted")]
    seen_seq: Annotated[int, Field(ge=1), classified("internal")]


class FieldReferenceIn(BaseModel):
    """`POST …/references`: a document in this return; C4 verifies the citation."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_id: Annotated[UUID, classified("internal")]
    page: Annotated[int | None, Field(ge=1), classified("internal")] = None
    seen_seq: Annotated[int, Field(ge=1), classified("internal")]


class FieldTickIn(BaseModel):
    """`POST …/ticks`: "Sign off field". An unsupported value answers 422 `uncited_change`; a
    different current hash answers 409 `content_changed`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    level: Annotated[Level, classified("internal")]
    seen_hash: Annotated[ContentHash, classified("internal")]


fields_router = AbacusRouter(prefix="/v1/fields", tags=["review"])
_FIELD = "/{target_type}/{target_id}/{field_key}"


@fields_router.get(
    _FIELD + "/provenance", action="field.read", response_model=FieldProvenanceOut, errors=(501,)
)
async def field_provenance_route(
    target_type: FieldTargetType, target_id: UUID, field_key: FieldKey, ctx: Ctx
) -> FieldProvenanceOut:
    """SHL-09 a to f: versions, prior values, citations, ticks and flags with staleness."""
    await _stub(ctx)


@fields_router.put(
    _FIELD + "/value", action="field.edit", response_model=FieldProvenanceOut, errors=(409, 501)
)
async def field_edit_route(
    target_type: FieldTargetType,
    target_id: UUID,
    field_key: FieldKey,
    body: FieldEditIn,
    ctx: Ctx,
) -> FieldProvenanceOut:
    """SHL-09 c: a person's edit with a citation note (a human checkpoint where the owner
    checkpoints, SHL-16)."""
    await _stub(ctx)


@fields_router.post(
    _FIELD + "/references",
    action="field.add_reference",
    response_model=FieldProvenanceOut,
    status_code=201,
    errors=(409, 501),
)
async def field_reference_route(
    target_type: FieldTargetType,
    target_id: UUID,
    field_key: FieldKey,
    body: FieldReferenceIn,
    ctx: Ctx,
) -> FieldProvenanceOut:
    """ "Add reference": a document in this return, verified through C4."""
    await _stub(ctx)


@fields_router.post(
    _FIELD + "/ticks",
    action="field.sign_off",
    response_model=FieldProvenanceOut,
    status_code=201,
    errors=(409, 501),
)
async def field_tick_route(
    target_type: FieldTargetType,
    target_id: UUID,
    field_key: FieldKey,
    body: FieldTickIn,
    ctx: Ctx,
) -> FieldProvenanceOut:
    """ "Sign off field": a `field_tick` sign-off (human only)."""
    await _stub(ctx)
