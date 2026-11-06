"""C18 Portal approvals, the routes (R-02-T03 stub; R-02 §4.3; SPEC-646 AC-1 to AC-16). Contract:
`docs/contracts/portal-approvals.md`; screens POR-08 and POR-09 a2, b.

Every route answers, in order: the matrix action (client people only, `scope_only`; firm roles,
agents, system and support are denied); 409 `approval_kind_not_registered` for a kind no provider
registered (the slot, `engagements.client_approval_provider`); 501 until R-02-T11 and T15. The
flag `portal.approvals` arrives with R-02-T14.

Pack rule (AC-7): no field is named or holds materiality, a threshold, a policy name, "within
threshold", a review note, a sign-off, the agent, a confidence or an internal status; the schema
scan fails the build if one appears. Decline notes and questions are hostile client text (AC-34).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.engagements.api import (
    ClientApprovalKind,
    ClientApprovalState,
    DeclineReason,
    client_approval_provider,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member

# A portal person themself, never a break-glass support context.
Member = Annotated[AuthContext, Depends(current_member)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")
Money = Annotated[Decimal, Field(max_digits=20, decimal_places=2), Confidential]

KindParam = Annotated[str, Path(max_length=40)]
ApprovalFilter = Literal["waiting", "posted", "approved", "declined"]
ApprovalAction = Literal["accept", "decline", "approve", "acknowledge", "ask"]
SeenHash = Annotated[str, Field(min_length=1, max_length=128), Internal]
Reason = Annotated[str, Field(min_length=1, max_length=1000), Restricted]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class ApprovalLineOut(BaseModel):
    model_config = _frozen()

    account: Annotated[str, Confidential]
    debit: Money | None = None
    credit: Money | None = None


class ApprovalSupportOut(BaseModel):
    """A read-only preview chip; the bytes come through the portal's document routes."""

    model_config = _frozen()

    label: Annotated[str, Confidential]
    document_id: Annotated[UUID | None, Internal] = None


class ApprovalPartOut(BaseModel):
    model_config = _frozen()

    label: Annotated[str, Confidential]
    deliverable_id: Annotated[UUID | None, Internal] = None


class ApprovalItemOut(BaseModel):
    """One card. Amounts come from the provider; the browser computes nothing (ADR-050)."""

    model_config = _frozen()

    kind: Annotated[ClientApprovalKind, Internal]
    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    state: Annotated[ClientApprovalState, Internal]
    amount: Money | None = None
    decided_by: Annotated[str | None, Confidential] = None
    decided_at: Annotated[datetime | None, Internal] = None
    reason_code: Annotated[DeclineReason | None, Internal] = None
    question_sent_at: Annotated[datetime | None, Internal] = None
    allowed_actions: Annotated[list[ApprovalAction], Internal]


class ApprovalItemDetailOut(ApprovalItemOut):
    """Detail. `highlights` are verbatim as the partner approved them (P-25); `seen_hash` covers
    amounts, lines, legend and highlights (AC-4)."""

    seen_hash: SeenHash
    lines: Annotated[list[ApprovalLineOut], Confidential]
    parts: Annotated[list[ApprovalPartOut], Confidential] = Field(
        default_factory=list[ApprovalPartOut]
    )
    support: Annotated[list[ApprovalSupportOut], Confidential] = Field(
        default_factory=list[ApprovalSupportOut]
    )
    legend: Annotated[str | None, Confidential] = None
    highlights: Annotated[str | None, Confidential] = None
    reason: Annotated[str | None, Restricted] = None


class ApprovalCountsOut(BaseModel):
    model_config = _frozen()

    waiting: Annotated[int, Internal]
    posted: Annotated[int, Internal]
    approved: Annotated[int, Internal]
    declined: Annotated[int, Internal]


class ApprovalContextOut(BaseModel):
    """A period (`2026-08`) or an engagement the picker offers."""

    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]
    state: Annotated[ClientApprovalState | None, Internal] = None


class ApprovalsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[ApprovalItemOut], Confidential]
    counts: Annotated[ApprovalCountsOut, Internal]
    contexts: Annotated[list[ApprovalContextOut], Confidential]


class ProposedEntryDecideIn(BaseModel):
    model_config = _strict()

    decision: Annotated[Literal["accept", "decline"], Internal]
    seen_hash: SeenHash
    reason: Reason | None = None


class ApprovalAcknowledgeIn(BaseModel):
    model_config = _strict()

    seen_hash: SeenHash


class PackageDecideIn(BaseModel):
    """`other` requires a note (AC-14)."""

    model_config = _strict()

    decision: Annotated[Literal["approve", "decline"], Internal]
    seen_hash: SeenHash
    reason_code: Annotated[DeclineReason | None, Internal] = None
    note: Reason | None = None


