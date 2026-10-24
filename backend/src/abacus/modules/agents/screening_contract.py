"""C5 v1.2, the SHL-20 family stub: the evidence-screening card, its rerun, feedback and the
screening-return follow-up draft (P-06-T15; P-06 §4.3; contract `docs/contracts/c5-requests-
binders.md` §12). The follow-up's edit and send are the live follow-ups v2 routes (P-06-T14).

Behind `screening.card`: off, every route here answers 404 (the card area shows nothing extra).
On, the card, its rerun and feedback are live (P-06-T20, `screening_card`), and the
screening-return draft answers 501 `not_implemented` until P-06-T22. The card is composed by
code from the per-file screenings and verified reviewer flags (`screening_aggregate`). It never
carries a confidence (P-06 §7), and its flags carry only code-verified quotes, through C4
regions (INV-2). The agent screens; a person returns, sends and gives feedback (INV-1):
`screening.feedback` denies the agent.
"""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel._flags import SCREENING_CARD
from abacus.kernel._statuses import EvidenceScreeningStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.text import MultiLineText
from abacus.modules.agents.follow_up_routes import FollowUpOut
from abacus.modules.agents.screening_card import (
    CardView,
    FeedbackView,
    give_feedback,
    rerun_screening,
    screening_card,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
CheckKey = Literal["right_document", "right_period"]
CheckVerdict = Literal["pass", "flag", "not_run"]
CheckSource = Literal["model", "code"]
# The returned-file reasons F-03-T15 registered for a send-back.
ReturnReason = Literal["wrong_document", "wrong_year"]
FeedbackThumb = Literal["up", "down"]
FeedbackReason = Literal["wrong_request_match", "wrong_period", "unclear_file", "other"]

screening_items_router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/request-items/{item_id}", tags=["screening"]
)
screenings_router = AbacusRouter(prefix="/v1/screenings", tags=["screening"])


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, SCREENING_CARD):
        raise NotFound("screening.card")
    raise NotImplementedYet


class ScreeningCheckOut(BaseModel):
    """One named check: "Right document", "Right period". Code checks and verified model flags
    only (ADR-050)."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[CheckKey, classified("internal")]
    verdict: Annotated[CheckVerdict, classified("internal")]
    source: Annotated[CheckSource, classified("internal")]
    answer_ref: Annotated[str | None, classified("internal")]  # the request it answers
    citation_ids: Annotated[list[UUID], classified("internal")]


class ScreeningFileFlagOut(BaseModel):
    """A flagged file with the deciding region one click away ("View" opens SHL-08 on it)."""

    model_config = ConfigDict(frozen=True)

    evidence_version_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    reason_code: Annotated[ReturnReason, classified("internal")]
    region_ref: Annotated[str | None, classified("internal")]  # a C4 region


class ScreeningProvenanceOut(BaseModel):
    """ "Screened by Accrued Agent · screener@v3 · 2 s · instructions inside files are never
    followed": the parts as data; the UI words them."""

    model_config = ConfigDict(frozen=True)

    prompt_ref: Annotated[str | None, classified("internal")]
    duration_ms: Annotated[int | None, classified("internal")]
    screened_at: Annotated[datetime | None, classified("internal")]


class ScreeningFeedbackOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    screening_result_id: Annotated[UUID, classified("internal")]
    thumb: Annotated[FeedbackThumb, classified("internal")]
    reason_code: Annotated[FeedbackReason | None, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]


