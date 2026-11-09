"""C18 Portal approvals, the routes (R-02-T03 stub; R-02 §4.3; SPEC-646 AC-1 to AC-16). Contract:
`docs/contracts/portal-approvals.md`; screens POR-08 and POR-09 a2, b.

Every route answers, in order: the matrix action (client people only, `scope_only`; firm roles,
agents, system and support are denied); 409 `approval_kind_not_registered` for a kind no provider
registered (the slot, `engagements.client_approval_provider`); then C18's service
(`portal/approvals.py`, R-02-T11): list, detail and the decide routes. Questions (R-02-T22) and
the entries journal (C11) still answer 501. The flag `portal.approvals` arrives with R-02-T14.

Pack rule (AC-7): no field is named or holds materiality, a threshold, a policy name, "within
threshold", a review note, a sign-off, the agent, a confidence or an internal status; the schema
scan fails the build if one appears. Decline notes and questions are hostile client text (AC-34).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal, NoReturn, Self
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel._flags import PORTAL_APPROVALS
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.modules.engagements.api import (
    ApprovalItem,
    ClientApprovalKind,
    ClientApprovalState,
    ClientDecision,
    DeclineReason,
    client_approval_provider,
)
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member
from abacus.modules.portal import approvals as service

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
    debit: Annotated[Money | None, Confidential] = None
    credit: Annotated[Money | None, Confidential] = None


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
    amount: Annotated[Money | None, Confidential] = None
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
    reason: Annotated[Reason | None, Restricted] = None

    @model_validator(mode="after")
    def _a_decline_says_why(self) -> Self:
        if self.decision == "decline" and self.reason is None:
            raise ValueError("a decline needs a reason")
        return self


class ApprovalAcknowledgeIn(BaseModel):
    model_config = _strict()

    seen_hash: SeenHash


class PackageDecideIn(BaseModel):
    """`other` requires a note (AC-14)."""

    model_config = _strict()

    decision: Annotated[Literal["approve", "decline"], Internal]
    seen_hash: SeenHash
    reason_code: Annotated[DeclineReason | None, Internal] = None
    note: Annotated[Reason | None, Restricted] = None

    @model_validator(mode="after")
    def _a_decline_says_why(self) -> Self:
        if self.decision == "decline" and self.reason_code is None:
            raise ValueError("a decline needs a reason")
        if self.reason_code == "other" and self.note is None:
            raise ValueError("`other` needs a note")
        return self


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


async def _flag_on(ctx: AuthContext, flag: Flag) -> None:
    """R-02-T14 (DEC-3112): a firm whose flag is off serves none of these (404); the matrix's
    `scope_only` and the grant checks run in the services behind each route."""
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


def _registered(kind: str) -> None:
    client_approval_provider(kind)


def _out(shown: service.Shown) -> ApprovalItemOut:
    i = shown.item
    return ApprovalItemOut(
        kind=i.kind,
        id=i.item_id,
        title=i.title,
        state=i.state,
        amount=i.amount,
        decided_by=i.decided_by,
        decided_at=i.decided_at,
        reason_code=i.reason_code,
        allowed_actions=list(shown.actions),
    )


def _detail(
    i: ApprovalItem, actions: tuple[service.ApprovalAction, ...] = ("ask",)
) -> ApprovalItemDetailOut:
    return ApprovalItemDetailOut(
        kind=i.kind,
        id=i.item_id,
        title=i.title,
        state=i.state,
        amount=i.amount,
        decided_by=i.decided_by,
        decided_at=i.decided_at,
        reason_code=i.reason_code,
        allowed_actions=list(actions),
        seen_hash=i.seen_hash,
        lines=[
            ApprovalLineOut(account=line.account, debit=line.debit, credit=line.credit)
            for line in i.lines
        ],
        legend=i.legend,
        highlights=i.highlights,
    )


@approvals_router.get("", action="client_approval.read", response_model=ApprovalsOut)
async def list_approvals_route(
    ctx: Member,
    scope_id: Annotated[UUID | None, Query()] = None,
    context: Annotated[str | None, Query(max_length=40)] = None,
    filter: Annotated[ApprovalFilter | None, Query()] = None,
) -> ApprovalsOut:
    """POR-08: items whose provider reports `sent_to_client`, for scopes the grant covers."""
    await _flag_on(ctx, PORTAL_APPROVALS)
    del context  # the period picker's contexts arrive with the close kinds (C-02)
    listing = await service.approvals(ctx, scope_id, filter)
    return ApprovalsOut(
        items=[_out(s) for s in listing.items],
        counts=ApprovalCountsOut(**listing.counts),
        contexts=[],
    )


@approvals_router.post(
    "/proposed-entries/{entry_id}/decide",
    action="proposed_entry.client_decide",
    response_model=ApprovalItemDetailOut,
    errors=(409,),
)
async def decide_proposed_entry_route(
    entry_id: UUID, body: ProposedEntryDecideIn, ctx: Member, idempotency_key: IdempotencyKey
) -> ApprovalItemDetailOut:
    """POR-08 e: through C18's service to `adjustments.api.apply_client_decision`."""
    await _flag_on(ctx, PORTAL_APPROVALS)
    decided = await service.client_decide(
        ctx,
        "proposed_entry",
        entry_id,
        ClientDecision(
            body.decision,
            body.seen_hash,
            "other" if body.decision == "decline" else None,
            body.reason,
        ),
        action="proposed_entry.client_decide",
        idempotency_key=idempotency_key,
    )
    return _detail(decided)


