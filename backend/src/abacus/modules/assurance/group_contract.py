"""The group-audit contract stubs, firm side (A-09-T03; SPEC-658 F1 to F6; DEC-5039).
Contracts: C9 v2.1 `docs/contracts/ledger-consolidation.md` (consolidations, structure, TB
attachments, consolidated TB by level and entity), C8 v1.1 (eliminations: `kind = elimination`,
`posting_target`, line entity and level) and `docs/contracts/group-audit.md` (components,
scoping, decision kinds, component auditors, instructions, deliverables).

`ledger` stays dependency-free (DEC-66), so `assurance` hosts these routes and calls the ledger
and adjustments services when they land (A-09-T13, T10). Every route has one matrix action and
answers, in order: a client principal 404; the action on the work item's engagement (walls 404,
independence 403); 404 without the firm's `group_audit` entitlement; then 501 naming its task.
The rollout flags `ledger.consolidation` and `assurance.group_audit` join the gate (A-09-T09,
T13): the capability `group_audit_on` is the entitlement and both flags.
Every figure is code's (ADR-050); nothing is ever posted to a client system (ADR-040).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Any, Final, Literal, cast
from uuid import UUID

from fastapi import Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._statuses import (
    ComponentDeliverableStatus,
    ComponentInstructionsStatus,
    ConsolidationLockStatus,
    ConsolidationStatus,
    ConsolidationTbStatus,
    EliminationEntryStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound, NotImplementedYet
from abacus.modules.adjustments.api import EliminationLine
from abacus.modules.engagements.api import get_ref, work_item_engagement
from abacus.modules.identity.api import AbacusRouter, AuthContext, authorise, current_context
from abacus.modules.ledger.api import CONSOLIDATION_ENGINE_VERSION, consolidation_facts
from abacus.modules.platform.api import group_audit_on

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
IfMatch = Annotated[str, Header(alias="If-Match", min_length=1, max_length=64)]
Money = Annotated[Decimal, classified("confidential")]
Firm = Annotated[Decimal, classified("confidential")]  # firm-confidential judgements (materiality)
Internal = classified("internal")
Label = Literal["standard", "interim", "prior", "budget", "preliminary"]
PlannedWork = Literal["full_scope", "specific_procedures", "analytical_only"]
ENTITLEMENT = "group_audit"


class TrialBalanceMissing(DomainConflict):
    code = "trial_balance_missing"


class UnbalancedEntry(DomainConflict):
    code = "unbalanced_entry"


class EntityAlreadyCovered(DomainConflict):
    code = "entity_already_covered"


class StructureInvalid(DomainInvalid):
    """A fourth tier, ownership other than 100%, or a currency other than USD (X-06)."""

    code = "structure_invalid"


class StructureSourceMissing(DomainConflict):
    """No OneWorld source on the consolidation, or none of its subsidiaries matches one of the
    client's entities under a single top entity: there is nothing to propose (DEC-5340)."""

    code = "structure_source_missing"


class ComponentPmInvalid(DomainInvalid):
    """A component PM at or above group PM, or on an Analytical-only component."""

    code = "component_pm_invalid"


# --- C9 v2.1 consolidation -----------------------------------------------------------------------


class ConsolidationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    year_end: Annotated[date, classified("confidential")]
    reporting_currency: Annotated[Literal["USD"], classified("internal")]
    interim_period_end: Annotated[date | None, classified("confidential")] = None
    prior_period_end: Annotated[date | None, classified("confidential")] = None
    source_connection_id: Annotated[UUID | None, classified("internal")] = None


class TrialBalanceSlotOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    label: Annotated[Label, Internal]
    period_kind: Annotated[Literal["current", "prior"], Internal]
    period_start: Annotated[date, Internal]
    period_end: Annotated[date, Internal]
    state: Annotated[ConsolidationTbStatus, Internal]
    file_name: Annotated[str | None, classified("confidential")]
    total_debits: Annotated[Money | None, classified("confidential")]
    not_needed_reason: Annotated[str | None, classified("confidential")]


class ConsolidationEntityOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    client_entity_id: Annotated[UUID, Internal]
    name: Annotated[str, classified("confidential")]
    level: Annotated[int, Field(ge=1, le=3), Internal]
    parent_id: Annotated[UUID | None, Internal]
    ownership_pct: Annotated[Decimal, Internal]  # always 100 (X-06)
    city: Annotated[str | None, classified("confidential")]
    component_auditor_name: Annotated[str | None, classified("confidential")]
    trial_balances: Annotated[list[TrialBalanceSlotOut], Internal]


class ConsolidationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    name: Annotated[str, classified("confidential")]
    status: Annotated[ConsolidationStatus, Internal]
    lock_state: Annotated[ConsolidationLockStatus, Internal]
    year_end: Annotated[date, Internal]
    reporting_currency: Annotated[Literal["USD"], Internal]
    interim_period_end: Annotated[date | None, Internal]
    prior_period_end: Annotated[date | None, Internal]
    entities: Annotated[list[ConsolidationEntityOut], Internal]
    tiers: Annotated[int, Internal]
    interim_total_debits: Money  # code's: 187,860,000
    all_balanced: Annotated[bool, Internal]
    missing: Annotated[list[str], Internal]  # the slots that block finalize, named
    finalized_by_name: Annotated[str | None, classified("confidential")]
    finalized_at: Annotated[datetime | None, Internal]
    row_version: Annotated[int, Internal]
    allowed_actions: Annotated[
        list[Literal["consolidation.edit", "consolidation.finalize", "consolidation.lock"]],
        classified("public"),
    ]


class StructureEntityIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    client_entity_id: Annotated[UUID, classified("internal")]
    parent_client_entity_id: Annotated[UUID | None, classified("internal")] = None
    level: Annotated[int, Field(ge=1, le=3), classified("internal")]
    ownership_pct: Annotated[Literal[100], classified("confidential")]
    city: Annotated[str | None, Field(max_length=120), classified("confidential")] = None
    component_auditor_id: Annotated[UUID | None, classified("internal")] = None


class StructureIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entities: Annotated[
        list[StructureEntityIn], Field(min_length=1, max_length=50), classified("confidential")
    ]


class TbAttachIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: Annotated[Literal["upload", "evidence", "connection"], classified("internal")]
    label: Annotated[Label, classified("confidential")]
    period_kind: Annotated[Literal["current", "prior"], classified("internal")]
    upload_id: Annotated[UUID | None, classified("internal")] = None
    evidence_version_id: Annotated[UUID | None, classified("internal")] = None
    connection_id: Annotated[UUID | None, classified("internal")] = None


class TbNotNeededIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]


class ConsolidationFinalizeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    seen_version: Annotated[int, Field(ge=1), classified("internal")]


class GroupReasonIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=1, max_length=500), classified("confidential")]


class GroupSuggestionRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    suggestion_id: Annotated[UUID, Internal]


class GroupRunRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    workflow_id: Annotated[str, Internal]


class TbCellOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    column: Annotated[str, Internal]  # an entity key, "eliminations" or "consolidated"
    amount: Money  # debits positive, credits negative
    elimination_codes: Annotated[list[str], Internal]  # tag chips, eliminations column only


class TbRowOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    caption: Annotated[str, classified("confidential")]
    section: Annotated[Literal["assets", "liabilities_equity", "income"], Internal]
    cells: Annotated[list[TbCellOut], Internal]


class GroupTalliesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    total_assets: Money
    net_income: Money
    balanced: Annotated[Literal["tie", "off", "pending"], Internal]
    off_by: Annotated[Money | None, classified("confidential")]
    intercompany: Annotated[Literal["tie", "off", "pending"], Internal]
    intercompany_off_by: Annotated[Money | None, classified("confidential")]
    eliminations_posted: Annotated[int, Internal]
    mapped: Annotated[int, Internal]
    accounts: Annotated[int, Internal]


class ConsolidatedTbOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    level: Annotated[int, Field(ge=1, le=2), Internal]
    view: Annotated[str, Internal]
    columns: Annotated[list[str], Internal]
    rows: Annotated[list[TbRowOut], Internal]
    tallies: Annotated[GroupTalliesOut, Internal]
    engine_version: Annotated[str, Internal]


# --- C8 v1.1 eliminations ------------------------------------------------------------------------


class EliminationLineOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    caption: Annotated[str, classified("confidential")]
    client_entity_id: Annotated[UUID | None, Internal]
    debit: Money
    credit: Money


class EliminationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    display_code: Annotated[str, Field(pattern=r"^E\d+[a-z]?$"), Internal]
    consolidation_level: Annotated[int, Field(ge=1, le=3), Internal]
    description: Annotated[str, classified("confidential")]
    status: Annotated[EliminationEntryStatus, Internal]
    posting_target: Annotated[Literal["consolidation_layer"], Internal]
    lines: Annotated[list[EliminationLineOut], Internal]
    total_debit: Money
    total_credit: Money
    off_by: Money  # code's; zero when balanced
    computation: Annotated[str | None, classified("confidential")]  # code's sentence
    citation_ids: Annotated[list[UUID], Internal]
    proposed_by_run_id: Annotated[UUID | None, Internal]
    approved_by_name: Annotated[str | None, classified("confidential")]
    posted_at: Annotated[datetime | None, Internal]


class EliminationsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[EliminationOut], Internal]
    total_debit: Money
    total_credit: Money


class EliminationLineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    caption: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    client_entity_id: Annotated[UUID, classified("internal")]
    debit: Annotated[
        Decimal, Field(ge=0, max_digits=20, decimal_places=2), classified("confidential")
    ] = Decimal(0)
    credit: Annotated[
        Decimal, Field(ge=0, max_digits=20, decimal_places=2), classified("confidential")
    ] = Decimal(0)


class EliminationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consolidation_level: Annotated[int, Field(ge=1, le=3), classified("internal")]
    description: Annotated[str, Field(min_length=1, max_length=300), classified("confidential")]
    lines: Annotated[
        list[EliminationLineIn], Field(min_length=2, max_length=50), classified("confidential")
    ]


class EliminationApproveItemsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: Annotated[list[UUID], Field(min_length=1, max_length=100), classified("internal")]


# --- group audit ---------------------------------------------------------------------------------


class GroupMaterialityOptionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    key: Annotated[str, Internal]
    benchmark: Annotated[str, Internal]
    base: Money
    rate_pct: Firm
    amount: Firm
    recommended: Annotated[bool, Internal]
    citation_ids: Annotated[list[UUID], Internal]


class GroupComponentOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    entity_name: Annotated[str, classified("confidential")]
    planned_work: Annotated[PlannedWork | None, Internal]
    scope_areas: Annotated[list[str], Internal]
    performed_by: Annotated[Literal["group_team", "component_auditor"], Internal]
    component_pm: Annotated[Firm | None, classified("confidential")]
    pm_pct_of_group: Annotated[Decimal | None, Internal]  # code's: 75 · 58 · 30 · 50
    suggestion_id: Annotated[UUID | None, Internal]


class GroupCoverageOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    measure: Annotated[Literal["third_party_sales", "total_assets"], Internal]
    total: Money
    full_scope: Money
    specific_procedures: Money
    full_scope_pct: Annotated[Decimal, Internal]
    specific_procedures_pct: Annotated[Decimal, Internal]


class GroupScopingOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_card_id: Annotated[UUID | None, Internal]
    decided: Annotated[bool, Internal]
    group_materiality: Annotated[Firm | None, classified("confidential")]
    performance_materiality: Annotated[Firm | None, classified("confidential")]
    clearly_trivial: Annotated[Firm | None, classified("confidential")]
    decided_by_name: Annotated[str | None, classified("confidential")]
    decided_at: Annotated[datetime | None, Internal]
    options: Annotated[list[GroupMaterialityOptionOut], Internal]
    components: Annotated[list[GroupComponentOut], Internal]
    component_pm_total: Firm
    coverage: Annotated[list[GroupCoverageOut], Internal]
    allowed_actions: Annotated[
        list[Literal["component.edit", "group_materiality.propose", "decision.decide"]],
        classified("public"),
    ]


class GroupComponentIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    planned_work: Annotated[PlannedWork, classified("internal")]
    scope_areas: Annotated[list[str], Field(max_length=20), classified("internal")] = []
    performed_by: Annotated[Literal["group_team", "component_auditor"], classified("internal")]
    component_pm: Annotated[
        Decimal | None, Field(ge=0, max_digits=20, decimal_places=2), classified("confidential")
    ] = None


class GroupDecisionCardOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision_card_id: Annotated[UUID, Internal]
    kind: Annotated[Literal["group_materiality", "make_reference"], Internal]


class ComponentAuditorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    organisation_name: Annotated[str, classified("confidential")]
    city: Annotated[str | None, classified("confidential")]
    component_id: Annotated[UUID, Internal]
    contact_name: Annotated[str | None, classified("confidential")]
    questionnaire_received_on: Annotated[date | None, Internal]
    competence_evaluated_at: Annotated[datetime | None, Internal]
    independence_confirmed_at: Annotated[datetime | None, Internal]
    peer_review_obtained_on: Annotated[date | None, Internal]
    make_reference: Annotated[bool, Internal]
    instructions_status: Annotated[ComponentInstructionsStatus | None, Internal]


class ComponentAuditorsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ComponentAuditorOut], Internal]


class ComponentAuditorIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organisation_name: Annotated[
        str, Field(min_length=1, max_length=200), classified("confidential")
    ]
    city: Annotated[str | None, Field(max_length=120), classified("confidential")] = None
    component_id: Annotated[UUID, classified("internal")]
    ep_contact_id: Annotated[UUID | None, classified("internal")] = None


class ComponentInstructionSectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: Annotated[int, Internal]
    title: Annotated[str, Internal]
    body: Annotated[str, classified("confidential")]
    needs_input: Annotated[bool, Internal]


class ComponentInstructionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    status: Annotated[ComponentInstructionsStatus, Internal]
    version_id: Annotated[UUID, Internal]
    sections: Annotated[list[ComponentInstructionSectionOut], Internal]
    provenance: Annotated[str, classified("confidential")]  # "Drafted by Omar Haddad via Agent"
    send_blocked_reason: Annotated[str | None, Internal]
    content_hash: Annotated[str, Internal]
    # A-09-T27 (DEC-5405): the pending send a 10-second Undo names (on the send's answer only).
    send_id: Annotated[UUID | None, Internal] = None


class ComponentInstructionsEditIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: Annotated[int, Field(ge=1, le=20), classified("internal")]
    body: Annotated[str, Field(min_length=1, max_length=20000), classified("confidential")]


class ComponentInstructionsSendIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recipient_contact_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]


class ComponentDeliverableOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    title: Annotated[str, classified("confidential")]
    due_on: Annotated[date, Internal]
    status: Annotated[ComponentDeliverableStatus, Internal]  # Late and Returned are derived
    days_late: Annotated[int | None, Internal]
    received_at: Annotated[datetime | None, Internal]
    reviewed_by_name: Annotated[str | None, classified("confidential")]
    return_reason: Annotated[str | None, classified("confidential")]


class ComponentDeliverablesOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[ComponentDeliverableOut], Internal]


class ComponentDeliverableIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: Annotated[str, Field(min_length=1, max_length=200), classified("confidential")]
    due_on: Annotated[date, classified("confidential")]


class DeliverableReturnIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Annotated[str, Field(min_length=1, max_length=1000), classified("confidential")]


# --- routes --------------------------------------------------------------------------------------

router = AbacusRouter(prefix="/v1", tags=["group-audit"])
_A = "/audits/{work_item_id}"
_C = f"{_A}/consolidations/{{consolidation_id}}"


async def _gate(ctx: AuthContext, work_item_id: UUID, action: str) -> None:
    if ctx.client:
        raise NotFound("group_audit")
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, action, ref.resource())
    if not await group_audit_on(ctx.tenant):
        raise NotFound(ENTITLEMENT)


async def _gate_record(ctx: AuthContext) -> None:
    """A record's own path: client 404 and the capability; the service authorises."""
    if ctx.client:
        raise NotFound("group_audit")
    if not await group_audit_on(ctx.tenant):
        raise NotFound(ENTITLEMENT)


def _todo(task: str) -> NotImplementedYet:
    return NotImplementedYet(task)


@router.post(
    f"{_A}/consolidations",
    action="consolidation.edit",
    response_model=ConsolidationOut,
    status_code=201,
    errors=(409, 501),
)
async def group_create_consolidation(
    work_item_id: UUID, body: ConsolidationIn, ctx: Ctx, _key: IdempotencyKey
) -> ConsolidationOut:
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_consolidation as svc

    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    return await svc.create(ctx, work_item_id, engagement_id, body, _key)


@router.get(_C, action="consolidation.read", response_model=ConsolidationOut, errors=(501,))
async def group_get_consolidation(
    work_item_id: UUID, consolidation_id: UUID, ctx: Ctx
) -> ConsolidationOut:
    await _gate(ctx, work_item_id, "consolidation.read")
    from abacus.modules.assurance import group_consolidation as svc

    return await svc.get(ctx, work_item_id, consolidation_id)


@router.patch(_C, action="consolidation.edit", response_model=ConsolidationOut, errors=(409, 501))
async def group_edit_consolidation(
    work_item_id: UUID, consolidation_id: UUID, body: ConsolidationIn, ctx: Ctx, _if: IfMatch
) -> ConsolidationOut:
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_consolidation as svc

    return await svc.edit(ctx, work_item_id, consolidation_id, body, _if)


