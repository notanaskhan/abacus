"""Records governance v1 stub (Q-05-T03; SPEC-711 AC-19 to AC-28; `records-governance.md`).
Screen FIL-02: retention summary and policy versions, destruction batches, approvals, the
documents list and certificates. Q-02's policy and hold routes keep their owners; their extended
bodies (policy text and effective date, hold scope fields) land with Q-05-T11 after Oct 24 (P-29).

Every route answers, in order: a client principal 404 (no portal route; INV-4); the
`records.governance` flag off 404; a human-only route refuses an agent, the platform or a
support session 403 (INV-1); then 501 until its build task (Q-05-T11, T13, T15).

Classification (ADR-031): client names and scope descriptions are `confidential`; ids, counts,
refs, record types and states are `internal`. Nothing here is TRI (record metadata only).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import RECORDS_GOVERNANCE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, Forbidden, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
Internal = classified("internal")
Confidential = classified("confidential")
Count = Annotated[int, Field(ge=0), Internal]

BatchStatus = Literal["awaiting_approval", "approved", "destroying", "destroyed", "cancelled"]
ApproverRole = Literal["firm_admin", "security_admin"]


def _cfg() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class RecordsPersonOut(BaseModel):
    model_config = _cfg()

    user_id: Annotated[UUID, Internal]
    name: Annotated[str, Field(max_length=120), Confidential]


class RecordsSummaryOut(BaseModel):
    """FIL-02 tiles: policies, active holds, pending batch, last certificate."""

    model_config = _cfg()

    policies: Count
    active_holds: Count
    pending_batches: Count
    pending_documents: Count
    last_certificate_ref: Annotated[str | None, Field(max_length=40), Internal] = None
    last_certificate_at: Annotated[datetime | None, Internal] = None


class RecordsPolicyVersionOut(BaseModel):
    """FIL-02 g: one insert-only version (AC-20)."""

    model_config = _cfg()

    version_id: Annotated[UUID, Internal]
    version_no: Annotated[int, Field(ge=1), Internal]
    retention_years: Annotated[int, Field(ge=0, le=100), Internal]
    legal_minimum_years: Annotated[int, Field(ge=0, le=100), Internal]
    policy_text: Annotated[str | None, Field(max_length=4000), Internal] = None
    effective_from: Annotated[date | None, Internal] = None
    created_by: Annotated[RecordsPersonOut, classified("confidential")]
    created_at: Annotated[datetime, Internal]


class RecordsPolicyVersionListOut(BaseModel):
    model_config = _cfg()

    record_type: Annotated[str, Field(max_length=60), Internal]
    service_line: Annotated[str | None, Field(max_length=20), Internal] = None
    items: Annotated[list[RecordsPolicyVersionOut], Internal]


class RecordsPolicyCreateIn(BaseModel):
    """OQ-11: a service-line override at or above the record type's policy."""

    model_config = _cfg()

    record_type: Annotated[str, Field(min_length=1, max_length=60), Internal]
    service_line: Annotated[Literal["audit", "tax", "cas", "advisory"], Internal]
    retention_years: Annotated[int, Field(ge=0, le=100), Internal]
    policy_text: Annotated[str | None, Field(max_length=4000), Internal] = None
    effective_from: Annotated[date | None, Internal] = None


class RecordsApprovalOut(BaseModel):
    model_config = _cfg()

    approver: Annotated[RecordsPersonOut, classified("confidential")]
    approver_role: Annotated[ApproverRole, Internal]
    approved_at: Annotated[datetime, Internal]


class RecordsBatchOut(BaseModel):
    """FIL-02 c (AC-22): 2026-Q3, 1,204 documents of 31 former clients, Grace Holloway Sep 8."""

    model_config = _cfg()

    batch_id: Annotated[UUID, Internal]
    ref: Annotated[str, Field(max_length=20), Internal]
    scope_description: Annotated[str, Field(max_length=200), Confidential]
    status: Annotated[BatchStatus, Internal]
    assembled_at: Annotated[datetime, Internal]
    eligible_count: Count
    held_excluded_count: Count
    destroyed_count: Count
    client_count: Count
    approvals: Annotated[list[RecordsApprovalOut], Internal]
    hold_recheck_at: Annotated[datetime | None, Internal] = None
    certificate_ref: Annotated[str | None, Field(max_length=40), Internal] = None
    confirmation_phrase: Annotated[str, Field(max_length=40), Internal]
    allowed_actions: Annotated[list[str], Internal] = []


class RecordsBatchListOut(BaseModel):
    model_config = _cfg()

    items: Annotated[list[RecordsBatchOut], Internal]
    next_cursor: Annotated[str | None, Internal] = None


class RecordsApprovalIn(BaseModel):
    """The second approval carries the typed confirmation (AC-23)."""

    model_config = _cfg()

    items_seen: Annotated[int, Field(ge=0), Internal]
    confirmation: Annotated[str | None, Field(max_length=40), Internal] = None


class RecordsCancelIn(BaseModel):
    model_config = _cfg()

    reason: Annotated[str, Field(min_length=1, max_length=500), Confidential]


class RecordsCertificateOut(BaseModel):
    """FIL-02 i (OQ-10): counts, approvers, hold re-check, manifest hash, checkpoint root."""

    model_config = _cfg()

    certificate_id: Annotated[UUID, Internal]
    ref: Annotated[str, Field(max_length=40), Internal]
    batch_id: Annotated[UUID, Internal]
    destroyed_count: Count
    excluded_count: Count
    manifest_sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]
    audit_checkpoint_root: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]
    generated_at: Annotated[datetime, Internal]
    document_version_id: Annotated[UUID, Internal]