class ScreeningCardOut(BaseModel):
    """SHL-20 a-e: the request batch's screening ("29 of 31 files answer the request"). `verdict`
    is C2's `evidence_screening` glyph; a verdict never carries a percentage (P-06 §7)."""

    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    screening_result_id: Annotated[UUID | None, classified("internal")]  # None: not screened
    batch_no: Annotated[int | None, classified("internal")]
    verdict: Annotated[EvidenceScreeningStatus, classified("internal")]
    running: Annotated[bool, classified("internal")]  # c: "Screening 2 new files…"
    files_total: Annotated[int, classified("internal")]
    files_answering: Annotated[int, classified("internal")]
    checks: Annotated[list[ScreeningCheckOut], classified("internal")]
    file_flags: Annotated[list[ScreeningFileFlagOut], classified("confidential")]
    provenance: Annotated[ScreeningProvenanceOut, classified("internal")]
    my_feedback: Annotated[ScreeningFeedbackOut | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class ScreeningRerunOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    running: Annotated[bool, classified("internal")]
    as_of: Annotated[datetime, classified("internal")]


class ScreeningFeedbackIn(BaseModel):
    """SHL-20 f: a thumbs-down needs a reason (422 otherwise)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    thumb: Annotated[FeedbackThumb, classified("internal")]
    reason_code: Annotated[FeedbackReason | None, classified("internal")] = None
    note: Annotated[MultiLineText | None, Field(max_length=500), classified("confidential")] = None

    @model_validator(mode="after")
    def _down_needs_a_reason(self) -> ScreeningFeedbackIn:
        if self.thumb == "down" and self.reason_code is None:
            raise ValueError("reason_required")
        return self


class ScreeningReturnDraftIn(BaseModel):
    """SHL-20 b: "Draft follow-up" on a flagged card, naming the files it returns."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[Literal["screening_return"], classified("internal")]
    returning: Annotated[list[UUID], Field(min_length=1, max_length=50), classified("internal")]
    reason_code: Annotated[ReturnReason, classified("internal")] = "wrong_document"


def _feedback_out(view: FeedbackView) -> ScreeningFeedbackOut:
    return ScreeningFeedbackOut.model_validate(asdict(view))


def _card_out(view: CardView) -> ScreeningCardOut:
    """Validated as data: the codes are the table's CHECK values, composed by code."""
    provenance = ("prompt_ref", "duration_ms", "screened_at")
    found = asdict(view)
    return ScreeningCardOut.model_validate(
        {k: v for k, v in found.items() if k not in provenance}
        | {"provenance": {k: found[k] for k in provenance}}
    )


@screening_items_router.get(
    "/screening", action="upload_review.read", response_model=ScreeningCardOut
)
async def screening_card_route(engagement_id: UUID, item_id: UUID, ctx: Ctx) -> ScreeningCardOut:
    """SHL-20 a-e: the request batch's screening, composed by code. 404 with `screening.card`
    off."""
    return _card_out(await screening_card(ctx, engagement_id, item_id))


@screening_items_router.post(
    "/screening/rerun",
    action="screening.request",
    response_model=ScreeningRerunOut,
    status_code=202,
    errors=(409,),
)
async def rerun_screening_route(engagement_id: UUID, item_id: UUID, ctx: Ctx) -> ScreeningRerunOut:
    """Re-screen the current files (SHL-20 c); 409 `screening_running` while one runs."""
    view = await rerun_screening(ctx, engagement_id, item_id)
    return ScreeningRerunOut(
        request_item_id=view.request_item_id, running=view.running, as_of=view.as_of
    )


@screenings_router.post(
    "/{screening_result_id}/feedback",
    action="screening.feedback",
    response_model=ScreeningFeedbackOut,
    status_code=201,
)
async def screening_feedback_route(
    screening_result_id: UUID, body: ScreeningFeedbackIn, ctx: Ctx
) -> ScreeningFeedbackOut:
    """SHL-20 f: a person's thumbs up or down on a card, insert-only."""
    view = await give_feedback(ctx, screening_result_id, body.thumb, body.reason_code, body.note)
    return _feedback_out(view)


@screening_items_router.post(
    "/follow-ups",
    action="follow_up.draft",
    response_model=FollowUpOut,
    status_code=201,
    errors=(409, 501),
)
async def draft_screening_return_route(
    engagement_id: UUID, item_id: UUID, body: ScreeningReturnDraftIn, ctx: Ctx
) -> FollowUpOut:
    """SHL-20 b: a template-composed draft from the firm's Return template, with the files it
    returns. Its edit and send are `PATCH /v1/follow-ups/{id}` and `POST …/send` (P-06-T14);
    for this kind, send also returns the files and posts the shared comment (P-06-T22)."""
    await _stub(ctx)
