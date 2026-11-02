"""The C8 adjustments contract stub (A-06-T05; SPEC-642; DEC-1965).
Contract: `docs/contracts/adjustments.md` (C8 v1, freeze Fri Oct 1, 2027); screens AUD-16 b, b2,
c, d; consumers EBP-06, T-05, C-02, A-09.

Proposed entries (AJE, RJE, PAJE, TJE, elimination) with their lines, a named person's approval
batches, the approve-and-send to the client through C18 under a 10-second hold, the recorded
client decision, and the adjusted TB read (Unadjusted, AJE, RJE, Final). **No route posts,
books or writes an entry to any client system** (ADR-040; `pe_posting_dormant`). Every route
answers, in order: a client principal 404 (C18's BFF is the client's path); the action on the
work item's engagement; 404 with `adjustments.entries` off; 501 `not_implemented` until A-06-T09
and T10.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import ADJUSTMENTS_ENTRIES
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Money = Annotated[
    Decimal, Field(ge=0, max_digits=20, decimal_places=2), classified("confidential")
]
EntryKind = Literal["aje", "rje", "paje", "tje", "elimination"]
EntryStatus = Literal[
    "proposed",
    "within_threshold",
    "review_required",
    "approved",
    "rejected",
    "client_approved",
    "client_declined",
]  # fmt: skip  -- posted, failed_post and reversed are dormant (pe_posting_dormant)
AdjustmentAction = Literal[
    "proposed_entry.update",
    "proposed_entry.send_to_client",
    "proposed_entry.reject",
    "proposed_entry.record_client_decision",
    "approval_batch.create",
]
Actions = Annotated[list[AdjustmentAction], classified("internal")]
Layer = Literal["unadjusted", "aje", "rje", "final"]


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_code: Annotated[str, Field(min_length=1, max_length=64), classified("internal")]
    debit: Money = Decimal(0)
    credit: Money = Decimal(0)


class LineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    line_no: Annotated[int, Field(ge=1), classified("internal")]
    account_code: Annotated[str, classified("internal")]
    account_name: Annotated[str | None, classified("internal")]
    fs_line_key: Annotated[str | None, classified("internal")]
    debit: Money
    credit: Money


class EntryOut(BaseModel):
    """An entry as AUD-16 b, b2 and c draw it (AJE-1: Dr 1250 48,600 / Cr 4100 33,540 / Cr 4200
    15,060, Review required because Northwind is an attest client)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    ref: Annotated[str, classified("internal")]
    kind: Annotated[EntryKind, classified("internal")]
    description: Annotated[str | None, classified("confidential")]
    amount: Money
    status: Annotated[EntryStatus, classified("internal")]
    threshold_result: Annotated[
        Literal["within_threshold", "review_required"], classified("internal")
    ]
    is_attest_client: Annotated[bool, classified("internal")]
    lines: Annotated[list[LineOut], Field(max_length=200), classified("confidential")]
    # "Approved by Hannah Leclerc under BH AJE thresholds v2" (a named person, never the agent).
    approval_label: Annotated[str | None, classified("internal")]
    version: Annotated[int, Field(ge=1), classified("internal")]
    allowed_actions: Actions


class EntryIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Annotated[EntryKind, classified("internal")]
    description: Annotated[str | None, Field(max_length=500), classified("confidential")] = None
    misstatement_id: Annotated[UUID | None, classified("internal")] = None
    lines: Annotated[list[LineIn], Field(min_length=2, max_length=200), classified("confidential")]


class SendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_ids: Annotated[list[UUID], Field(min_length=1, max_length=100), classified("internal")]
    recipient_contact_id: Annotated[UUID, classified("internal")]
    wording_template_version_id: Annotated[UUID, classified("internal")]
    seen_versions: Annotated[dict[str, int], classified("internal")]


class AdjustmentSendOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    approval_batch_id: Annotated[UUID, classified("internal")]
    undo_until: Annotated[str, classified("internal")]  # ISO instant, 10 seconds out (DEC-24)


class BatchIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entry_ids: Annotated[list[UUID], Field(min_length=1, max_length=500), classified("internal")]
    policy_version_id: Annotated[UUID, classified("internal")]


class BatchOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("internal")]


class ClientDecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Annotated[
        Literal["client_accepted", "client_declined", "client_question"], classified("internal")
    ]
    by_contact_id: Annotated[UUID, classified("internal")]
    decided_on: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$"), classified("internal")]
    reason: Annotated[str | None, Field(max_length=2000), classified("confidential")] = None
    evidence_version_id: Annotated[UUID, classified("internal")]


class RejectIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason_code: Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,59}$"), classified("internal")]


class AdjustedLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    account_code: Annotated[str, classified("internal")]
    account_name: Annotated[str, classified("internal")]
    unadjusted: Annotated[Money | None, classified("confidential")]
    aje: Annotated[Decimal | None, classified("confidential")]
    rje: Annotated[Decimal | None, classified("confidential")]
    final: Annotated[Decimal | None, classified("confidential")]


class AdjustedTbOut(BaseModel):
    """C8's read: the adjusted TB by layer, code's (EBP-06, T-05, A-09, AUD-20)."""

    model_config = ConfigDict(frozen=True)

    layer: Annotated[Layer, classified("internal")]
    lines: Annotated[list[AdjustedLineOut], classified("confidential")]
    pending_entries: Annotated[int, Field(ge=0), classified("internal")]


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str) -> None:
    if ctx.client:
        raise NotFound("adjustments")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await flag_enabled(ctx.tenant, ADJUSTMENTS_ENTRIES):
        raise NotFound(ADJUSTMENTS_ENTRIES.name)


async def _gate_flag(ctx: AuthContext) -> None:
    if ctx.client:
        raise NotFound("adjustments")
    if not await flag_enabled(ctx.tenant, ADJUSTMENTS_ENTRIES):
        raise NotFound(ADJUSTMENTS_ENTRIES.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


router = AbacusRouter(prefix="/v1", tags=["adjustments"])
_WI = "/work-items/{work_item_id}"


@router.get(
    f"{_WI}/proposed-entries",
    action="proposed_entry.read",
    response_model=ListPage[EntryOut],
    errors=(501,),
)
async def proposed_entries_route(
    work_item_id: UUID, ctx: Ctx, kind: EntryKind | None = None
) -> ListPage[EntryOut]:
    await _gate(ctx, work_item_id, "proposed_entry.read")
    _not_yet()


@router.post(
    f"{_WI}/proposed-entries",
    action="proposed_entry.create",
    response_model=EntryOut,
    status_code=201,
    errors=(409, 501),
)
async def proposed_entry_create_route(
    work_item_id: UUID, body: EntryIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EntryOut:
    """A balanced entry (`unbalanced_entry` at commit); an attest client's is Review required."""
    await _gate(ctx, work_item_id, "proposed_entry.create")
    _not_yet()


@router.post(
    f"{_WI}/proposed-entries:approve-and-send",
    action="proposed_entry.send_to_client",
    response_model=AdjustmentSendOut,
    status_code=201,
    errors=(409, 501),
)
async def proposed_entries_send_route(
    work_item_id: UUID, body: SendIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> AdjustmentSendOut:
    """Approve, batch and send through C18; the client sees nothing for 10 seconds (Undo)."""
    await _gate(ctx, work_item_id, "proposed_entry.send_to_client")
    _not_yet()


@router.post(
    "/proposed-entries/{entry_id}/reject",
    action="proposed_entry.reject",
    response_model=EntryOut,
    errors=(409, 501),
)
async def proposed_entry_reject_route(
    entry_id: UUID, body: RejectIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EntryOut:
    await _gate_flag(ctx)
    _not_yet()


@router.post(
    "/proposed-entries/{entry_id}/client-decision:record",
    action="proposed_entry.record_client_decision",
    response_model=EntryOut,
    errors=(409, 501),
)
async def proposed_entry_record_route(
    entry_id: UUID, body: ClientDecisionIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> EntryOut:
    """Record mode: the client's decision from email, with the email as evidence."""
    await _gate_flag(ctx)
    _not_yet()


@router.post(
    "/approval-batches",
    action="approval_batch.create",
    response_model=BatchOut,
    status_code=201,
    errors=(409, 501),
)
async def approval_batch_route(
    body: BatchIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> BatchOut:
    await _gate_flag(ctx)
    _not_yet()


@router.get(
    f"{_WI}/adjusted-tb", action="adjusted_tb.read", response_model=AdjustedTbOut, errors=(501,)
)
async def adjusted_tb_route(work_item_id: UUID, ctx: Ctx, layer: Layer = "final") -> AdjustedTbOut:
    await _gate(ctx, work_item_id, "adjusted_tb.read")
    _not_yet()
