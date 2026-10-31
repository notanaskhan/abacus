"""C7 v1 letter half: the ENG-04 engagement-letter composer, the stubs (N-02-T03; N-02 §3.11,
§4.3; SPEC-381 AC-13..AC-15). Contract: `docs/contracts/c7-envelopes.md` §2.

The composer lives under `/letter/composer` because `PUT /v1/engagements/{id}/letter` is the kept
record path (`letter.record`, `routes.py`). Every route answers 404 with `signatures.envelopes`
off and 501 with it on, except the composer's GET and PUT (N-02-T32, `letters.py`) and
request-approval, approve, send and amend (N-02-T33, `letter_flow.py`), which
`engagements.letter_composer` turns on (send also needs `signatures.envelopes`). The agent may
draft (`letter.draft`); approval is the partner's against the content hash with a fresh second
factor, and sending creates a C7 draft from the `engagement_letter` source. §7216 consents are
separate documents, never clauses (AC-15). No model drafts letter text (DEC-79 off).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import ENGAGEMENTS_LETTER_COMPOSER, SIGNATURES_ENVELOPES
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
    # N-02-T32: the template marks it non-standard, or its state differs from the default.
    non_standard: Annotated[bool, classified("internal")] = False


class LetterVariable(BaseModel):
    """A typed variable from facts; a person may override it with plain text. Fee and billing
    values are computed by code and never overridden (`source` "computed")."""

    model_config = ConfigDict(frozen=True)

    key: Annotated[str, classified("internal")]
    value: Annotated[str | None, classified("confidential")]
    source: Annotated[Literal["facts", "override", "computed"], classified("internal")]
    # Why a variable reads "—" (`cas_only`, `attest_only`, `ebp_only`, `not_designated`).
    reason: Annotated[str | None, classified("internal")] = None
    # N-02-T34: the template's label for a key it declares; facts keys are labelled by ENG-04.
    label: Annotated[str | None, classified("internal")] = None


class LetterSignerOut(BaseModel):
    """N-02-T34: who signs, in order: the client signer, then the firm's countersignature."""

    model_config = ConfigDict(frozen=True)

    order: Annotated[int, classified("internal")]
    name: Annotated[str, classified("confidential")]
    role: Annotated[Literal["client", "firm"], classified("internal")]
    identity: Annotated[Literal["email_code"], classified("internal")] = "email_code"
    signed: Annotated[bool, classified("internal")] = False


class LetterheadOut(BaseModel):
    """N-02-T34: the firm's name and address lines over the paper (no colour, T10)."""

    model_config = ConfigDict(frozen=True)

    firm: Annotated[str, classified("internal")]
    address: Annotated[list[str], classified("internal")] = []


class LetterConsentOut(BaseModel):
    """N-02-T34: a §7216 consent beside the letter: always its own document, never a clause
    (Rev. Proc. 2013-14 §5.05; AC-15). Filled from T-01's consent sets with N-02-T33."""

    model_config = ConfigDict(frozen=True)

    purpose: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    status: Annotated[Literal["on_file", "needed"], classified("internal")]
    signed_on: Annotated[date | None, classified("internal")] = None
    expires_on: Annotated[date | None, classified("internal")] = None


Cents = Annotated[int, Field(ge=0, le=100_000_000_00)]
FeeLabel = Annotated[str, Field(min_length=1, max_length=200)]


class FeeLineIn(BaseModel):
    """One part of the fee (`$6,500 for the section 754 work`)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Annotated[FeeLabel, classified("confidential")]
    amount_cents: Annotated[Cents, classified("confidential")]


class InstallmentIn(BaseModel):
    """One billing installment as a share of the fee, in basis points (5000 is 50%)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    label: Annotated[FeeLabel, classified("confidential")]
    share_bp: Annotated[int, Field(ge=1, le=10_000), classified("confidential")]


