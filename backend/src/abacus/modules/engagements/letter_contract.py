"""C7 v1 letter half: the ENG-04 engagement-letter composer, the stubs (N-02-T03; N-02 §3.11,
§4.3; SPEC-381 AC-13..AC-15). Contract: `docs/contracts/c7-envelopes.md` §2.

The composer lives under `/letter/composer` because `PUT /v1/engagements/{id}/letter` is the kept
record path (`letter.record`, `routes.py`). Every route answers 404 with `signatures.envelopes`
off (until `engagements.letter_composer` exists, N-02-T32) and 501 with it on. The agent may
draft (`letter.draft`); approval is the partner's against the content hash with a fresh second
factor, and sending creates a C7 draft from the `engagement_letter` source. §7216 consents are
separate documents, never clauses (AC-15). No model drafts letter text (DEC-79 off).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import SIGNATURES_ENVELOPES
from abacus.kernel._statuses import LetterStatus
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
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=64)]
ClauseState = Literal["on", "off", "required"]


async def _stub(ctx: AuthContext, action: str) -> NoReturn:
    """Client principals: 404; then the action, then the flag, then 501."""
    if ctx.client:
        raise NotFound("letter")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, SIGNATURES_ENVELOPES):
        raise NotFound(SIGNATURES_ENVELOPES.name)
    raise NotImplementedYet


class LetterClause(BaseModel):
    """One clause of the template version and its state."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    title: Annotated[str, classified("internal")]
    state: Annotated[ClauseState, classified("internal")]


class LetterVariable(BaseModel):
    """A typed variable from facts; a person may override it with plain text."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    value: Annotated[str | None, classified("confidential")]
    source: Annotated[Literal["facts", "override"], classified("internal")]


class LetterOut(BaseModel):
    """`GET /v1/engagements/{id}/letter/composer`: the ENG-04 projection."""

    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    mode: Annotated[Literal["composed", "recorded"], classified("internal")]
    status: Annotated[LetterStatus, classified("internal")]
    version_no: Annotated[int | None, classified("internal")]
    template_version_id: Annotated[UUID | None, classified("internal")]
    clauses: Annotated[list[LetterClause], classified("internal")]
    variables: Annotated[list[LetterVariable], classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]
    approval_content_hash: Annotated[str | None, classified("internal")]
    envelope_id: Annotated[UUID | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]
    version: Annotated[int, classified("internal")]


class LetterDraftIn(BaseModel):
    """`PUT …/letter/composer` (If-Match): draft edits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    template_version_id: Annotated[UUID, classified("internal")]
    clause_states: Annotated[dict[str, ClauseState], classified("internal")]
    variables: Annotated[dict[str, str], classified("confidential")]
    section_overrides: Annotated[
        dict[str, Annotated[str, Field(max_length=4000)]], classified("confidential")
    ] = {}


class LetterCompareOut(BaseModel):
    """C11 compare against the standard or an earlier version."""

    model_config = ConfigDict(frozen=True)

    against: Annotated[str, classified("internal")]
    changed_clauses: Annotated[list[str], classified("internal")]
    changed_sections: Annotated[list[str], classified("internal")]


class LetterSendOut(BaseModel):
    """The C7 draft the send created, for SIG-02."""

    model_config = ConfigDict(frozen=True)

    envelope_id: Annotated[UUID, classified("internal")]


letter_router = AbacusRouter(prefix="/v1/engagements", tags=["engagements"])


@letter_router.get(
    "/{engagement_id}/letter/composer",
    action="letter.read",
    response_model=LetterOut,
    errors=(501,),
)
async def get_letter_route(engagement_id: UUID, ctx: Ctx) -> LetterOut:
    """ENG-04 (N-02-T33)."""
    await _stub(ctx, "letter.read")


@letter_router.put(
    "/{engagement_id}/letter/composer",
    action="letter.draft",
    response_model=LetterOut,
    errors=(409, 501),
)
async def draft_letter_route(
    engagement_id: UUID, body: LetterDraftIn, ctx: Ctx, if_match: IfMatch
) -> LetterOut:
    """Draft edits; an edit after approval stales it (N-02-T33)."""
    await _stub(ctx, "letter.draft")


@letter_router.get(
    "/{engagement_id}/letter/compare",
    action="letter.read",
    response_model=LetterCompareOut,
    errors=(501,),
)
async def compare_letter_route(
    engagement_id: UUID, ctx: Ctx, to: str = "standard"
) -> LetterCompareOut:
    """C11 compare (N-02-T34)."""
    await _stub(ctx, "letter.read")


@letter_router.get(
    "/{engagement_id}/letter/pdf", action="letter.read", response_model=bytes, errors=(501,)
)
async def letter_pdf_route(engagement_id: UUID, ctx: Ctx) -> Response:
    """The generated document (N-02-T34)."""
    await _stub(ctx, "letter.read")


@letter_router.post(
    "/{engagement_id}/letter/request-approval",
    action="letter.draft",
    response_model=LetterOut,
    errors=(409, 501),
)
async def request_approval_route(engagement_id: UUID, ctx: Ctx) -> LetterOut:
    """C13 `letter_partner_approval` (N-02-T35)."""
    await _stub(ctx, "letter.draft")


@letter_router.post(
    "/{engagement_id}/letter/approve",
    action="letter.approve",
    response_model=LetterOut,
    errors=(409, 501),
)
async def approve_letter_route(engagement_id: UUID, ctx: Ctx, if_match: IfMatch) -> LetterOut:
    """Partner, fresh MFA, against the content hash (N-02-T35)."""
    await _stub(ctx, "letter.approve")


@letter_router.post(
    "/{engagement_id}/letter/send",
    action="letter.send",
    response_model=LetterSendOut,
    errors=(409, 501),
)
async def send_letter_route(engagement_id: UUID, ctx: Ctx) -> LetterSendOut:
    """A C7 draft from the `engagement_letter` source (N-02-T35)."""
    await _stub(ctx, "letter.send")


@letter_router.post(
    "/{engagement_id}/letter/amend",
    action="letter.amend",
    response_model=LetterOut,
    status_code=201,
    errors=(409, 501),
)
async def amend_letter_route(engagement_id: UUID, ctx: Ctx) -> LetterOut:
    """An addendum version (N-02-T37)."""
    await _stub(ctx, "letter.amend")
