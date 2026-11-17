"""The confirmations contract stub (A-08-T06; SPEC-657 AC-0.6, F6, F7; DEC-5031).
Contract: `docs/contracts/confirmations.md`; screens AUD-14 (firm) and POR-17 (public).

**Firm routes** (`/v1/work-items/{work_item_id}/confirmations…`, `/v1/confirmations/{id}…`): one
matrix action each, answering in order: a client principal 404 (I-CONFIRMATION-ISOLATION); the
action on the work item's engagement (walls 404, independence 403); 404 with
`audits.confirmations` off; then 501 `not_implemented` until A-08-T16 and T18.

**The public family** (`/v1/confirm/{token}…`, the ADR-152 amendment, under the `LINK_PRINCIPAL`
marker): no session; the path token names one link principal. Until the link authenticator
(A-08-T15) the stub serves POR-17's synthetic fixtures (`confirmations_fixtures`) in local and test
environments only, and every other token, environment or state answers the one uniform `expired`
view (DV-7), padded to the same floor so status, body and timing reveal nothing. Nothing is
written; the token is never logged.
"""

from __future__ import annotations

import asyncio
import time
from decimal import Decimal
from typing import Annotated, Final, Literal, cast
from uuid import UUID

from fastapi import Cookie, Depends, Header, Path, Query, Request, Response
from pydantic import BaseModel, ConfigDict

from abacus.kernel._flags import AUDITS_CONFIRMATIONS
from abacus.kernel.classification import classified
from abacus.kernel.config import settings
from abacus.kernel.errors import DomainConflict, NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.logging import get_logger
from abacus.kernel.safe_xlsx import XLSX
from abacus.modules.assurance import confirmations_fixtures as fx
from abacus.modules.assurance.confirmations_contract_models import (
    AcceptedOut,
    AddressVerificationIn,
    AddressVerificationOut,
    AlternativeProcedureIn,
    AttachmentOut,
    AuthorizationIn,
    CodeRequestIn,
    CodeVerifyIn,
    ConfirmationAuthorizationOut,
    ConfirmationCreateIn,
    ConfirmationDetailOut,
    ConfirmationLogOut,
    ConfirmationSummaryOut,
    ExceptionPrefillOut,
    ReconciliationIn,
    RecordedResponseIn,
    RespondentReceiptOut,
    RespondentResponseIn,
    RespondentViewOut,
    SeenHashIn,
    VerifiedOut,
)
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import (
    LINK_COOKIE_NAME,
    LINK_PRINCIPAL,
    AbacusRouter,
    AuthContext,
    authorise,
    current_context,
    request_link_code,
    resolve_link,
    verify_link_code,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
# The path token: never in a query string, never logged (uvicorn's access log is off and spans
# carry only the route template, `kernel.telemetry`).
Token = Annotated[str, Path(min_length=16, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")]
# Every public answer takes at least this long from receipt (the amendment's padded floor).
CONFIRM_PAD_SECONDS: Final = 0.4
LINK_PURPOSE: Final = "confirmation"
_FIXTURE_ENVIRONMENTS: Final = frozenset({"local", "test"})


class AddressNotVerified(DomainConflict):
    """Send refused: no address verification cites a non-client source (AC-6.1)."""

    code = "address_not_verified"


class AuthorizationMissing(DomainConflict):
    """Send refused: the client's authorization envelope is not on file (AC-6.3)."""

    code = "authorization_missing"


class AlreadyAnswered(DomainConflict):
    """A replayed response: the link was consumed (AC-7.5)."""

    code = "already_answered"


class ConfirmationIdOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]


router = AbacusRouter(prefix="/v1", tags=["confirmations"])
_WI = "/work-items/{work_item_id}/confirmations"
_C = "/confirmations/{confirmation_id}"
_log = get_logger(__name__)
_T = "/confirm/{token}"


# --- firm routes ---------------------------------------------------------------------------------


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str) -> None:
    """Client 404; the action on the work item's engagement; the flag."""
    if ctx.client:
        raise NotFound("confirmation")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, AUDITS_CONFIRMATIONS):
        raise NotFound(AUDITS_CONFIRMATIONS.name)


async def _gate_record(ctx: AuthContext) -> None:
    """A confirmation's own path: client 404 and the flag; the service (A-08-T16) resolves the
    confirmation's work item and authorises the action there."""
    if ctx.client:
        raise NotFound("confirmation")
    if not await flag_enabled(ctx.tenant, AUDITS_CONFIRMATIONS):
        raise NotFound(AUDITS_CONFIRMATIONS.name)