class ThirdPartyFeeIn(BaseModel):
    """A fee another party bills directly (the engineer's): shown, never added to the total."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    payee: Annotated[FeeLabel, classified("confidential")]
    estimated_cents: Annotated[Cents, classified("confidential")]


class LetterFeesIn(BaseModel):
    """The fee terms a person sets in Draft; every total is computed by code (ADR-050)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    basis: Annotated[Literal["fixed", "estimate"], classified("internal")] = "fixed"
    lines: Annotated[
        list[FeeLineIn], Field(min_length=1, max_length=20), classified("confidential")
    ]
    installments: Annotated[
        list[InstallmentIn], Field(max_length=12), classified("confidential")
    ] = []
    third_party: Annotated[
        list[ThirdPartyFeeIn], Field(max_length=5), classified("confidential")
    ] = []


class InstallmentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    label: Annotated[str, classified("confidential")]
    share_bp: Annotated[int, classified("confidential")]
    amount_cents: Annotated[int, classified("confidential")]


class ThirdPartyFeeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    payee: Annotated[str, classified("confidential")]
    estimated_cents: Annotated[int, classified("confidential")]
    included_in_total: Annotated[Literal[False], classified("internal")] = False


class LetterFeesOut(BaseModel):
    """The computed fee: the lines, their total, each installment's amount (the last carries the
    rounding remainder) and the third-party fees shown beside it, not added."""

    model_config = ConfigDict(frozen=True)

    basis: Annotated[Literal["fixed", "estimate"], classified("internal")]
    lines: Annotated[list[FeeLineIn], classified("confidential")]
    total_cents: Annotated[int, classified("confidential")]
    installments: Annotated[list[InstallmentOut], classified("confidential")]
    third_party: Annotated[list[ThirdPartyFeeOut], classified("confidential")]


class ComposerLetterOut(BaseModel):
    """`GET /v1/engagements/{id}/letter/composer`: the ENG-04 projection."""

    model_config = ConfigDict(frozen=True)

    engagement_id: Annotated[UUID, classified("internal")]
    mode: Annotated[Literal["composed", "recorded"], classified("internal")]
    status: Annotated[LetterStatus, classified("internal")]
    version_no: Annotated[int | None, classified("internal")]
    template_version_id: Annotated[UUID | None, classified("internal")]
    clauses: Annotated[list[LetterClause], classified("internal")]
    variables: Annotated[list[LetterVariable], classified("internal")]
    fees: Annotated[LetterFeesOut | None, classified("confidential")] = None
    redline_count: Annotated[int, classified("internal")] = 0
    generated_document_id: Annotated[UUID | None, classified("internal")] = None
    # N-02-T34: the template named in the structure pane and the paper's blocks (the template
    # version's body; variable runs resolve against `variables`), the signers and the consents.
    template_name: Annotated[str | None, classified("internal")] = None
    template_version_no: Annotated[int | None, classified("internal")] = None
    # The clause library the template's clauses come from ("BH clauses 2026.1"); None until P-11
    # names libraries apart from template versions.
    clause_library: Annotated[str | None, classified("internal")] = None
    letterhead: Annotated[LetterheadOut | None, classified("internal")] = None
    # C11's DocBlocks as JSON (ENG-04 reads them as the generated client's C11 block types):
    # `engagements` may not import `reporting`'s models (ADR-008).
    paper: Annotated[list[dict[str, object]], classified("confidential")] = []
    signers: Annotated[list[LetterSignerOut], classified("confidential")] = []
    consents: Annotated[list[LetterConsentOut], classified("confidential")] = []
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
    variables: Annotated[
        dict[str, Annotated[str, Field(min_length=1, max_length=500)]], classified("confidential")
    ]
    section_overrides: Annotated[
        dict[str, Annotated[str, Field(max_length=4000)]], classified("confidential")
    ] = {}
    fees: Annotated[LetterFeesIn, classified("confidential")]


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
    response_model=ComposerLetterOut,
    errors=(501,),
)
async def get_letter_route(engagement_id: UUID, ctx: Ctx) -> ComposerLetterOut:
    """ENG-04's composed letter (N-02-T32) behind `engagements.letter_composer`."""
    if not ctx.client and await flag_enabled(ctx.tenant, ENGAGEMENTS_LETTER_COMPOSER):
        from abacus.modules.engagements.letters import composed_letter

        return await composed_letter(ctx, engagement_id)
    await _stub(ctx, "letter.read")