@approvals_router.post(
    "/uncorrected-misstatements/{item_id}/acknowledge",
    action="uncorrected_misstatements.acknowledge",
    response_model=ApprovalItemDetailOut,
    errors=(409,),
)
async def acknowledge_uncorrected_route(
    item_id: UUID, body: ApprovalAcknowledgeIn, ctx: Member, idempotency_key: IdempotencyKey
) -> ApprovalItemDetailOut:
    """POR-08 e2: one insert-only, human-only row per snapshot and contact (AC-12); 409 until
    assurance registers the kind (R-02-T15)."""
    await _flag_on(ctx, PORTAL_APPROVALS)
    _registered("uncorrected_misstatements")
    decided = await service.client_decide(
        ctx,
        "uncorrected_misstatements",
        item_id,
        ClientDecision("acknowledge", body.seen_hash),
        action="uncorrected_misstatements.acknowledge",
        idempotency_key=idempotency_key,
    )
    return _detail(decided)


@approvals_router.post(
    "/packages/{package_id}/decide",
    action="close_package.client_decide",
    response_model=ApprovalItemDetailOut,
    errors=(409,),
)
async def decide_package_route(
    package_id: UUID, body: PackageDecideIn, ctx: Member, idempotency_key: IdempotencyKey
) -> ApprovalItemDetailOut:
    """POR-08 a to c. 409 `approval_kind_not_registered` until C-02 or A-08 registers it."""
    await _flag_on(ctx, PORTAL_APPROVALS)
    _registered("fs_package")
    decided = await service.client_decide(
        ctx,
        "fs_package",
        package_id,
        ClientDecision(body.decision, body.seen_hash, body.reason_code, body.note),
        action="close_package.client_decide",
        idempotency_key=idempotency_key,
    )
    return _detail(decided)


@approvals_router.get(
    "/{kind}/{item_id}",
    action="client_approval.read",
    response_model=ApprovalItemDetailOut,
    errors=(409,),
)
async def get_approval_route(kind: KindParam, item_id: UUID, ctx: Member) -> ApprovalItemDetailOut:
    await _flag_on(ctx, PORTAL_APPROVALS)
    _registered(kind)
    shown = await service.approval(ctx, kind, item_id)
    return _detail(shown.item, shown.actions)


@approvals_router.get(
    "/{kind}/{item_id}/questions",
    action="client_approval.ask",
    response_model=ApprovalQuestionsOut,
    errors=(409, 501),
)
async def list_approval_questions_route(
    kind: KindParam, item_id: UUID, ctx: Member
) -> ApprovalQuestionsOut:
    await _flag_on(ctx, PORTAL_APPROVALS)
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
    await _flag_on(ctx, PORTAL_APPROVALS)
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
    await _flag_on(ctx, PORTAL_APPROVALS)
    _registered(kind)
    _not_yet()