class ApprovalQuestionIn(BaseModel):
    model_config = _strict()

    body: Annotated[str, Field(min_length=1, max_length=4000), Restricted]


class ApprovalQuestionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    author: Annotated[str, Confidential]
    body: Annotated[str, Restricted]
    created_at: Annotated[datetime, Internal]


class ApprovalQuestionsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[ApprovalQuestionOut], Restricted]


class EntriesJournalOut(BaseModel):
    """202 while the deterministic journal renders (C11); the route then answers 302."""

    model_config = _frozen()

    render_job_id: Annotated[UUID, Internal]


approvals_router = AbacusRouter(prefix="/v1/portal/approvals", tags=["portal approvals"])


def _not_yet() -> NoReturn:
    raise NotImplementedYet


def _registered(kind: str) -> None:
    client_approval_provider(kind)


@approvals_router.get(
    "", action="client_approval.read", response_model=ApprovalsOut, errors=(501,)
)
async def list_approvals_route(
    ctx: Member,
    scope_id: Annotated[UUID | None, Query()] = None,
    context: Annotated[str | None, Query(max_length=40)] = None,
    filter: Annotated[ApprovalFilter | None, Query()] = None,
) -> ApprovalsOut:
    """POR-08: items whose provider reports `sent_to_client`, for scopes the grant covers."""
    _not_yet()


@approvals_router.post(
    "/proposed-entries/{entry_id}/decide",
    action="proposed_entry.client_decide",
    response_model=ApprovalItemDetailOut,
    errors=(409, 501),
)
async def decide_proposed_entry_route(
    entry_id: UUID, body: ProposedEntryDecideIn, ctx: Member, idempotency_key: IdempotencyKey
) -> ApprovalItemDetailOut:
    """POR-08 e: `adjustments.api.apply_client_decision`. Provider wired with R-02-T07."""
    _not_yet()


@approvals_router.post(
    "/uncorrected-misstatements/{item_id}/acknowledge",
    action="uncorrected_misstatements.acknowledge",
    response_model=ApprovalItemDetailOut,
    errors=(409, 501),
)
async def acknowledge_uncorrected_route(
    item_id: UUID, body: ApprovalAcknowledgeIn, ctx: Member, idempotency_key: IdempotencyKey
) -> ApprovalItemDetailOut:
    """POR-08 e2: one insert-only, human-only row per snapshot and contact (AC-12)."""
    _not_yet()


@approvals_router.post(
    "/packages/{package_id}/decide",
    action="close_package.client_decide",
    response_model=ApprovalItemDetailOut,
    errors=(409, 501),
)
async def decide_package_route(
    package_id: UUID, body: PackageDecideIn, ctx: Member, idempotency_key: IdempotencyKey
) -> ApprovalItemDetailOut:
    """POR-08 a to c. 409 `approval_kind_not_registered` until C-02 or A-08 registers it."""
    _registered("fs_package")
    _not_yet()


@approvals_router.get(
    "/{kind}/{item_id}",
    action="client_approval.read",
    response_model=ApprovalItemDetailOut,
    errors=(409, 501),
)
async def get_approval_route(kind: KindParam, item_id: UUID, ctx: Member) -> ApprovalItemDetailOut:
    _registered(kind)
    _not_yet()


@approvals_router.get(
    "/{kind}/{item_id}/questions",
    action="client_approval.ask",
    response_model=ApprovalQuestionsOut,
    errors=(409, 501),
)
async def list_approval_questions_route(
    kind: KindParam, item_id: UUID, ctx: Member
) -> ApprovalQuestionsOut:
    _registered(kind)
    _not_yet()


@approvals_router.post(
    "/{kind}/{item_id}/questions",
    action="client_approval.ask",
    response_model=ApprovalQuestionOut,
    status_code=201,
    errors=(409, 501),
)
async def ask_about_item_route(
    kind: KindParam,
    item_id: UUID,
    body: ApprovalQuestionIn,
    ctx: Member,
    idempotency_key: IdempotencyKey,
) -> ApprovalQuestionOut:
    """A client-authored comment on the item's thread (AC-31; R-02-T22)."""
    _registered(kind)
    _not_yet()


@approvals_router.get(
    "/{kind}/{item_id}/journal",
    action="client_approval.read",
    response_model=EntriesJournalOut,
    status_code=202,
    errors=(409, 501),
)
async def entries_journal_route(kind: KindParam, item_id: UUID, ctx: Member) -> EntriesJournalOut:
    """ "Download entries": 202 `{render_job_id}`, then 302 to a signed URL."""
    _registered(kind)
    _not_yet()