@letter_router.put(
    "/{engagement_id}/letter/composer",
    action="letter.draft",
    response_model=ComposerLetterOut,
    errors=(409, 501),
)
async def draft_letter_route(
    engagement_id: UUID, body: LetterDraftIn, ctx: Ctx, if_match: IfMatch
) -> ComposerLetterOut:
    """Draft edits: a new version, rendered as a C11 draft (N-02-T32); an edit after approval
    returns the letter to Draft (N-02-T33 resolves the approval)."""
    if not ctx.client and await flag_enabled(ctx.tenant, ENGAGEMENTS_LETTER_COMPOSER):
        from abacus.modules.engagements.letters import draft_letter

        return await draft_letter(ctx, engagement_id, body, if_match)
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
    response_model=ComposerLetterOut,
    errors=(409, 501),
)
async def request_approval_route(
    engagement_id: UUID, ctx: Ctx, if_match: IfMatch
) -> ComposerLetterOut:
    """C13 `letter_partner_approval`: the draft waits on the engagement partners (N-02-T33)."""
    if not ctx.client and await flag_enabled(ctx.tenant, ENGAGEMENTS_LETTER_COMPOSER):
        from abacus.modules.engagements.letter_flow import request_approval

        return await request_approval(ctx, engagement_id, if_match)
    await _stub(ctx, "letter.draft")


@letter_router.post(
    "/{engagement_id}/letter/approve",
    action="letter.approve",
    response_model=ComposerLetterOut,
    errors=(409, 501),
)
async def approve_letter_route(
    engagement_id: UUID, ctx: Ctx, if_match: IfMatch
) -> ComposerLetterOut:
    """Partner, fresh MFA, against the content hash (N-02-T33)."""
    if not ctx.client and await flag_enabled(ctx.tenant, ENGAGEMENTS_LETTER_COMPOSER):
        from abacus.modules.engagements.letter_flow import approve_letter

        return await approve_letter(ctx, engagement_id, if_match)
    await _stub(ctx, "letter.approve")


@letter_router.post(
    "/{engagement_id}/letter/send",
    action="letter.send",
    response_model=LetterSendOut,
    errors=(409, 501),
)
async def send_letter_route(engagement_id: UUID, ctx: Ctx) -> LetterSendOut:
    """A C7 draft from the `engagement_letter` source (N-02-T33), with `signatures.envelopes`."""
    if (
        not ctx.client
        and await flag_enabled(ctx.tenant, ENGAGEMENTS_LETTER_COMPOSER)
        and await flag_enabled(ctx.tenant, SIGNATURES_ENVELOPES)
    ):
        from abacus.modules.engagements.letter_flow import send_letter

        return LetterSendOut(envelope_id=await send_letter(ctx, engagement_id))
    await _stub(ctx, "letter.send")


@letter_router.post(
    "/{engagement_id}/letter/amend",
    action="letter.amend",
    response_model=ComposerLetterOut,
    status_code=201,
    errors=(409, 501),
)
async def amend_letter_route(engagement_id: UUID, ctx: Ctx) -> ComposerLetterOut:
    """An addendum version amending the signed letter (N-02-T33)."""
    if not ctx.client and await flag_enabled(ctx.tenant, ENGAGEMENTS_LETTER_COMPOSER):
        from abacus.modules.engagements.letter_flow import amend_letter

        return await amend_letter(ctx, engagement_id)
    await _stub(ctx, "letter.amend")
