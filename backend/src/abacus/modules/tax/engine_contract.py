"""The tax-engine bridge and the e-file record, the stub (T-01-T02; T-01 §3.8 to §3.15, §4.3).
Contracts: `docs/contracts/tax-engine-bridge.md` and `docs/contracts/efile-record.md`.

CCH Axcess Tax is the engine of record (ADR-231): Accrued exports a workbook after a person's final
approval, imports engine files (values, diagnostics, PDFs, acknowledgements) through a diff a
person approves, assembles the delivery packet, drafts the 8879 envelope with the amount binding
that relocks on drift beyond the Pub 1345 tolerances (C21), and records what the ERO did. Accrued
is never an ERO or a transmitter (R-04): `transmissions` is a person's record of a transmission
made in the engine, and no route here talks to the IRS or a state.

The red files T-01 builds behind these routes (declared protected in T-01-T07): `tax/approval.py`
(final approval, the only writer of a tax return's `final_approval` sign-off), `tax/export.py`,
`tax/filing.py` (bindings, transmissions, acks) and `tax/tri.py`.

Each route answers 404 for a client principal (INV-4), 403 for a principal the matrix refuses, 404
with its flag off (`tax.engine_bridge` for approval, sync, export and import; `tax.delivery_efile`
for delivery, e-file and acks) and 501 `not_implemented` with it on. Every write takes an
`Idempotency-Key`; every state change carries `seen_version` (409 `stale_version`).

Classification (ADR-031): figures, diffs, diagnostics and packets are TRI; names are confidential;
a submission id shows its last four only.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Final, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Header, Path, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import TAX_DELIVERY_EFILE, TAX_ENGINE_BRIDGE
from abacus.kernel.classification import classified
from abacus.kernel.clock import now
from abacus.kernel.errors import DomainTooLarge, NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)
from abacus.modules.tax import approval, engine_import

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=200)]
ReturnId = Annotated[UUID, Path()]
Sha256 = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]

# The sync chip: the blueprint's `return_sync_chip` codes (status registry; T-02-T04).
SyncState = Literal[
    "not_yet_exported",
    "ready_for_export",
    "exporting",
    "synced",
    "out_of_sync",
    "import_pending_approval",
    "failed",
]
ImportKind = Literal["values", "diagnostics", "pdfs", "acks"]
ImportStatus = Literal["scanning", "pending_approval", "approved", "rejected", "routed"]
PacketStatus = Literal["draft", "approved", "superseded"]
Last4 = Annotated[str, Field(pattern=r"^[0-9A-Za-z]{4}$")]
Jurisdiction = Annotated[str, Field(pattern=r"^(US|[A-Z]{2})$")]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


# --- final approval (TAX-09 a, a2, b; SHL-12 h) -------------------------------------------------


class ApprovalBlockerOut(BaseModel):
    """Why final approval is not open yet: a code and the record it names, never prose."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    ref_id: Annotated[UUID | None, classified("internal")]


class FinalApprovalOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    return_id: Annotated[UUID, classified("internal")]
    eligible: Annotated[bool, classified("internal")]
    blockers: Annotated[list[ApprovalBlockerOut], classified("internal")]
    approver_user_id: Annotated[UUID | None, classified("internal")]
    checkpoint_id: Annotated[UUID | None, classified("internal")]
    content_hash: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("confidential")]


class FinalApprovalIn(BaseModel):
    model_config = _frozen()

    seen_checkpoint_id: Annotated[UUID, classified("internal")]
    content_hash: Annotated[Sha256, classified("internal")]


# --- engine sync, exports and imports (TAX-09 c, d, e) ------------------------------------------


EngineSyncKind = Literal[
    "export_generated",
    "marked_exported",
    "import_uploaded",
    "import_approved",
    "import_rejected",
    "diagnostics",
    "pdfs",
    "acks",
    "changed_after_import",  # T-01-T15 (additive): Accrued changed after the last import
]


class EngineSyncEventOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    kind: Annotated[EngineSyncKind, classified("internal")]
    actor_name: Annotated[str | None, classified("confidential")]
    at: Annotated[datetime, classified("confidential")]
    # T-01-T15 (additive): the engine's return version ("2025I:FeldJ:V3"), and the fields a
    # change or a diagnostics run counts ("3 fields", "0 errors · 2 informational").
    engine_version: Annotated[str | None, classified("confidential")] = None
    field_keys: Annotated[list[str], classified("internal")] = Field(default_factory=list[str])
    errors: Annotated[int | None, classified("internal")] = None
    informational: Annotated[int | None, classified("internal")] = None


class EngineDiagnosticOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    severity: Annotated[Literal["error", "informational"], classified("internal")]
    field_key: Annotated[str | None, classified("internal")]
    # The engine's message is client-system content: hostile, TRI (ADR-052).
    message_text: Annotated[str, classified("restricted", tri=True)]
    issue_id: Annotated[UUID | None, classified("internal")]


class EngineSyncOut(BaseModel):
    """TAX-09's chip, history, diagnostics and the connection facts (file bridge, never API)."""

    model_config = ConfigDict(frozen=True)

    return_id: Annotated[UUID, classified("internal")]
    state: Annotated[SyncState, classified("internal")]
    engine_return_id: Annotated[str | None, classified("confidential")]
    mode: Annotated[Literal["file_bridge"], classified("internal")]
    history: Annotated[list[EngineSyncEventOut], classified("confidential")]
    diagnostics: Annotated[list[EngineDiagnosticOut], classified("restricted", tri=True)]
    allowed_actions: Annotated[list[str], classified("internal")]
    # T-01-T15 (additive): why Export is not open yet (codes, and the names they need: the
    # approver of record and the policy, the source of a draft K-1), and the synced date.
    blockers: Annotated[list[ApprovalBlockerOut], classified("internal")] = Field(
        default_factory=list[ApprovalBlockerOut]
    )
    approver_name: Annotated[str | None, classified("confidential")] = None
    policy_code: Annotated[str | None, classified("internal")] = None  # "BH-TAX-02"
    draft_k1_source: Annotated[str | None, classified("confidential")] = None
    synced_at: Annotated[datetime | None, classified("confidential")] = None


class EngineExportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    return_id: Annotated[UUID, classified("internal")]
    checkpoint_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    sha256: Annotated[str, classified("internal")]
    generated_at: Annotated[datetime, classified("confidential")]
    marked_exported_at: Annotated[datetime | None, classified("confidential")]


class EngineExportIn(BaseModel):
    model_config = _frozen()

    checkpoint_id: Annotated[UUID, classified("internal")]


class MarkExportedIn(BaseModel):
    model_config = _frozen()

    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class ImportDiffRowOut(BaseModel):
    """One field: Accrued's value against the engine's, and why they differ (a fixed code)."""

    model_config = ConfigDict(frozen=True)

    field_key: Annotated[str, classified("internal")]
    accrued: Annotated[Decimal | None, classified("restricted", tri=True)]
    engine: Annotated[Decimal | None, classified("restricted", tri=True)]
    cause_code: Annotated[str | None, classified("internal")]
    # T-01-T15 (additive): a value that is not one amount (four vouchers, a masked account, a
    # method), and the figures the cause line cites, as the engine file gave them.
    engine_display: Annotated[str | None, classified("restricted", tri=True)] = None
    cause_facts: Annotated[dict[str, str], classified("restricted", tri=True)] = Field(
        default_factory=dict[str, str]
    )


class EngineImportOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    return_id: Annotated[UUID, classified("internal")]
    kind: Annotated[ImportKind, classified("internal")]
    status: Annotated[
        Literal["scanning", "pending_approval", "approved", "rejected", "routed"],
        classified("internal"),
    ]
    rows: Annotated[list[ImportDiffRowOut], classified("restricted", tri=True)]
    uploaded_at: Annotated[datetime, classified("confidential")]
    allowed_actions: Annotated[list[str], classified("internal")]