# --- routes (each 501, one action) -------------------------------------------------------------

records_governance_router = AbacusRouter(prefix="/v1", tags=["evidence"])
_B = "/destruction-batches/{batch_id}"


def _batch_out(row: dict[str, object]) -> RecordsBatchOut:
    return RecordsBatchOut.model_validate(
        {
            "batch_id": row["id"],
            "ref": row["ref"],
            "scope_description": row["scope_description"],
            "status": row["status"],
            "assembled_at": row["assembled_at"],
            "eligible_count": row["eligible_count"],
            "held_excluded_count": row["held_excluded_count"],
            "destroyed_count": row["destroyed_count"],
            "client_count": row["client_count"],
            "approvals": [],
            "hold_recheck_at": row["hold_recheck_at"],
            "confirmation_phrase": row["confirmation_phrase"],
        }
    )


async def _on(ctx: AuthContext) -> None:
    if ctx.client or not await flag_enabled(ctx.tenant, RECORDS_GOVERNANCE):
        raise NotFound(RECORDS_GOVERNANCE.name)


async def _human(ctx: AuthContext, action: str) -> None:
    await _on(ctx)
    if ctx.tenant.actor_kind != "human" or ctx.is_support:
        raise Forbidden(action, "role")


@records_governance_router.get(
    "/retention/summary", action="retention.read", response_model=RecordsSummaryOut, errors=(501,)
)
async def retention_summary_route(ctx: Ctx) -> RecordsSummaryOut:
    """FIL-02 tiles (Q-05-T11)."""
    from abacus.modules.evidence import destruction

    await _on(ctx)
    return RecordsSummaryOut.model_validate(await destruction.summary(ctx.tenant))


@records_governance_router.get(
    "/retention/policies/{policy_id}/versions",
    action="retention.read",
    response_model=RecordsPolicyVersionListOut,
    errors=(501,),
)
async def retention_policy_versions_route(
    policy_id: UUID, ctx: Ctx
) -> RecordsPolicyVersionListOut:
    await _on(ctx)
    raise NotImplementedYet


@records_governance_router.post(
    "/retention/policies",
    action="retention_policy.manage",
    response_model=RecordsPolicyVersionOut,
    status_code=201,
    errors=(409, 501),
)
async def retention_policy_create_route(
    body: RecordsPolicyCreateIn, ctx: Ctx, key: IdempotencyKey
) -> RecordsPolicyVersionOut:
    """A policy below the legal minimum is refused (AC-19); fresh MFA."""
    await _human(ctx, "retention_policy.manage")
    raise NotImplementedYet


@records_governance_router.get(
    "/destruction-batches",
    action="retention.read",
    response_model=RecordsBatchListOut,
    errors=(501,),
)
async def destruction_batches_route(
    ctx: Ctx, status: BatchStatus | None = None, cursor: str | None = None
) -> RecordsBatchListOut:
    """Newest first (Q-05-T11); the approvals join with Q-05-T12's approval task."""
    from abacus.modules.evidence import destruction

    await _on(ctx)
    del cursor
    rows = await destruction.batches(ctx.tenant, status)
    return RecordsBatchListOut(items=[_batch_out(r) for r in rows])


@records_governance_router.get(
    _B, action="retention.read", response_model=RecordsBatchOut, errors=(501,)
)
async def destruction_batch_route(batch_id: UUID, ctx: Ctx) -> RecordsBatchOut:
    from abacus.modules.evidence import destruction

    await _on(ctx)
    return _batch_out(await destruction.batch(ctx.tenant, batch_id))


@records_governance_router.get(
    f"{_B}/documents.csv", action="destruction.export_list", response_model=bytes, errors=(501,)
)
async def destruction_documents_route(batch_id: UUID, ctx: Ctx) -> bytes:
    """An audited export with fresh MFA (DEC-60)."""
    from abacus.kernel.uow import Target, uow
    from abacus.modules.evidence import destruction

    await _human(ctx, "destruction.export_list")
    body = await destruction.documents_csv(ctx.tenant, batch_id)
    async with uow(ctx.tenant) as tx:
        tx.record("destruction_batch.exported", target=Target("destruction_batch", batch_id))
    return body


@records_governance_router.post(
    f"{_B}/approvals",
    action="destruction.approve",
    response_model=RecordsBatchOut,
    status_code=201,
    errors=(409, 501),
)
async def destruction_approval_route(
    batch_id: UUID, body: RecordsApprovalIn, ctx: Ctx, key: IdempotencyKey
) -> RecordsBatchOut:
    """409 `same_approver`, `approver_role_taken`, `batch_phrase_mismatch` (AC-22, AC-23)."""
    await _human(ctx, "destruction.approve")
    raise NotImplementedYet


@records_governance_router.post(
    f"{_B}/cancel",
    action="destruction.approve",
    response_model=RecordsBatchOut,
    errors=(409, 501),
)
async def destruction_cancel_route(
    batch_id: UUID, body: RecordsCancelIn, ctx: Ctx, key: IdempotencyKey
) -> RecordsBatchOut:
    """Before execution only; API and runbook (OQ-12)."""
    await _human(ctx, "destruction.approve")
    raise NotImplementedYet


@records_governance_router.get(
    "/destruction-certificates/{certificate_id}",
    action="retention.read",
    response_model=RecordsCertificateOut,
    errors=(501,),
)
async def destruction_certificate_route(certificate_id: UUID, ctx: Ctx) -> RecordsCertificateOut:
    await _on(ctx)
    raise NotImplementedYet
