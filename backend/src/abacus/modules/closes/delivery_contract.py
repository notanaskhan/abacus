"""Closes-delivery stub (C-02-T07; SPEC-701; `docs/contracts/closes-delivery.md`). Screen
families CLS-08 (FS package, release, client approval, lock), CLS-12 (Handoff to tax) and CLS-13
(1099 / W-9 tracker).

Every route answers, in order: a client principal 404 (the client approves the package through
R-02's C18 applier, not here); its flag off 404 (`closes.delivery`, `closes.tax_handoff`,
`closes.information_returns`); a human-only route refuses an agent, the platform or a support
session 403 (INV-1); then 501 until its build task (C-02-T21/T23/T29 package, T39 hand-off,
T33/T45/T46 information returns). There is deliberately no transmit route (R-04, IRIS-001).

Classification (ADR-031): statements, vendor names and commentary are `confidential`; a TIN is
never in a payload, only its last four, `restricted` (ADR-167); ids, states and counts are
`internal`. Money is `Decimal` (ADR-050). Seed examples are Copperleaf's August 2026 package and
its 2026 vendors.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, cast
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field
from pydantic.config import JsonDict

from abacus.kernel._flags import CLOSES_DELIVERY, CLOSES_INFORMATION_RETURNS, CLOSES_TAX_HANDOFF
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Forbidden,
    current_context,
    mask_tins_for,
)
from abacus.modules.organisations.api import TinRevealOut

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")  # a TIN (ADR-167): never logged
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Confidential]

DeliverableStatus = Literal["drafting", "draft", "released", "approved_by_client"]
Route = Literal["ar_c_70_preparation", "cas_by_product", "standalone_letter"]
Section = Literal[
    "balance_sheet", "income_statement", "cash_flows", "reconciliation_summary", "commentary"
]
Blocker = Literal["accounts_unreconciled", "issues_open", "entries_unposted"]
HandoffStatus = Literal["not_available", "ready", "handed_off", "superseded"]
W9Status = Literal["on_file", "requested", "tin_mismatch", "missing"]
EntityType = Literal[
    "individual", "single_member_llc", "partnership", "c_corporation", "s_corporation",
    "trust_estate", "llc_c", "llc_s", "llc_p", "other", "unknown",
]  # fmt: skip
Form = Literal["nec", "misc"]
Reportability = Literal["reportable", "below_threshold", "exempt_corporation", "paid_by_card"]
BatchStatus = Literal["not_started", "approved", "exported", "filed_iris", "accepted", "rejected"]
MatchResult = Literal["match", "mismatch", "not_issued", "invalid"]
BackupEvent = Literal["watch_started", "b_notice_received", "started", "stopped"]


def _cfg(example: dict[str, object] | None = None) -> ConfigDict:
    if example is None:
        return ConfigDict(frozen=True, extra="forbid")
    extra = cast(JsonDict, {"examples": [example]})
    return ConfigDict(frozen=True, extra="forbid", json_schema_extra=extra)


# --- CLS-08 package ----------------------------------------------------------------------------


class DeliveryPreconditionOut(BaseModel):
    """CLS-08c: "9 of 21 accounts reconciled" · "7 open issues" · "Entries not posted"."""

    model_config = _cfg({"blocker": "accounts_unreconciled", "done": 9, "of": 21})

    blocker: Annotated[Blocker, Internal]
    done: Annotated[int | None, Field(ge=0), Internal] = None
    of: Annotated[int | None, Field(ge=0), Internal] = None


class DeliveryStatementLineOut(BaseModel):
    model_config = _cfg()

    key: Annotated[str, Field(max_length=80), Internal]
    label: Annotated[str, Field(max_length=200), Confidential]
    amount: Money
    account_refs: Annotated[list[str], Internal] = []
    # C-02-T23: the income statement's prior month (CLS-08a "August vs July 2026").
    prior: Annotated[Decimal | None, Field(max_digits=20, decimal_places=2), Confidential] = None


class DeliveryPackageOut(BaseModel):
    """CLS-08a: total assets 549,195.45 = 184,983.05 + 364,212.40; net income 27,795 (July
    31,455); route AR-C 70 preparation with "No assurance is provided." on every page."""

    model_config = _cfg(
        {"close_id": "00000000-0000-4000-8000-000000000c08", "status": "draft",
         "version_no": 2, "route": "ar_c_70_preparation",
         "legend": "No assurance is provided.", "sections": ["balance_sheet",
         "income_statement", "commentary"], "cas_answer": True, "preconditions": [],
         "content_hash": "0" * 64, "version": 2}
    )  # fmt: skip

    close_id: Annotated[UUID, Internal]
    status: Annotated[DeliverableStatus, Internal]
    version_no: Annotated[int, Field(ge=1), Internal]
    route: Annotated[Route, Internal]
    legend: Annotated[str | None, Field(max_length=200), Internal] = None
    sections: Annotated[list[Section], Internal]
    cas_answer: Annotated[bool, Internal]
    balance_sheet: Annotated[list[DeliveryStatementLineOut], Internal] = []
    income_statement: Annotated[list[DeliveryStatementLineOut], Internal] = []
    commentary: Annotated[str | None, Field(max_length=20000), Confidential] = None
    preconditions: Annotated[list[DeliveryPreconditionOut], Internal]
    released_at: Annotated[datetime | None, Internal] = None
    released_by: Annotated[str | None, Field(max_length=200), Confidential] = None
    client_approved_at: Annotated[datetime | None, Internal] = None
    client_approved_by: Annotated[str | None, Field(max_length=200), Confidential] = None
    content_hash: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]
    version: Annotated[int, Field(ge=1), Internal]


class DeliveryPackageEditIn(BaseModel):
    model_config = _cfg()

    sections: Annotated[list[Section], Field(min_length=1), Internal]
    cas_answer: Annotated[bool, Internal]
    expected_version: Annotated[int, Field(ge=1), Internal]


class DeliveryCommentaryIn(BaseModel):
    model_config = _cfg()

    doc: Annotated[str, Field(max_length=20000), Confidential]
    expected_version: Annotated[int, Field(ge=1), Internal]


class DeliveryGenerateOut(BaseModel):
    model_config = _cfg()

    run_id: Annotated[UUID, Internal]
    version_no: Annotated[int, Field(ge=1), Internal]


class DeliveryPageOut(BaseModel):
    model_config = _cfg()

    page_no: Annotated[int, Field(ge=1), Internal]
    of: Annotated[int, Field(ge=1), Internal]
    image_url: Annotated[str, Field(max_length=2000), Internal]


class DeliveryReleaseIn(BaseModel):
    model_config = _cfg()

    seen_version: Annotated[int, Field(ge=1), Internal]


class DeliveryReopenIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[str, Field(min_length=1, max_length=1000), Confidential]


class DeliveryCloseStateOut(BaseModel):
    model_config = _cfg()

    close_id: Annotated[UUID, Internal]
    status: Annotated[Literal["in_review", "approved", "delivered", "locked"], Internal]
    version: Annotated[int, Field(ge=1), Internal]


# --- CLS-12 hand-off ---------------------------------------------------------------------------


class DeliveryScheduleOut(BaseModel):
    """Fixed asset register: cost 278,400.00 · accumulated depreciation 74,900.00 · 2026 book
    depreciation 25,680.00."""

    model_config = _cfg()

    key: Annotated[str, Field(max_length=60), Internal]
    label: Annotated[str, Field(max_length=200), Internal]
    included: Annotated[bool, Internal]
    figures: Annotated[dict[str, Decimal], Confidential] = {}


class DeliveryHandoffOut(BaseModel):
    model_config = _cfg()

    status: Annotated[HandoffStatus, Internal]
    reason: Annotated[str | None, Field(max_length=200), Internal] = None
    tb_version: Annotated[str | None, Field(pattern=r"^TB v[1-9][0-9]*$"), Internal] = None
    locked_at: Annotated[date | None, Internal] = None
    target_return_id: Annotated[UUID | None, Internal] = None
    schedules: Annotated[list[DeliveryScheduleOut], Internal] = []
    superseded_on_next: Annotated[bool, Internal] = False
    version: Annotated[int, Field(ge=1), Internal] = 1


class DeliveryHandoffIn(BaseModel):
    model_config = _cfg()

    schedules: Annotated[list[str], Field(max_length=20), Internal]
    items: Annotated[list[UUID], Field(max_length=50), Internal] = []
    seen_version: Annotated[int, Field(ge=1), Internal]


class DeliveryHandoffPublishedOut(BaseModel):
    """ "Handed off to 2026 Form 1120-S · 3 tax issues created"."""

    model_config = _cfg()

    handoff_id: Annotated[UUID, Internal]
    tb_version: Annotated[str, Internal]
    tax_issues_created: Annotated[int, Field(ge=0), Internal]


# --- CLS-13 information returns ----------------------------------------------------------------


class DeliveryVendorRowOut(BaseModel):
    """Larimer Street Properties · 1099-MISC box 1 rents · $78,400.00 · TIN ••-•••4471."""

    model_config = _cfg()

    vendor_id: Annotated[UUID, Internal]
    display_name: Annotated[str, Field(max_length=200), Confidential]
    entity_type: Annotated[EntityType, Internal]
    is_attorney: Annotated[bool, Internal]
    reportability: Annotated[Reportability, Internal]
    form: Annotated[Form | None, Internal] = None
    box: Annotated[str | None, Field(max_length=4), Internal] = None
    amount: Money
    tin_last4: Annotated[
        str | None, Field(pattern=r"^[0-9]{4}$"), classified("restricted", pii_kind="tin")
    ] = None
    w9_status: Annotated[W9Status, Internal]
    version: Annotated[int, Field(ge=1), Internal]


class DeliveryInformationReturnsOut(BaseModel):
    """CLS-13a: 12 Vendors paid · 6 Reportable · 2 Requested · 1 TIN mismatch · 0 Filed."""

    model_config = _cfg()

    tax_year: Annotated[int, Field(ge=2020, le=2100), Internal]
    vendors_paid: Annotated[int, Field(ge=0), Internal]
    reportable: Annotated[int, Field(ge=0), Internal]
    requested: Annotated[int, Field(ge=0), Internal]
    w9_mismatches: Annotated[int, Field(ge=0), Internal]  # W-9s whose TIN did not match
    filed: Annotated[int, Field(ge=0), Internal]
    threshold_rule: Annotated[str, Field(max_length=500), Internal]
    due_rule: Annotated[str, Field(max_length=500), Internal]
    items: Annotated[list[DeliveryVendorRowOut], Internal]
    batch_status: Annotated[BatchStatus, Internal]


class DeliveryVendorPatchIn(BaseModel):
    model_config = _cfg()

    entity_type: Annotated[EntityType | None, Internal] = None
    is_attorney: Annotated[bool | None, Internal] = None
    exempt_reason: Annotated[str | None, Field(max_length=200), Internal] = None
    expected_version: Annotated[int, Field(ge=1), Internal]


class DeliveryRevealIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class DeliveryW9RequestIn(BaseModel):
    model_config = _cfg()

    vendor_ids: Annotated[list[UUID], Field(min_length=1, max_length=100), Internal]
    channel: Annotated[Literal["portal"], Internal] = "portal"
    wording_template_version_id: Annotated[UUID, Internal]


class DeliveryW9RequestOut(BaseModel):
    model_config = _cfg()

    request_id: Annotated[UUID, Internal]
    request_item_ids: Annotated[list[UUID], Internal]


class DeliveryTinMatchIn(BaseModel):
    model_config = _cfg()

    checked_on: Annotated[date, Internal]
    result: Annotated[MatchResult, Internal]
    evidence_version_id: Annotated[UUID, Internal]


class DeliveryBackupWithholdingIn(BaseModel):
    model_config = _cfg()

    event: Annotated[BackupEvent, Internal]
    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]
    evidence_version_id: Annotated[UUID | None, Internal] = None


class DeliveryRecordOut(BaseModel):
    model_config = _cfg()

    record_id: Annotated[UUID, Internal]


class DeliveryReturnBatchIn(BaseModel):
    model_config = _cfg()

    client_entity_id: Annotated[UUID, Internal]
    tax_year: Annotated[int, Field(ge=2020, le=2100), Internal]
    seen_versions: Annotated[dict[UUID, int], Internal]


class DeliveryReturnBatchOut(BaseModel):
    model_config = _cfg()

    batch_id: Annotated[UUID, Internal]
    status: Annotated[BatchStatus, Internal]
    forms: Annotated[int, Field(ge=0), Internal]
    due_on: Annotated[date | None, Internal] = None


class DeliveryFiledIn(BaseModel):
    model_config = _cfg()

    iris_receipt_id: Annotated[str, Field(min_length=1, max_length=64), Internal]
    filed_on: Annotated[date, Internal]
    evidence_version_id: Annotated[UUID, Internal]


class DeliveryAckIn(BaseModel):
    model_config = _cfg()

    status: Annotated[Literal["accepted", "rejected"], Internal]
    at: Annotated[datetime, Internal]
    evidence_version_id: Annotated[UUID, Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

delivery_router = AbacusRouter(prefix="/v1", tags=["closes"])
_C = "/closes/{close_id}"
_PKG = f"{_C}/package"


async def _on(ctx: AuthContext, flag: Flag) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


async def _human(ctx: AuthContext, flag: Flag, action: str) -> None:
    await _on(ctx, flag)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


def _not_built[M: BaseModel](model: type[M]) -> M:
    """The stub's answer until its row builds it (501); the route already masks what it returns,
    so the built body keeps the offshore masking (review 6)."""
    raise NotImplementedYet


@delivery_router.get(
    _PKG, action="close_package.read", response_model=DeliveryPackageOut, errors=(501,)
)
async def package_route(close_id: UUID, ctx: Ctx) -> DeliveryPackageOut:
    """Structure, preconditions and route (C-02-T21, DEC-5703): figures from the posted TB."""
    from abacus.modules.closes.package_service import get_package

    await _on(ctx, CLOSES_DELIVERY)
    return await get_package(ctx, close_id)


@delivery_router.patch(
    _PKG, action="close_package.edit", response_model=DeliveryPackageOut, errors=(409, 501)
)
async def package_edit_route(
    close_id: UUID, body: DeliveryPackageEditIn, ctx: Ctx
) -> DeliveryPackageOut:
    """Section toggles and the CAS answer: a new version at the version seen (C-02-T21)."""
    from abacus.modules.closes.package_service import edit_package

    await _human(ctx, CLOSES_DELIVERY, "close_package.edit")
    return await edit_package(ctx, close_id, body)


@delivery_router.patch(
    f"{_PKG}/commentary",
    action="close_package.edit",
    response_model=DeliveryPackageOut,
    errors=(409, 501),
)
async def commentary_route(
    close_id: UUID, body: DeliveryCommentaryIn, ctx: Ctx
) -> DeliveryPackageOut:
    """Only commentary is editable; figures are locked to the ledger."""
    await _human(ctx, CLOSES_DELIVERY, "close_package.edit")
    raise NotImplementedYet


@delivery_router.post(
    f"{_PKG}/generate",
    action="close_package.generate",
    response_model=DeliveryGenerateOut,
    status_code=202,
    errors=(409, 501),
)
async def generate_route(close_id: UUID, ctx: Ctx) -> DeliveryGenerateOut:
    """A deterministic DET run; regenerate keeps commentary edits."""
    await _human(ctx, CLOSES_DELIVERY, "close_package.generate")
    raise NotImplementedYet


@delivery_router.get(
    f"{_PKG}/pages/{{page_no}}",
    action="close_package.read",
    response_model=DeliveryPageOut,
    errors=(501,),
)
async def page_route(close_id: UUID, page_no: int, ctx: Ctx) -> DeliveryPageOut:
    await _on(ctx, CLOSES_DELIVERY)
    raise NotImplementedYet


@delivery_router.get(
    f"{_C}/package.pdf", action="close_package.export", response_model=bytes, errors=(501,)
)
async def package_pdf_route(close_id: UUID, ctx: Ctx) -> bytes:
    await _human(ctx, CLOSES_DELIVERY, "close_package.export")
    raise NotImplementedYet


@delivery_router.get(
    f"{_C}/package.xlsx", action="close_package.export", response_model=bytes, errors=(501,)
)
async def package_xlsx_route(close_id: UUID, ctx: Ctx) -> bytes:
    await _human(ctx, CLOSES_DELIVERY, "close_package.export")
    raise NotImplementedYet


@delivery_router.post(
    f"{_PKG}/release",
    action="close_package.release",
    response_model=DeliveryPackageOut,
    status_code=202,
    errors=(409, 501),
)
async def close_package_release_route(
    close_id: UUID, body: DeliveryReleaseIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DeliveryPackageOut:
    """Partner only, live, fresh MFA; 409 `release_preconditions_unmet` (C-02-T23)."""
    await _human(ctx, CLOSES_DELIVERY, "close_package.release")
    raise NotImplementedYet


@delivery_router.post(
    f"{_C}/lock", action="close.lock", response_model=DeliveryCloseStateOut, errors=(409, 501)
)
async def lock_route(close_id: UUID, ctx: Ctx) -> DeliveryCloseStateOut:
    """409 `client_approval_required` before the client approves."""
    await _human(ctx, CLOSES_DELIVERY, "close.lock")
    raise NotImplementedYet


@delivery_router.post(
    f"{_C}/reopen", action="close.reopen", response_model=DeliveryCloseStateOut, errors=(409, 501)
)
async def reopen_route(close_id: UUID, body: DeliveryReopenIn, ctx: Ctx) -> DeliveryCloseStateOut:
    await _human(ctx, CLOSES_DELIVERY, "close.reopen")
    raise NotImplementedYet


@delivery_router.get(
    f"{_C}/tax-handoff",
    action="tax_handoff.read",
    response_model=DeliveryHandoffOut,
    errors=(501,),
)
async def close_tax_handoff_route(close_id: UUID, ctx: Ctx) -> DeliveryHandoffOut:
    """Availability and preview; `handoff_not_available` before a locked December close."""
    await _on(ctx, CLOSES_TAX_HANDOFF)
    raise NotImplementedYet


@delivery_router.post(
    f"{_C}/tax-handoff",
    action="tax_handoff.publish",
    response_model=DeliveryHandoffPublishedOut,
    status_code=202,
    errors=(409, 501),
)
async def close_tax_handoff_publish_route(
    close_id: UUID, body: DeliveryHandoffIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DeliveryHandoffPublishedOut:
    """Publish through C12 `receive_tb_handoff` (C-02-T39)."""
    await _human(ctx, CLOSES_TAX_HANDOFF, "tax_handoff.publish")
    raise NotImplementedYet


@delivery_router.get(
    "/client-entities/{client_entity_id}/information-returns",
    action="information_returns.read",
    response_model=DeliveryInformationReturnsOut,
    errors=(501,),
)
async def information_returns_route(
    client_entity_id: UUID, ctx: Ctx, tax_year: int, w9: W9Status | None = None
) -> DeliveryInformationReturnsOut:
    """CLS-13 tiles, rule text from C21 rows, vendor rows (C-02-T45). Each row's TIN last four is
    masked for an offshore reader (review 6)."""
    await _on(ctx, CLOSES_INFORMATION_RETURNS)
    return await mask_tins_for(ctx, _not_built(DeliveryInformationReturnsOut))


@delivery_router.get(
    "/vendors/{vendor_id}", action="information_returns.read", response_model=DeliveryVendorRowOut,
    errors=(501,),
)  # fmt: skip
async def vendor_route(vendor_id: UUID, ctx: Ctx) -> DeliveryVendorRowOut:
    await _on(ctx, CLOSES_INFORMATION_RETURNS)
    return await mask_tins_for(ctx, _not_built(DeliveryVendorRowOut))


@delivery_router.patch(
    "/vendors/{vendor_id}", action="vendor_1099.update", response_model=DeliveryVendorRowOut,
    errors=(409, 501),
)  # fmt: skip
async def vendor_patch_route(
    vendor_id: UUID, body: DeliveryVendorPatchIn, ctx: Ctx
) -> DeliveryVendorRowOut:
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "vendor_1099.update")
    return await mask_tins_for(ctx, _not_built(DeliveryVendorRowOut))


@delivery_router.post(
    "/vendors/{vendor_id}/tin:reveal", action="tin.reveal", response_model=TinRevealOut,
    errors=(409, 501),
)  # fmt: skip
async def tin_reveal_route(vendor_id: UUID, body: DeliveryRevealIn, ctx: Ctx) -> TinRevealOut:
    """Logged; refused offshore (`tin_reveal_refused`). The one reveal payload (organisations'
    `TinRevealOut`, the vendor as `entity_id`): no second schema carries a TIN (DEC-141)."""
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "tin.reveal")
    raise NotImplementedYet


@delivery_router.post(
    "/client-entities/{client_entity_id}/w9-requests", action="w9.request",
    response_model=DeliveryW9RequestOut, status_code=201, errors=(409, 501),
)  # fmt: skip
async def w9_request_route(
    client_entity_id: UUID, body: DeliveryW9RequestIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DeliveryW9RequestOut:
    """Portal requests through C5, sent by a person (DEC-74)."""
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "w9.request")
    raise NotImplementedYet


@delivery_router.post(
    "/vendors/{vendor_id}/tin-match-results", action="tin_match.record",
    response_model=DeliveryRecordOut, status_code=201, errors=(409, 501),
)  # fmt: skip
async def tin_match_route(
    vendor_id: UUID, body: DeliveryTinMatchIn, ctx: Ctx
) -> DeliveryRecordOut:
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "tin_match.record")
    raise NotImplementedYet


@delivery_router.post(
    "/vendors/{vendor_id}/backup-withholding", action="backup_withholding.record",
    response_model=DeliveryRecordOut, status_code=201, errors=(409, 501),
)  # fmt: skip
async def backup_withholding_route(
    vendor_id: UUID, body: DeliveryBackupWithholdingIn, ctx: Ctx
) -> DeliveryRecordOut:
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "backup_withholding.record")
    raise NotImplementedYet


@delivery_router.post(
    "/information-return-batches", action="information_return_batch.approve",
    response_model=DeliveryReturnBatchOut, status_code=201, errors=(409, 501),
)  # fmt: skip
async def return_batch_route(body: DeliveryReturnBatchIn, ctx: Ctx) -> DeliveryReturnBatchOut:
    """After the December close locks (`close_not_locked`); human only."""
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "information_return_batch.approve")
    raise NotImplementedYet


@delivery_router.get(
    "/information-return-batches/{batch_id}/iris.csv",
    action="information_return_batch.export", response_model=bytes, errors=(409, 501),
)  # fmt: skip
async def iris_csv_route(batch_id: UUID, ctx: Ctx) -> bytes:
    """A deterministic IRIS CSV a person uploads; Accrued never transmits."""
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "information_return_batch.export")
    raise NotImplementedYet


@delivery_router.post(
    "/information-return-batches/{batch_id}/filed",
    action="information_return_batch.record_filing", response_model=DeliveryReturnBatchOut,
    errors=(409, 501),
)  # fmt: skip
async def filed_route(batch_id: UUID, body: DeliveryFiledIn, ctx: Ctx) -> DeliveryReturnBatchOut:
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "information_return_batch.record_filing")
    raise NotImplementedYet


@delivery_router.post(
    "/information-return-batches/{batch_id}/acknowledgement",
    action="information_return_batch.record_ack", response_model=DeliveryReturnBatchOut,
    errors=(409, 501),
)  # fmt: skip
async def ack_route(batch_id: UUID, body: DeliveryAckIn, ctx: Ctx) -> DeliveryReturnBatchOut:
    await _human(ctx, CLOSES_INFORMATION_RETURNS, "information_return_batch.record_ack")
    raise NotImplementedYet