class ImportApproveIn(BaseModel):
    model_config = _frozen()

    accepted_field_keys: Annotated[list[str], Field(max_length=2000), classified("internal")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class ImportRejectIn(BaseModel):
    model_config = _frozen()

    reason: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


# --- delivery, the 8879 binding, transmissions and acks (TAX-12) --------------------------------


class DeliveryItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[str, classified("internal")]
    evidence_version_id: Annotated[UUID | None, classified("internal")]
    included: Annotated[bool, classified("internal")]


class PaymentInstructionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    jurisdiction: Annotated[str, classified("internal")]
    kind: Annotated[Literal["refund", "balance_due", "estimate"], classified("internal")]
    amount: Annotated[Decimal, classified("restricted", tri=True)]
    due_on: Annotated[date | None, classified("restricted", tri=True)]


class DeliveryOut(BaseModel):
    """TAX-12's checklist read model."""

    model_config = ConfigDict(frozen=True)

    return_id: Annotated[UUID, classified("internal")]
    packet_id: Annotated[UUID | None, classified("internal")]
    packet_status: Annotated[
        Literal["draft", "approved", "superseded"] | None, classified("internal")
    ]
    items: Annotated[list[DeliveryItemOut], classified("restricted", tri=True)]
    payments: Annotated[list[PaymentInstructionOut], classified("restricted", tri=True)]
    envelope_id: Annotated[UUID | None, classified("internal")]
    binding_id: Annotated[UUID | None, classified("internal")]
    binding_superseded: Annotated[bool, classified("internal")]
    transmitted_on: Annotated[date | None, classified("confidential")]
    acks: Annotated[list[EfileAckOut], classified("restricted", tri=True)]
    allowed_actions: Annotated[list[str], classified("internal")]


class DeliveryPacketOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    return_id: Annotated[UUID, classified("internal")]
    version: Annotated[int, classified("internal")]
    status: Annotated[Literal["draft", "approved", "superseded"], classified("internal")]
    items: Annotated[list[DeliveryItemOut], classified("restricted", tri=True)]
    letter_document_id: Annotated[UUID | None, classified("internal")]
    approved_by_name: Annotated[str | None, classified("confidential")]


class DeliveryPacketPatchIn(BaseModel):
    model_config = _frozen()

    included: Annotated[dict[str, bool], classified("internal")]
    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class SeenVersionIn(BaseModel):
    model_config = _frozen()

    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class EfileEnvelopeOut(BaseModel):
    """The drafted 8879 envelope (C7) and the amount binding it is signed against."""

    model_config = ConfigDict(frozen=True)

    envelope_id: Annotated[UUID, classified("internal")]
    binding_id: Annotated[UUID, classified("internal")]
    authorization_form: Annotated[str, classified("internal")]
    tolerances_reference_set_version_id: Annotated[UUID, classified("internal")]


class EroNoticeOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    notified_user_id: Annotated[UUID, classified("internal")]
    notified_at: Annotated[datetime, classified("confidential")]


class TransmissionIn(BaseModel):
    """The ERO's record of a transmission made in the engine (409 `signatures_incomplete`,
    `binding_superseded`, `not_synced`)."""

    model_config = _frozen()

    jurisdictions: Annotated[
        list[Jurisdiction], Field(min_length=1, max_length=60), classified("internal")
    ]
    transmitted_on: Annotated[date, classified("confidential")]
    method: Annotated[Literal["practitioner_pin", "ero_signature"], classified("internal")]
    seen_binding_id: Annotated[UUID, classified("internal")]


class TransmissionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    return_id: Annotated[UUID, classified("internal")]
    ero_user_id: Annotated[UUID, classified("internal")]
    jurisdictions: Annotated[list[str], classified("internal")]
    transmitted_on: Annotated[date, classified("confidential")]
    recorded_at: Annotated[datetime, classified("confidential")]


class EfileAckIn(BaseModel):
    model_config = _frozen()

    jurisdiction: Annotated[Jurisdiction, classified("internal")]
    status: Annotated[Literal["accepted", "rejected"], classified("internal")]
    submission_id_last4: Annotated[
        str, Field(pattern=r"^[0-9A-Za-z]{4}$"), classified("confidential")
    ]
    reject_code: Annotated[str | None, Field(max_length=40), classified("internal")] = None
    received_at: Annotated[datetime, classified("confidential")]
    upload_id: Annotated[UUID, classified("internal")]


class EfileAckOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    jurisdiction: Annotated[str, classified("internal")]
    status: Annotated[Literal["accepted", "rejected"], classified("internal")]
    submission_id_last4: Annotated[str, classified("confidential")]
    reject_code: Annotated[str | None, classified("internal")]
    reject_text: Annotated[str | None, classified("restricted", tri=True)]
    received_at: Annotated[datetime, classified("confidential")]
    source: Annotated[Literal["engine_file", "manual"], classified("internal")]


class DeliverablePublishOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    delivery_id: Annotated[UUID, classified("internal")]
    published_at: Annotated[datetime, classified("confidential")]


class EroDesignationIn(BaseModel):
    model_config = _frozen()

    designated: Annotated[bool, classified("internal")]


class EroDesignationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    user_id: Annotated[UUID, classified("internal")]
    designated: Annotated[bool, classified("internal")]


DeliveryOut.model_rebuild()

# --- routes --------------------------------------------------------------------------------------

engine_router = AbacusRouter(prefix="/v1", tags=["tax-engine"])


async def _stub(ctx: AuthContext, action: str, flag: Flag) -> NoReturn:
    """INV-4 (404 for a client principal), then the matrix (403), the flag (404), then 501. The
    work-item conditions (`function_in(signer)`, BH-TAX-02) are checked against the return once
    the routes are built; the stub checks the role."""
    if ctx.client:
        raise NotFound("tax_return")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    raise NotImplementedYet


async def _live(ctx: AuthContext, action: str, flag: Flag) -> None:
    """A built route: INV-4, the role row, then the flag; the service checks the return."""
    if ctx.client:
        raise NotFound("tax_return")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


def _approval_out(found: approval.Eligibility, approved_at: datetime | None) -> FinalApprovalOut:
    return FinalApprovalOut(
        return_id=found.return_id,
        eligible=found.eligible,
        blockers=[ApprovalBlockerOut(kind=b.kind, ref_id=b.ref_id) for b in found.blockers],
        approver_user_id=found.signer,
        checkpoint_id=found.checkpoint_id,
        content_hash=found.content_hash,
        approved_at=approved_at,
    )


def _typed(value: object) -> tuple[object, object]:
    """A stored `{t, v}` as its type and value (anything else as no value)."""
    if isinstance(value, dict):
        typed = cast(dict[str, object], value)
        return typed.get("t"), typed.get("v")
    return None, None


def _amount(value: object) -> Decimal | None:
    kind, raw = _typed(value)
    return Decimal(str(raw)) if kind == "decimal" and raw is not None else None


def _display(value: object) -> str | None:
    kind, raw = _typed(value)
    return str(raw) if kind != "decimal" and raw is not None else None


def _import_out(v: engine_import.ImportView) -> EngineImportOut:
    return EngineImportOut(
        id=v.id,
        return_id=v.return_id,
        kind=v.kind,
        status=v.status,
        rows=[
            ImportDiffRowOut(
                field_key=str(r["field_key"]),
                accrued=_amount(r["accrued"]),
                engine=_amount(r["engine"]),
                cause_code=cast(str | None, r["cause_code"]),
                engine_display=_display(r["engine"]),
            )
            for r in v.rows
        ],
        uploaded_at=v.uploaded_at,
        allowed_actions=list(v.allowed_actions),
    )


MAX_ENGINE_FILE: Final = 10 * 1024 * 1024


async def _file(request: Request) -> bytes:
    """The engine file, refused past the limit before it is all read (413)."""
    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > MAX_ENGINE_FILE:
            raise DomainTooLarge(facts={"limit": MAX_ENGINE_FILE})
    return bytes(data)


B, D = TAX_ENGINE_BRIDGE, TAX_DELIVERY_EFILE


@engine_router.get(
    "/tax-returns/{return_id}/final-approval",
    action="tax_return.read",
    response_model=FinalApprovalOut,
)
async def final_approval_route(return_id: ReturnId, ctx: Ctx) -> FinalApprovalOut:
    """Eligibility facts and blockers (T-01-T18; TAX-02, TAX-09 a/a2)."""
    await _live(ctx, "tax_return.read", B)
    return _approval_out(await approval.eligibility(ctx, return_id), None)


@engine_router.post(
    "/tax-returns/{return_id}/final-approval",
    action="tax_return.approve",
    response_model=FinalApprovalOut,
    errors=(409,),
)
async def approve_return_route(
    return_id: ReturnId, body: FinalApprovalIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FinalApprovalOut:
    """SHL-12 h: the L4 sign-off, recorded only by `tax/approval.py` (T-01-T18)."""
    await _live(ctx, "tax_return.approve", B)
    found = await approval.approve(ctx, return_id, body.seen_checkpoint_id, body.content_hash)
    return _approval_out(found, await now(ctx.tenant))


@engine_router.get(
    "/tax-returns/{return_id}/engine-sync",
    action="tax_return.read",
    response_model=EngineSyncOut,
)
async def engine_sync_route(return_id: ReturnId, ctx: Ctx) -> EngineSyncOut:
    """TAX-09's chip, history and diagnostics, derived (T-01-T19)."""
    await _live(ctx, "tax_return.read", B)
    v = await engine_import.sync_view(ctx, return_id)
    return EngineSyncOut(
        return_id=v.return_id,
        state=v.state,
        engine_return_id=v.engine_return_id,
        mode="file_bridge",
        history=[
            EngineSyncEventOut(
                id=e.id,
                kind=cast(EngineSyncKind, e.kind),
                actor_name=e.actor_name,
                at=e.at,
                engine_version=e.engine_version,
                field_keys=list(e.field_keys),
                errors=e.errors,
                informational=e.informational,
            )
            for e in v.history
        ],
        diagnostics=[
            EngineDiagnosticOut(
                code=str(d["code"]),
                severity="error" if d["severity"] == "error" else "informational",
                field_key=cast(str | None, d["field_key"]),
                message_text=str(d["message_text"]),
                issue_id=cast(UUID | None, d["issue_id"]),
            )
            for d in v.diagnostics
        ],
        allowed_actions=list(v.allowed_actions),
        synced_at=v.synced_at,
    )


@engine_router.post(
    "/tax-returns/{return_id}/engine-exports",
    action="tax_return.export",
    response_model=EngineExportOut,
    status_code=201,
    errors=(409, 501),
)
async def export_return_route(
    return_id: ReturnId, body: EngineExportIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EngineExportOut:
    """Generate the workbook after final approval (consumes the write grant)."""
    await _stub(ctx, "tax_return.export", B)


@engine_router.get(
    "/engine-exports/{export_id}/file",
    action="tax_return.export",
    response_model=bytes,
    errors=(501,),
)
async def export_file_route(export_id: Annotated[UUID, Path()], ctx: Ctx) -> bytes:
    await _stub(ctx, "tax_return.export", B)


@engine_router.post(
    "/engine-exports/{export_id}/mark-exported",
    action="tax_return.export",
    response_model=EngineExportOut,
    errors=(409, 501),
)
async def mark_exported_route(
    export_id: Annotated[UUID, Path()], body: MarkExportedIn, ctx: Ctx
) -> EngineExportOut:
    """A person confirms the file reached the engine."""
    await _stub(ctx, "tax_return.export", B)


@engine_router.post(
    "/tax-returns/{return_id}/engine-imports",
    action="engine_import.create",
    response_model=EngineImportOut,
    status_code=201,
    errors=(409,),
)
async def upload_import_route(
    return_id: ReturnId,
    request: Request,
    ctx: Ctx,
    kind: Annotated[ImportKind, Query()],
    file_name: Annotated[str, Header(alias="X-File-Name", min_length=1, max_length=255)],
) -> EngineImportOut:
    """An engine file as the raw body (no multipart; DEC-1363): scanned and stored, parsed in the
    isolated child; values wait as "Import pending approval" (T-01-T19). 409
    `engine_return_mismatch`, `engine_version_behind`, `import_pending`; 422
    `engine_file_invalid`, `import_kind_unavailable`."""
    await _live(ctx, "engine_import.create", B)
    content = await _file(request)
    return _import_out(await engine_import.import_file(ctx, return_id, kind, file_name, content))


@engine_router.get(
    "/engine-imports/{import_id}",
    action="tax_return.read",
    response_model=EngineImportOut,
)
async def engine_import_route(import_id: Annotated[UUID, Path()], ctx: Ctx) -> EngineImportOut:
    """TAX-09 O4: the import's diff rows (T-01-T19)."""
    await _live(ctx, "tax_return.read", B)
    return _import_out(await engine_import.import_view(ctx, import_id))


@engine_router.post(
    "/engine-imports/{import_id}/approve",
    action="engine_import.approve",
    response_model=EngineImportOut,
    errors=(409,),
)
async def approve_import_route(
    import_id: Annotated[UUID, Path()], body: ImportApproveIn, ctx: Ctx
) -> EngineImportOut:
    """TAX-09 c: approve the accepted rows only (a person). 409 `import_decided`,
    `stale_version`; 422 `nothing_accepted`."""
    await _live(ctx, "engine_import.approve", B)
    found = await engine_import.resolve_import(
        ctx,
        import_id,
        accepted=body.accepted_field_keys,
        seen_version=body.seen_version,
        reason=None,
    )
    return _import_out(found)


@engine_router.post(
    "/engine-imports/{import_id}/reject",
    action="engine_import.approve",
    response_model=EngineImportOut,
    errors=(409,),
)
async def reject_import_route(
    import_id: Annotated[UUID, Path()], body: ImportRejectIn, ctx: Ctx
) -> EngineImportOut:
    """TAX-09 e: reject the import with a reason (a person). 409 `import_decided`,
    `stale_version`."""
    await _live(ctx, "engine_import.approve", B)
    found = await engine_import.resolve_import(
        ctx, import_id, accepted=(), seen_version=body.seen_version, reason=body.reason
    )
    return _import_out(found)


@engine_router.get(
    "/tax-returns/{return_id}/delivery",
    action="tax_return.read",
    response_model=DeliveryOut,
    errors=(501,),
)
async def delivery_route(return_id: ReturnId, ctx: Ctx) -> DeliveryOut:
    await _stub(ctx, "tax_return.read", D)


@engine_router.post(
    "/tax-returns/{return_id}/delivery-packet:assemble",
    action="delivery_packet.prepare",
    response_model=DeliveryPacketOut,
    status_code=201,
    errors=(409, 501),
)
async def assemble_packet_route(
    return_id: ReturnId, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DeliveryPacketOut:
    await _stub(ctx, "delivery_packet.prepare", D)


@engine_router.patch(
    "/delivery-packets/{packet_id}",
    action="delivery_packet.prepare",
    response_model=DeliveryPacketOut,
    errors=(409, 501),
)
async def patch_packet_route(
    packet_id: Annotated[UUID, Path()], body: DeliveryPacketPatchIn, ctx: Ctx
) -> DeliveryPacketOut:
    await _stub(ctx, "delivery_packet.prepare", D)


@engine_router.post(
    "/delivery-packets/{packet_id}/letter:regenerate",
    action="delivery_packet.prepare",
    response_model=DeliveryPacketOut,
    errors=(409, 501),
)
async def regenerate_letter_route(
    packet_id: Annotated[UUID, Path()], body: SeenVersionIn, ctx: Ctx
) -> DeliveryPacketOut:
    """The cover letter from a template (no model text; ADR P-25 off)."""
    await _stub(ctx, "delivery_packet.prepare", D)


@engine_router.post(
    "/delivery-packets/{packet_id}/approve",
    action="delivery_packet.approve",
    response_model=DeliveryPacketOut,
    errors=(409, 501),
)
async def approve_packet_route(
    packet_id: Annotated[UUID, Path()], body: SeenVersionIn, ctx: Ctx
) -> DeliveryPacketOut:
    await _stub(ctx, "delivery_packet.approve", D)


@engine_router.post(
    "/tax-returns/{return_id}/efile-envelope",
    action="delivery_packet.prepare",
    response_model=EfileEnvelopeOut,
    status_code=201,
    errors=(409, 501),
)
async def efile_envelope_route(
    return_id: ReturnId, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EfileEnvelopeOut:
    """Draft the 8879 envelope through C7 with the amount binding (C21 tolerances)."""
    await _stub(ctx, "delivery_packet.prepare", D)


@engine_router.post(
    "/tax-returns/{return_id}/ero-notices",
    action="delivery_packet.prepare",
    response_model=EroNoticeOut,
    status_code=201,
    errors=(409, 501),
)
async def ero_notice_route(return_id: ReturnId, ctx: Ctx) -> EroNoticeOut:
    await _stub(ctx, "delivery_packet.prepare", D)


@engine_router.post(
    "/tax-returns/{return_id}/transmissions",
    action="transmission.record",
    response_model=TransmissionOut,
    status_code=201,
    errors=(409, 501),
)
async def record_transmission_route(
    return_id: ReturnId, body: TransmissionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> TransmissionOut:
    """The ERO's human record (never a transmission by Accrued; R-04)."""
    await _stub(ctx, "transmission.record", D)


@engine_router.post(
    "/tax-returns/{return_id}/acks",
    action="efile_ack.record",
    response_model=EfileAckOut,
    status_code=201,
    errors=(409, 501),
)
async def record_ack_route(
    return_id: ReturnId, body: EfileAckIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EfileAckOut:
    await _stub(ctx, "efile_ack.record", D)


@engine_router.post(
    "/tax-returns/{return_id}/deliverables:publish",
    action="deliverable.publish",
    response_model=DeliverablePublishOut,
    errors=(409, 501),
)
async def publish_deliverable_route(
    return_id: ReturnId, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DeliverablePublishOut:
    """Release the client copy to the portal (a person's act; the email is R-01's template)."""
    await _stub(ctx, "deliverable.publish", D)


@engine_router.put(
    "/firm/members/{user_id}/ero",
    action="member.set_ero",
    response_model=EroDesignationOut,
    errors=(501,),
)
async def set_ero_route(
    user_id: Annotated[UUID, Path()], body: EroDesignationIn, ctx: Ctx
) -> EroDesignationOut:
    await _stub(ctx, "member.set_ero", D)


# --- tax.api (T-01-T27 and T-02 implement) -------------------------------------------------------

# T-01-T18 built them in `tax/approval.py`: `eligibility`, `register_final_approval_blocker`.