@router.delete(_C, action="consolidation.edit", response_model=ConsolidationOut, errors=(409, 501))
async def group_discard_consolidation(
    work_item_id: UUID, consolidation_id: UUID, ctx: Ctx
) -> ConsolidationOut:
    """Discard a Draft: status `discarded`, audited, never a hard delete."""
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_consolidation as svc

    return await svc.discard(ctx, work_item_id, consolidation_id)


@router.put(
    f"{_C}/structure",
    action="consolidation.edit",
    response_model=ConsolidationOut,
    errors=(409, 501),
)
async def group_save_structure(
    work_item_id: UUID, consolidation_id: UUID, body: StructureIn, ctx: Ctx, _if: IfMatch
) -> ConsolidationOut:
    """422 `structure_invalid` for a fourth tier or ownership other than 100 (X-06)."""
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_consolidation as svc

    return await svc.save_structure(ctx, work_item_id, consolidation_id, body, _if)


@router.post(
    f"{_C}/structure/proposal",
    action="consolidation.edit",
    response_model=GroupSuggestionRefOut,
    status_code=201,
    errors=(409, 501),
)
async def group_propose_structure(
    work_item_id: UUID, consolidation_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> GroupSuggestionRefOut:
    """A deterministic P-35 suggestion (DV-2; DEC-5340); adopt through
    `POST /v1/suggestions/{id}/adopt` (Use structure), or PUT the structure (Edit). 409
    `structure_source_missing` without a OneWorld source or a single matched top entity."""
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_structure as svc

    return GroupSuggestionRefOut(
        suggestion_id=await svc.propose(ctx, work_item_id, consolidation_id)
    )


@router.post(
    f"{_C}/entities/{{entity_id}}/trial-balances",
    action="consolidation.edit",
    response_model=TrialBalanceSlotOut,
    status_code=201,
    errors=(409, 501),
)
async def group_attach_trial_balance(
    work_item_id: UUID,
    consolidation_id: UUID,
    entity_id: UUID,
    body: TbAttachIn,
    ctx: Ctx,
    _key: IdempotencyKey,
) -> TrialBalanceSlotOut:
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_consolidation as svc

    return await svc.attach(ctx, work_item_id, consolidation_id, entity_id, body)


@router.post(
    f"{_C}/trial-balances/{{tb_id}}/not-needed",
    action="consolidation.edit",
    response_model=TrialBalanceSlotOut,
    errors=(409, 501),
)
async def group_mark_not_needed(
    work_item_id: UUID, consolidation_id: UUID, tb_id: UUID, body: TbNotNeededIn, ctx: Ctx
) -> TrialBalanceSlotOut:
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_consolidation as svc

    return await svc.not_needed(ctx, work_item_id, consolidation_id, tb_id, body)


_BULK_MAX: Final = 20 * 1024 * 1024  # a NetSuite TB by subsidiary export


class BulkTooLarge(DomainInvalid):
    code = "upload_too_large"


@router.post(
    f"{_C}/bulk-upload",
    action="consolidation.edit",
    response_model=ConsolidationOut,
    errors=(409, 501),
)
async def group_bulk_upload(
    work_item_id: UUID, consolidation_id: UUID, request: Request, ctx: Ctx, _key: IdempotencyKey
) -> ConsolidationOut:
    """A NetSuite "TB by subsidiary" CSV split into one snapshot per covered entity (the raw
    body; 422 `subsidiary_unknown` naming the position of an unknown one, nothing stored)."""
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_consolidation as svc
    from abacus.modules.assurance import group_pull

    data = bytearray()
    async for chunk in request.stream():
        data += chunk
        if len(data) > _BULK_MAX:
            raise BulkTooLarge
    await group_pull.bulk_upload(ctx, work_item_id, consolidation_id, bytes(data))
    return await svc.get(ctx, work_item_id, consolidation_id)


@router.post(
    f"{_C}/pull-all",
    action="consolidation.edit",
    response_model=GroupRunRefOut,
    status_code=202,
    errors=(409, 501),
)
async def group_pull_all(
    work_item_id: UUID, consolidation_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> GroupRunRefOut:
    """`ConsolidationPullAll` (synthetic tenants until a live OneWorld connector exists, DV-1)."""
    await _gate(ctx, work_item_id, "consolidation.edit")
    from abacus.modules.assurance import group_pull

    return GroupRunRefOut(
        workflow_id=await group_pull.start_pull_all(ctx, work_item_id, consolidation_id)
    )


@router.post(
    f"{_C}/finalize",
    action="consolidation.finalize",
    response_model=ConsolidationOut,
    errors=(409, 501),
)
async def group_finalize(
    work_item_id: UUID,
    consolidation_id: UUID,
    body: ConsolidationFinalizeIn,
    ctx: Ctx,
    _key: IdempotencyKey,
) -> ConsolidationOut:
    """A manager's or EP's human act; 409 `trial_balance_missing` naming the slot."""
    await _gate(ctx, work_item_id, "consolidation.finalize")
    from abacus.modules.assurance import group_consolidation as svc

    return await svc.finalize(ctx, work_item_id, consolidation_id, body, _key)


@router.post(
    f"{_C}/lock", action="consolidation.lock", response_model=ConsolidationOut, errors=(409, 501)
)
async def group_lock(
    work_item_id: UUID, consolidation_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> ConsolidationOut:
    await _gate(ctx, work_item_id, "consolidation.lock")
    from abacus.modules.assurance import group_consolidation as svc
    from abacus.modules.assurance import group_tb

    await group_tb.lock(ctx, work_item_id, consolidation_id)
    return await svc.get(ctx, work_item_id, consolidation_id)


@router.post(
    f"{_C}/reopen", action="consolidation.lock", response_model=ConsolidationOut, errors=(409, 501)
)
async def group_reopen(
    work_item_id: UUID, consolidation_id: UUID, body: GroupReasonIn, ctx: Ctx, _key: IdempotencyKey
) -> ConsolidationOut:
    """With a reason; stales consolidation sign-offs and AUD-34's coverage facts (OQ-2)."""
    await _gate(ctx, work_item_id, "consolidation.lock")
    from abacus.modules.assurance import group_consolidation as svc
    from abacus.modules.assurance import group_tb

    await group_tb.reopen(ctx, work_item_id, consolidation_id, body.reason)
    return await svc.get(ctx, work_item_id, consolidation_id)


@router.get(
    f"{_C}/tb", action="consolidation.read", response_model=ConsolidatedTbOut, errors=(501,)
)
async def group_consolidated_tb(
    work_item_id: UUID,
    consolidation_id: UUID,
    ctx: Ctx,
    level: Annotated[int, Query(ge=1, le=2)] = 1,
    view: Annotated[str, Query(pattern=r"^(consolidated|entity:[0-9a-f-]{36})$")] = "consolidated",
) -> ConsolidatedTbOut:
    """Code's columns, ties, tallies and attribution; no browser arithmetic."""
    await _gate(ctx, work_item_id, "consolidation.read")
    from abacus.modules.assurance import group_tb

    found, mapped, accounts = await group_tb.levels(ctx, work_item_id, consolidation_id)
    lv = group_tb.level_of(found, level)
    columns = list(lv.columns)
    if view != "consolidated":  # one entity's column beside the consolidated
        entity = view.removeprefix("entity:")
        columns = [c for c in columns if c in (entity, "consolidated")]
    return ConsolidatedTbOut(
        level=level,
        view=view,
        columns=columns,
        rows=[
            TbRowOut(
                caption=r.caption,
                section=r.section,
                cells=[
                    TbCellOut(
                        column=c.column,
                        amount=group_tb.cell_amount(c.amount),
                        elimination_codes=list(c.elimination_codes),
                    )
                    for c in r.cells
                    if c.column in columns
                ],
            )
            for r in lv.rows
        ],
        tallies=GroupTalliesOut(
            total_assets=group_tb.cell_amount(lv.total_assets),
            net_income=group_tb.cell_amount(lv.net_income),
            balanced="tie" if lv.ties else "off",
            off_by=None
            if lv.ties
            else group_tb.cell_amount(sum(lv.column_totals.values(), Decimal(0))),
            intercompany="pending",
            intercompany_off_by=None,
            eliminations_posted=lv.eliminations_posted,
            mapped=mapped,
            accounts=accounts,
        ),
        engine_version=f"consolidation-{CONSOLIDATION_ENGINE_VERSION}",
    )


@router.get(
    f"{_C}/export.xlsx", action="consolidation.export", response_model=bytes, errors=(501,)
)
async def group_export_consolidation(
    work_item_id: UUID, consolidation_id: UUID, ctx: Ctx
) -> Response:
    await _gate(ctx, work_item_id, "consolidation.export")
    from abacus.modules.assurance import group_tb

    return Response(
        content=await group_tb.workbook(ctx, work_item_id, consolidation_id),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


_E = "/consolidations/{consolidation_id}/eliminations"


async def _engagement(ctx: AuthContext, work_item_id: UUID) -> UUID:
    engagement_id = await work_item_engagement(ctx.tenant, work_item_id)
    if engagement_id is None:
        raise NotFound("work_item")
    return engagement_id


async def _may(ctx: AuthContext, action: str, resource: object) -> bool:
    from abacus.modules.identity.api import Forbidden

    try:
        await authorise(ctx, action, resource)  # type: ignore[arg-type] -- a Resource
    except Forbidden:
        return False
    return True


async def _people(ctx: AuthContext, ids: list[UUID]) -> dict[UUID, str]:
    from abacus.modules.identity.api import names_of

    return dict(await names_of(ids)) if ids else {}


def _lines_in(body: EliminationIn) -> list[EliminationLine]:
    from abacus.modules.adjustments.api import eliminations as adj

    return [
        adj.EliminationLine(ln.caption, ln.client_entity_id, ln.debit, ln.credit)
        for ln in body.lines
    ]


def _elimination_out(v: object) -> EliminationOut:
    view = cast("Any", v)
    return EliminationOut(
        id=view.id,
        display_code=view.display_code,
        consolidation_level=view.level,
        description=view.description,
        status=view.status,
        posting_target="consolidation_layer",
        lines=[
            EliminationLineOut(
                caption=ln.caption,
                client_entity_id=ln.client_entity_id,
                debit=ln.debit,
                credit=ln.credit,
            )
            for ln in view.lines
        ],
        total_debit=view.total_debit,
        total_credit=view.total_credit,
        off_by=view.off_by,
        computation=None,
        citation_ids=[],
        proposed_by_run_id=None,
        approved_by_name=None,
        posted_at=None,
    )


def _eliminations_out(views: list[object]) -> EliminationsOut:
    items = [_elimination_out(v) for v in views]
    return EliminationsOut(
        items=items,
        total_debit=sum((i.total_debit for i in items), Decimal(0)),
        total_credit=sum((i.total_credit for i in items), Decimal(0)),
    )


async def _elimination_views(
    ctx: AuthContext, consolidation_id: UUID, action: str
) -> list[object]:
    """The consolidation's eliminations for someone allowed `action` on its engagement."""
    from abacus.modules.adjustments.api import eliminations as adj
    from abacus.modules.engagements.api import engagement_resource_of

    facts = await consolidation_facts(ctx.tenant, consolidation_id)
    await authorise(ctx, action, await engagement_resource_of(ctx.tenant, facts.engagement_id))
    return list(await adj.eliminations_of(ctx.tenant, consolidation_id))


@router.get(_E, action="elimination.read", response_model=EliminationsOut, errors=(501,))
async def group_list_eliminations(consolidation_id: UUID, ctx: Ctx) -> EliminationsOut:
    await _gate_record(ctx)
    views = await _elimination_views(ctx, consolidation_id, "elimination.read")
    return _eliminations_out(views)


@router.post(
    _E,
    action="elimination.edit",
    response_model=EliminationOut,
    status_code=201,
    errors=(409, 501),
)
async def group_create_elimination(
    consolidation_id: UUID, body: EliminationIn, ctx: Ctx, _key: IdempotencyKey
) -> EliminationOut:
    await _gate_record(ctx)
    from abacus.modules.adjustments.api import eliminations as adj

    facts = await consolidation_facts(ctx.tenant, consolidation_id)
    made = await adj.propose_elimination(
        ctx,
        engagement_id=facts.engagement_id,
        work_item_id=facts.work_item_id,
        consolidation_id=consolidation_id,
        level=body.consolidation_level,
        description=body.description,
        lines=_lines_in(body),
    )
    return _elimination_out(made)


@router.patch(
    "/proposed-entries/{entry_id}/elimination",
    action="elimination.edit",
    response_model=EliminationOut,
    errors=(409, 501),
)
async def group_edit_elimination(
    entry_id: UUID, body: EliminationIn, ctx: Ctx, _if: IfMatch
) -> EliminationOut:
    """Lines while Proposed; the server's "off n"."""
    await _gate_record(ctx)
    from abacus.modules.adjustments.api import eliminations as adj
    from abacus.modules.assurance.group_consolidation import seen_version

    return _elimination_out(
        await adj.edit_elimination(
            ctx,
            entry_id,
            level=body.consolidation_level,
            description=body.description,
            lines=_lines_in(body),
            seen_version=seen_version(_if),
        )
    )


@router.post(
    "/proposed-entries/{entry_id}/elimination/approve",
    action="elimination.approve",
    response_model=EliminationOut,
    errors=(409, 501),
)
async def group_approve_elimination(
    entry_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> EliminationOut:
    """409 `unbalanced_entry`; one human decision, never a policy actor (P-08)."""
    await _gate_record(ctx)
    from abacus.modules.adjustments.api import eliminations as adj

    return _elimination_out((await adj.approve(ctx, [entry_id]))[0])


@router.post(
    f"{_E}/approve",
    action="elimination.approve",
    response_model=EliminationsOut,
    errors=(409, 501),
)
async def group_approve_eliminations(
    consolidation_id: UUID, body: EliminationApproveItemsIn, ctx: Ctx, _key: IdempotencyKey
) -> EliminationsOut:
    """The per-item confirm list: one human decision per entry."""
    await _gate_record(ctx)
    from abacus.modules.adjustments.api import eliminations as adj

    await adj.approve(ctx, body.items)
    return _eliminations_out(await _elimination_views(ctx, consolidation_id, "elimination.read"))


@router.post(
    "/proposed-entries/{entry_id}/elimination/apply",
    action="elimination.apply",
    response_model=EliminationOut,
    errors=(409, 501),
)
async def group_apply_elimination(
    entry_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> EliminationOut:
    """`posting_target = consolidation_layer`; no entity snapshot or client ledger changes."""
    await _gate_record(ctx)
    from abacus.modules.adjustments.api import eliminations as adj

    return _elimination_out(await adj.post(ctx, entry_id))


@router.post(
    "/proposed-entries/{entry_id}/elimination/reject",
    action="elimination.approve",
    response_model=EliminationOut,
    errors=(409, 501),
)
async def group_reject_elimination(
    entry_id: UUID, body: GroupReasonIn, ctx: Ctx, _key: IdempotencyKey
) -> EliminationOut:
    await _gate_record(ctx)
    from abacus.modules.adjustments.api import eliminations as adj

    return _elimination_out(await adj.reject_elimination(ctx, entry_id, body.reason))


@router.post(
    f"{_E}/propose",
    action="elimination.propose_run",
    response_model=GroupRunRefOut,
    status_code=202,
    errors=(409, 501),
)
async def group_propose_eliminations(
    consolidation_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> GroupRunRefOut:
    """`EliminationProposal`: amounts by code, notes by the model, cells verified."""
    await _gate_record(ctx)
    raise _todo("A-09-T34")


@router.get(
    f"{_A}/group-scoping",
    action="group_scoping.read",
    response_model=GroupScopingOut,
    errors=(501,),
)
async def group_scoping(work_item_id: UUID, ctx: Ctx) -> GroupScopingOut:
    await _gate(ctx, work_item_id, "group_scoping.read")
    from abacus.modules.assurance import group_scoping as svc

    engagement_id = await _engagement(ctx, work_item_id)
    found = await svc.scoping(ctx, work_item_id, engagement_id)
    group_pm = None if found.decided is None else found.decided.pm
    resource = (await get_ref(ctx, engagement_id)).resource()
    allowed: list[Literal["component.edit", "group_materiality.propose", "decision.decide"]] = [
        a
        for a in ("component.edit", "group_materiality.propose", "decision.decide")
        if await _may(ctx, a, resource)
    ]
    names = await _people(ctx, [found.decided_by] if found.decided_by else [])
    return GroupScopingOut(
        decision_card_id=found.card_id,
        decided=found.decided is not None,
        group_materiality=None if found.decided is None else found.decided.materiality,
        performance_materiality=group_pm,
        clearly_trivial=None if found.decided is None else found.decided.ct,
        decided_by_name=names.get(found.decided_by) if found.decided_by else None,
        decided_at=found.decided_at,
        options=[
            GroupMaterialityOptionOut(
                key=key,
                benchmark=label,
                base=base,
                rate_pct=(t.materiality * 100 / base).quantize(Decimal("0.01"))
                if base
                else Decimal(0),
                amount=t.materiality,
                recommended=False,
                citation_ids=[],
            )
            for key, label, base, t in found.options
        ],
        components=[
            GroupComponentOut(
                id=c.id,
                entity_name=c.entity_name,
                planned_work=c.planned_work,
                scope_areas=list(c.scope_areas),
                performed_by=c.performed_by,
                component_pm=c.component_pm,
                pm_pct_of_group=(c.component_pm * 100 / group_pm).quantize(Decimal(1))
                if c.component_pm is not None and group_pm
                else None,
                suggestion_id=None,
            )
            for c in found.components
        ],
        component_pm_total=found.component_pm_total,
        coverage=[]
        if found.coverage is None
        else [
            GroupCoverageOut(
                measure="total_assets",
                total=found.coverage.total,
                full_scope=found.full_scope,
                specific_procedures=found.specific,
                full_scope_pct=(found.full_scope * 100 / found.coverage.total).quantize(Decimal(1))
                if found.coverage.total
                else Decimal(0),
                specific_procedures_pct=(found.specific * 100 / found.coverage.total).quantize(
                    Decimal(1)
                )
                if found.coverage.total
                else Decimal(0),
            )
        ],
        allowed_actions=allowed,
    )


@router.get(
    f"{_A}/group-scoping/export.xlsx",
    action="group_scoping.read",
    response_model=bytes,
    errors=(501,),
)
async def group_export_group_scoping(work_item_id: UUID, ctx: Ctx) -> Response:
    await _gate(ctx, work_item_id, "group_scoping.read")
    from abacus.modules.assurance import group_scoping as svc

    engagement_id = await _engagement(ctx, work_item_id)
    return Response(
        content=await svc.workbook(ctx, work_item_id, engagement_id),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.put(
    "/components/{component_id}",
    action="component.edit",
    response_model=GroupComponentOut,
    errors=(409, 501),
)
async def group_edit_component(
    component_id: UUID, body: GroupComponentIn, ctx: Ctx, _if: IfMatch
) -> GroupComponentOut:
    """422 `component_pm_invalid` at or above group PM or on an Analytical-only component."""
    await _gate_record(ctx)
    from abacus.modules.assurance import group_scoping as svc
    from abacus.modules.assurance.group_consolidation import seen_version

    c = await svc.edit_component(
        ctx,
        component_id,
        planned_work=body.planned_work,
        scope_areas=list(body.scope_areas),
        performed_by=body.performed_by,
        component_pm=body.component_pm,
        seen_version=seen_version(_if),
    )
    return GroupComponentOut(
        id=c.id,
        entity_name=c.entity_name,
        planned_work=c.planned_work,
        scope_areas=list(c.scope_areas),
        performed_by=c.performed_by,
        component_pm=c.component_pm,
        pm_pct_of_group=None,
        suggestion_id=None,
    )


@router.post(
    f"{_A}/decisions/group-materiality",
    action="group_materiality.propose",
    response_model=GroupDecisionCardOut,
    status_code=201,
    errors=(409, 501),
)
async def group_raise_group_materiality(
    work_item_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> GroupDecisionCardOut:
    """Raises the EP-reserved card; deciding is P-04's `decision.decide` (rationale, fresh MFA)."""
    await _gate(ctx, work_item_id, "group_materiality.propose")
    from abacus.modules.assurance import group_scoping as svc

    engagement_id = await _engagement(ctx, work_item_id)
    return GroupDecisionCardOut(
        decision_card_id=await svc.raise_card(ctx, work_item_id, engagement_id),
        kind="group_materiality",
    )


@router.get(
    f"{_A}/component-auditors",
    action="component_auditor.read",
    response_model=ComponentAuditorsOut,
    errors=(501,),
)
async def group_list_component_auditors(work_item_id: UUID, ctx: Ctx) -> ComponentAuditorsOut:
    await _gate(ctx, work_item_id, "component_auditor.read")
    from abacus.modules.assurance import component_auditors as ca

    return ComponentAuditorsOut(
        items=[_auditor_out(a) for a in await ca.auditors(ctx, work_item_id)]
    )


@router.post(
    f"{_A}/component-auditors",
    action="component_auditor.manage",
    response_model=ComponentAuditorOut,
    status_code=201,
    errors=(409, 501),
)
async def group_add_component_auditor(
    work_item_id: UUID, body: ComponentAuditorIn, ctx: Ctx, _key: IdempotencyKey
) -> ComponentAuditorOut:
    await _gate(ctx, work_item_id, "component_auditor.manage")
    from abacus.modules.assurance import component_auditors as ca

    return _auditor_out(
        await ca.add_auditor(
            ctx,
            work_item_id,
            organisation_name=body.organisation_name,
            city=body.city,
            component_id=body.component_id,
            ep_contact_id=body.ep_contact_id,
        )
    )


@router.post(
    "/component-auditors/{auditor_id}/instructions/draft",
    action="component_instructions.draft",
    response_model=ComponentInstructionsOut,
    status_code=201,
    errors=(409, 501),
)
async def group_draft_instructions(
    auditor_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> ComponentInstructionsOut:
    """The deterministic template merge on the person's behalf (DV-6)."""
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    return _instructions_out(await ca.draft_instructions(ctx, auditor_id))


@router.patch(
    "/component-instructions/{instructions_id}",
    action="component_instructions.edit",
    response_model=ComponentInstructionsOut,
    errors=(409, 501),
)
async def group_edit_instructions(
    instructions_id: UUID, body: ComponentInstructionsEditIn, ctx: Ctx, _if: IfMatch
) -> ComponentInstructionsOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca
    from abacus.modules.assurance.group_consolidation import seen_version

    return _instructions_out(
        await ca.edit_section(
            ctx,
            instructions_id,
            number=body.number,
            body=body.body,
            seen_version=seen_version(_if),
        )
    )


@router.post(
    "/component-instructions/{instructions_id}/send",
    action="component_instructions.send",
    response_model=ComponentInstructionsOut,
    errors=(409, 501),
)
async def group_send_instructions(
    instructions_id: UUID, body: ComponentInstructionsSendIn, ctx: Ctx, _key: IdempotencyKey
) -> ComponentInstructionsOut:
    """A person's send with a 10-second Undo; issues the `component_auditor` grant."""
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    view, _send = await ca.send_instructions(
        ctx,
        instructions_id,
        recipient_contact_id=body.recipient_contact_id,
        version_id=body.version_id,
    )
    return _instructions_out(view, send_id=_send)


@router.post(
    "/component-auditors/{auditor_id}/make-reference",
    action="component_auditor.manage",
    response_model=GroupDecisionCardOut,
    status_code=201,
    errors=(409, 501),
)
async def group_raise_make_reference(
    auditor_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> GroupDecisionCardOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    return GroupDecisionCardOut(
        decision_card_id=await ca.raise_make_reference(ctx, auditor_id), kind="make_reference"
    )


@router.get(
    "/component-auditors/{auditor_id}/deliverables",
    action="component_deliverable.read",
    response_model=ComponentDeliverablesOut,
    errors=(501,),
)
async def group_list_deliverables(auditor_id: UUID, ctx: Ctx) -> ComponentDeliverablesOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    return ComponentDeliverablesOut(
        items=[_deliverable_out(d) for d in await ca.deliverables(ctx, auditor_id)]
    )


@router.post(
    "/component-auditors/{auditor_id}/deliverables",
    action="component_deliverable.manage",
    response_model=ComponentDeliverableOut,
    status_code=201,
    errors=(409, 501),
)
async def group_add_deliverable(
    auditor_id: UUID, body: ComponentDeliverableIn, ctx: Ctx, _key: IdempotencyKey
) -> ComponentDeliverableOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    return _deliverable_out(
        await ca.request_deliverable(ctx, auditor_id, title=body.title, due_on=body.due_on)
    )


@router.post(
    "/component-deliverables/{deliverable_id}/review",
    action="component_deliverable.review",
    response_model=ComponentDeliverableOut,
    errors=(409, 501),
)
async def group_review_deliverable(
    deliverable_id: UUID, ctx: Ctx, _key: IdempotencyKey
) -> ComponentDeliverableOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    return _deliverable_out(await ca.review_deliverable(ctx, deliverable_id))


@router.post(
    "/component-deliverables/{deliverable_id}/return",
    action="component_deliverable.review",
    response_model=ComponentDeliverableOut,
    errors=(409, 501),
)
async def group_return_deliverable(
    deliverable_id: UUID, body: DeliverableReturnIn, ctx: Ctx, _key: IdempotencyKey
) -> ComponentDeliverableOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    return _deliverable_out(await ca.return_deliverable(ctx, deliverable_id, reason=body.reason))


class ComponentEvaluationIn(BaseModel):
    """A-09-T27 (DEC-5405): the evaluation facts a person records on AUD-35."""

    model_config = ConfigDict(extra="forbid")

    questionnaire_received_on: Annotated[date | None, classified("internal")] = None
    competence_evaluated: Annotated[bool, classified("internal")] = False
    independence_confirmed: Annotated[bool, classified("internal")] = False
    peer_review_obtained_on: Annotated[date | None, classified("internal")] = None


@router.patch(
    "/component-auditors/{auditor_id}/evaluation",
    action="component_auditor.manage",
    response_model=ComponentAuditorOut,
    errors=(409,),
)
async def group_evaluate_component_auditor(
    auditor_id: UUID, body: ComponentEvaluationIn, ctx: Ctx
) -> ComponentAuditorOut:
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    return _auditor_out(
        await ca.evaluate(
            ctx,
            auditor_id,
            questionnaire_received_on=body.questionnaire_received_on,
            competence_evaluated=body.competence_evaluated,
            independence_confirmed=body.independence_confirmed,
            peer_review_obtained_on=body.peer_review_obtained_on,
        )
    )


class SendUndoneOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    send_id: Annotated[UUID, Internal]
    undone: Annotated[bool, Internal]


@router.post(
    "/component-instruction-sends/{send_id}/undo",
    action="component_instructions.send",
    response_model=SendUndoneOut,
    errors=(409,),
)
async def group_undo_instructions_send(send_id: UUID, ctx: Ctx) -> SendUndoneOut:
    """The sender's Undo inside 10 seconds: nothing is sent (409 `undo_window_closed` after)."""
    await _gate_record(ctx)
    from abacus.modules.assurance import component_auditors as ca

    await ca.undo_send(ctx, send_id)
    return SendUndoneOut(send_id=send_id, undone=True)


def _auditor_out(a: object) -> ComponentAuditorOut:
    from abacus.modules.assurance.component_auditors import AuditorView

    v = cast(AuditorView, a)
    return ComponentAuditorOut(
        id=v.id,
        organisation_name=v.organisation_name,
        city=v.city,
        component_id=v.component_id,
        contact_name=v.contact_name,
        questionnaire_received_on=v.questionnaire_received_on,
        competence_evaluated_at=v.competence_evaluated_at,
        independence_confirmed_at=v.independence_confirmed_at,
        peer_review_obtained_on=v.peer_review_obtained_on,
        make_reference=v.make_reference,
        instructions_status=(
            None
            if v.instructions_status is None
            else ComponentInstructionsStatus(v.instructions_status)
        ),
    )


def _instructions_out(i: object, send_id: UUID | None = None) -> ComponentInstructionsOut:
    from abacus.modules.assurance.component_auditors import InstructionsView

    v = cast(InstructionsView, i)
    return ComponentInstructionsOut(
        id=v.id,
        status=ComponentInstructionsStatus(v.status),
        version_id=v.version_id,
        sections=[
            ComponentInstructionSectionOut(
                number=s.number, title=s.title, body=s.body, needs_input=s.needs_input
            )
            for s in v.sections
        ],
        provenance=v.provenance,
        send_blocked_reason=v.send_blocked_reason,
        content_hash=v.content_hash,
        send_id=send_id,
    )


def _deliverable_out(d: object) -> ComponentDeliverableOut:
    from abacus.modules.assurance.component_auditors import DeliverableView

    v = cast(DeliverableView, d)
    return ComponentDeliverableOut(
        id=v.id,
        title=v.title,
        due_on=v.due_on,
        # Late and Returned are derived: the stored word, with days_late / return_reason beside.
        status=ComponentDeliverableStatus(
            v.status if v.status in ("expected", "received", "reviewed") else "expected"
        ),
        days_late=v.days_late,
        received_at=v.received_at,
        reviewed_by_name=v.reviewed_by_name,
        return_reason=v.return_reason,
    )