def _todo(task: str) -> NotImplementedYet:
    return NotImplementedYet(task)


@router.get(_WI, action="confirmation.read", response_model=ConfirmationLogOut, errors=(501,))
async def list_confirmations(work_item_id: UUID, ctx: Ctx) -> ConfirmationLogOut:
    """AUD-14's log (filters type, respondent, status, channel, q) with `allowed_actions`."""
    await _gate(ctx, work_item_id, "confirmation.read")
    from abacus.modules.assurance import (
        confirmations_service as cs,
    )

    return await cs.confirmation_list(ctx, work_item_id)


@router.get(
    f"{_WI}/summary",
    action="confirmation.read",
    response_model=ConfirmationSummaryOut,
    errors=(501,),
)
async def confirmation_summary(work_item_id: UUID, ctx: Ctx) -> ConfirmationSummaryOut:
    """Tiles (sum to the log) and the coverage line, both code's."""
    await _gate(ctx, work_item_id, "confirmation.read")
    from abacus.modules.assurance import (
        confirmations_service as cs,
    )

    return await cs.summary(ctx, work_item_id)


@router.post(
    _WI,
    action="confirmation.create",
    response_model=ConfirmationIdOut,
    status_code=201,
    errors=(501,),
)
async def create_confirmation(
    work_item_id: UUID, body: ConfirmationCreateIn, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    """A Draft, positive form only, with lines from the TB and an optional sample item."""
    await _gate(ctx, work_item_id, "confirmation.create")
    from abacus.modules.assurance import (
        confirmations_service as cs,
    )

    return ConfirmationIdOut(id=(await cs.create(ctx, work_item_id, body)).id)


@router.post(
    f"{_WI}/authorization",
    action="confirmation.request_authorization",
    response_model=ConfirmationAuthorizationOut,
    status_code=201,
    errors=(409, 501),
)
async def confirmation_request_authorization(
    work_item_id: UUID, body: AuthorizationIn, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationAuthorizationOut:
    """One C7 envelope (purpose `confirmation_authorization`) for the confirmations named."""
    await _gate(ctx, work_item_id, "confirmation.request_authorization")
    from abacus.modules.assurance import confirmations_authorization as ca

    envelope_id = await ca.request(
        ctx,
        work_item_id,
        body.confirmation_ids,
        body.signer_contact_id,
        body.letter_evidence_version_id,
    )
    return ConfirmationAuthorizationOut(
        envelope_id=envelope_id, confirmation_ids=sorted(set(body.confirmation_ids), key=str)
    )


@router.get(
    f"{_WI}/export.xlsx", action="confirmation.export", response_model=bytes, errors=(501,)
)
async def export_confirmations(work_item_id: UUID, ctx: Ctx) -> Response:
    """The control log workbook (deterministic, text cells guarded, ADR-042)."""
    await _gate(ctx, work_item_id, "confirmation.export")
    _ = XLSX
    from abacus.modules.assurance import (
        confirmations_service as cs,
    )

    return Response(content=await cs.workbook_of(ctx, work_item_id), media_type=XLSX)


@router.get(_C, action="confirmation.read", response_model=ConfirmationDetailOut, errors=(501,))
async def get_confirmation(confirmation_id: UUID, ctx: Ctx) -> ConfirmationDetailOut:
    """The drawer: Response, Reconciliation, Classification and Why this was surfaced."""
    await _gate_record(ctx)
    from abacus.modules.assurance import (
        confirmations_service as cs,
    )

    return await cs.detail(ctx, confirmation_id)


@router.post(
    f"{_C}/address-verifications",
    action="confirmation.verify_address",
    response_model=AddressVerificationOut,
    status_code=201,
    errors=(501,),
)
async def verify_address(
    confirmation_id: UUID, body: AddressVerificationIn, ctx: Ctx, _key: IdempotencyKey
) -> AddressVerificationOut:
    """Method, sources and citations; insert-only; independent with a non-client source."""
    await _gate_record(ctx)
    from abacus.modules.assurance import (
        confirmations_service as cs,
    )

    return await cs.verify_address(ctx, confirmation_id, body)


async def _send_like(confirmation_id: UUID, ctx: AuthContext) -> ConfirmationIdOut:
    from abacus.modules.assurance import (
        confirmations_service as cs,
    )

    await _gate_record(ctx)
    await cs.check_sendable(ctx, confirmation_id)  # A-08-T16: 409 address_not_verified first
    from abacus.modules.assurance import confirmations_lifecycle as life

    return ConfirmationIdOut(id=await life.send(ctx, confirmation_id))


@router.post(
    f"{_C}/send", action="confirmation.send", response_model=ConfirmationIdOut, errors=(409, 501)
)
async def send_confirmation(
    confirmation_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    """Issues the link and the template email, or records a network send. A person's only; 409
    `address_not_verified`, `authorization_missing`."""
    return await _send_like(confirmation_id, ctx)


@router.post(
    f"{_C}/second-request",
    action="confirmation.send",
    response_model=ConfirmationIdOut,
    errors=(409, 501),
)
async def second_request(
    confirmation_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    """The second request (once, while unanswered)."""
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    return ConfirmationIdOut(id=await life.second_request(ctx, confirmation_id))


@router.post(
    f"{_C}/revoke-link",
    action="confirmation.send",
    response_model=ConfirmationIdOut,
    errors=(409, 501),
)
async def revoke_link(confirmation_id: UUID, ctx: Ctx, _key: IdempotencyKey) -> ConfirmationIdOut:
    """A-08-T18 (DEC-5324): end the sent confirmation's link; the status stays Sent."""
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    return ConfirmationIdOut(id=await life.revoke(ctx, confirmation_id))


@router.post(
    f"{_C}/record-response",
    action="confirmation.record_response",
    response_model=ConfirmationIdOut,
    errors=(409, 501),
)
async def record_response(
    confirmation_id: UUID, body: RecordedResponseIn, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    """A recorded channel's response (DV-6): uploaded evidence and amounts."""
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    done = await life.record_response(
        ctx,
        confirmation_id,
        agrees=body.agrees,
        confirmed_amounts=body.confirmed_amounts,
        evidence_version_ids=body.evidence_version_ids,
    )
    return ConfirmationIdOut(id=done)


@router.post(
    f"{_C}/reconciliation",
    action="confirmation.reconcile",
    response_model=ConfirmationIdOut,
    errors=(409, 501),
)
async def reconcile(
    confirmation_id: UUID, body: ReconciliationIn, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    """Reconciling items; code computes unreconciled."""
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    await life.reconcile(
        ctx,
        confirmation_id,
        [(i.description, i.amount, list(i.citation_ids)) for i in body.items],
    )
    return ConfirmationIdOut(id=confirmation_id)


@router.post(
    f"{_C}/accept-reconciliation",
    action="confirmation.accept_reconciliation",
    response_model=ConfirmationIdOut,
    errors=(409, 501),
)
async def accept_reconciliation(
    confirmation_id: UUID, body: SeenHashIn, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    """A manager or EP who did not enter the reconciliation (403 otherwise; 409 on change)."""
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    done = await life.accept_reconciliation(ctx, confirmation_id, body.seen_hash)
    return ConfirmationIdOut(id=done)


@router.post(
    f"{_C}/alternative-procedures",
    action="confirmation.record_alternative",
    response_model=ConfirmationIdOut,
    errors=(409, 501),
)
async def record_alternative(
    confirmation_id: UUID, body: AlternativeProcedureIn, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    done = await life.record_alternative(
        ctx, confirmation_id, body.description, list(body.citation_ids)
    )
    return ConfirmationIdOut(id=done)


@router.post(
    f"{_C}/exception",
    action="finding.create",
    response_model=ExceptionPrefillOut,
    errors=(409, 501),
)
async def confirmation_exception_prefill(confirmation_id: UUID, ctx: Ctx) -> ExceptionPrefillOut:
    """SHL-15's prefill; Below CT routes to `record_misstatement` (A-08-T18, DEC-5324)."""
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    found = await life.exception_prefill(ctx, confirmation_id)
    return ExceptionPrefillOut(
        confirmation_id=confirmation_id,
        difference=cast(Decimal, found["difference"]),
        below_clearly_trivial=bool(found["below_clearly_trivial"]),
        route=cast(Literal["finding", "misstatement"], found["route"]),
    )


@router.post(
    f"{_C}/close", action="confirmation.close", response_model=ConfirmationIdOut, errors=(409, 501)
)
async def close_confirmation(
    confirmation_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> ConfirmationIdOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import confirmations_lifecycle as life

    return ConfirmationIdOut(id=await life.close(ctx, confirmation_id))


@router.get(
    f"{_C}/respondent-preview",
    action="confirmation.read",
    response_model=RespondentViewOut,
    errors=(501,),
)
async def respondent_preview(confirmation_id: UUID, ctx: Ctx) -> RespondentViewOut:
    """The firm's preview of POR-17's render data for this confirmation."""
    await _gate_record(ctx)
    raise _todo("A-08-T19")  # POR-17's render data lands with the respondent service


# --- the public family ---------------------------------------------------------------------------


def _fixture_mode() -> bool:
    return settings().environment in _FIXTURE_ENVIRONMENTS


async def _pad(started: float) -> None:
    """Hold every public answer to the same floor (no timing oracle)."""
    left = CONFIRM_PAD_SECONDS - (time.monotonic() - started)
    if left > 0:
        await asyncio.sleep(left)


def _fixture_view(token: str) -> RespondentViewOut:
    found = fx.view(token) if _fixture_mode() else None
    return found or fx.EXPIRED


async def _resolved_view(token: str) -> RespondentViewOut:
    """A fixture link (local, test) or a live link principal's view; anything else, the one
    uniform expired view (A-08-T15: unknown, expired, revoked and locked are the same)."""
    if _fixture_mode() and fx.view(token) is not None:
        return _fixture_view(token)
    found = await resolve_link(token)
    if found is None or found.purpose != LINK_PURPOSE:
        # A-08-T38 (DEC-5404): the expired-view burst alarm counts these (no token, no address).
        _log.info("confirm.expired_view")
        return fx.EXPIRED
    from abacus.modules.assurance import (
        confirmations_service,
    )

    return await confirmations_service.respondent_view_of(found)


@router.get(_T, action=LINK_PRINCIPAL, response_model=RespondentViewOut)
async def respondent_view(token: Token) -> RespondentViewOut:
    """`confirmation.respond_view` (link_scope_only): open, answered or the uniform expired."""
    started = time.monotonic()
    view = await _resolved_view(token)
    await _pad(started)
    return view


@router.post(f"{_T}/code", action=LINK_PRINCIPAL, response_model=AcceptedOut, status_code=202)
async def request_code(token: Token, body: CodeRequestIn) -> AcceptedOut:
    """`confirmation.respond_verify`: 202 after the padded floor for any token and any address.
    A-08-T15: a live link whose address is the typed one gets a 10-minute code by email."""
    started = time.monotonic()
    if not _fixture_mode() or fx.view(token) is None:
        await request_link_code(token, body.email)
    await _pad(started)
    return AcceptedOut()


@router.post(f"{_T}/code/verify", action=LINK_PRINCIPAL, response_model=VerifiedOut)
async def verify_code(token: Token, body: CodeVerifyIn, response: Response) -> VerifiedOut:
    """`confirmation.respond_verify` (A-08-T15): a right code sets the `__Host-` page credential
    and returns its CSRF value in a header; five wrong codes lock the link for 15 minutes. Every
    failure is `false` after the same floor. Fixture links (local, test) keep the fixture code."""
    started = time.monotonic()
    if _fixture_mode() and fx.view(token) is not None:
        view = _fixture_view(token)
        ok = view.state == "open" and body.code == fx.FIXTURE_CODE
        await _pad(started)
        return VerifiedOut(verified=ok)
    verified = await verify_link_code(token, body.code)
    if verified is None:
        # A-08-T38 (DEC-5404): the OTP failure spike alarm counts these (no token, no code).
        _log.info("confirm.code_failed")
    if verified is not None:
        response.set_cookie(
            LINK_COOKIE_NAME,
            verified.credential,
            max_age=30 * 60,
            secure=True,
            httponly=True,
            samesite="strict",
            path="/",
        )
        response.headers["X-Abacus-CSRF"] = verified.csrf
    await _pad(started)
    return VerifiedOut(verified=verified is not None)


@router.post(
    f"{_T}/attachments",
    action=LINK_PRINCIPAL,
    response_model=AttachmentOut,
    status_code=201,
    errors=(413, 415),
)
async def upload_attachment(
    token: Token,
    request: Request,
    filename: Annotated[str, Query(min_length=1, max_length=255)],
    credential: Annotated[str | None, Cookie(alias=LINK_COOKIE_NAME)] = None,
    csrf: Annotated[str | None, Header(alias="X-Abacus-CSRF")] = None,
) -> AttachmentOut:
    """`confirmation.respond` (email verified): scanned, write-once evidence with channel
    `confirmation_response` (A-08-T19, DEC-5325); the raw body is the file, refused past the
    upload limit before it is all read. Any other link answers 404 after the floor."""
    started = time.monotonic()
    from abacus.modules.assurance import confirmations_respondent as respondent
    from abacus.modules.evidence.api import MAX_UPLOAD_BYTES, UploadTooLarge
    from abacus.modules.identity.api import credential_principal

    principal = await credential_principal(credential, csrf)
    linked = await resolve_link(token) if principal is not None else None
    if (
        principal is None
        or principal.purpose != LINK_PURPOSE
        or linked is None
        or linked.principal_id != principal.principal_id
    ):
        await _pad(started)
        raise NotFound("confirmation")
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_UPLOAD_BYTES:
            raise UploadTooLarge
    version, size = await respondent.attach(principal, filename, bytes(data))
    await _pad(started)
    return AttachmentOut(attachment_id=version, file_name=filename[:255], size_bytes=size)


def _receipt(view: RespondentViewOut, body: RespondentResponseIn) -> RespondentReceiptOut:
    """The server's difference (ADR-050): per client minus per respondent; agreeing is zero."""
    request = view.request
    if request is None:  # pragma: no cover - an open view always carries its request
        raise NotFound("confirmation")
    per_client = request.balance_per_client or Decimal("0.00")
    given = per_client if body.agrees or not body.balances else body.balances[0].amount
    return RespondentReceiptOut(
        receipt_id=f"{request.reference}-R1",
        reference=request.reference,
        agrees=body.agrees,
        respondent_balance=given,
        difference=(per_client - given).quantize(Decimal("0.01")),
        submitted_at=fx.RECEIPT.submitted_at,
        verified_email=fx.RECEIPT.verified_email,
    )


@router.post(
    f"{_T}/response",
    action=LINK_PRINCIPAL,
    response_model=RespondentReceiptOut,
    status_code=201,
    errors=(409, 501),
)
async def submit_response(
    token: Token,
    body: RespondentResponseIn,
    request: Request,
    credential: Annotated[str | None, Cookie(alias=LINK_COOKIE_NAME)] = None,
    csrf: Annotated[str | None, Header(alias="X-Abacus-CSRF")] = None,
) -> RespondentReceiptOut:
    """`confirmation.respond` (email verified): the one answer; 409 `already_answered` on a
    replay. The stub computes the fixture receipt and writes nothing; any other token answers
    404 after the floor (the expired page)."""
    started = time.monotonic()
    if _fixture_mode() and fx.view(token) is not None:
        view = _fixture_view(token)
        await _pad(started)
        if view.state == "answered":
            raise AlreadyAnswered()
        if view.state != "open":
            raise NotFound("confirmation")
        return _receipt(view, body)
    # A-08-T19: a live link principal whose page credential (cookie and CSRF header) proves it.
    from abacus.modules.assurance import confirmations_respondent as respondent
    from abacus.modules.identity.api import credential_principal

    principal = await credential_principal(credential, csrf)
    # S47 end-pass security review: the page's link and its credential name one principal; a
    # credential from another confirmation's page never answers through this link.
    linked = await resolve_link(token) if principal is not None else None
    if (
        principal is None
        or principal.purpose != LINK_PURPOSE
        or linked is None
        or linked.principal_id != principal.principal_id
    ):
        await _pad(started)
        raise NotFound("confirmation")
    try:
        receipt = await respondent.submit(
            principal,
            agrees=body.agrees,
            balance=body.balances[0].amount if body.balances else None,
            respondent_name=body.respondent_name,
            explanation=body.explanation,
            attachment_ids=list(body.attachment_ids),
            accounts=[(a.description, a.account_last4, a.balance) for a in body.accounts],
            ip=None if request.client is None else request.client.host,
            user_agent=request.headers.get("user-agent"),
        )
    except respondent.AlreadyAnswered as answered:
        await _pad(started)
        raise AlreadyAnswered(facts=answered.facts) from None
    await _pad(started)
    return RespondentReceiptOut(
        receipt_id=receipt.receipt_id,
        reference=receipt.reference,
        agrees=receipt.agrees,
        respondent_balance=receipt.respondent_balance,
        difference=receipt.difference,
        submitted_at=receipt.submitted_at,
        verified_email="",
    )
