"""C18's slot: one way to put a decision to a client (R-02-T03 stub; R-02 §3.1; SPEC-646 AC-1 to
AC-7). Contract: `docs/contracts/portal-approvals.md`.

A module registers a kind with `register_client_approval_kind(kind, provider)`. Engagements never
imports the provider. An unregistered kind fails closed: every route for it answers 409
`approval_kind_not_registered` and nothing is written (chapter 03 §2.4).

Only `modules/portal/approvals.py` and each provider's record-mode service may call a provider's
`decide()` (CLIENT-DECISION-001, R-02-T04). Every provider receives `ClientDecisionContext`, so its
audit row reads "Dana Kowalski (client) · Sep 25", never "via Agent" (INV-5, DEC-60).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Annotated, ClassVar, Final, Literal, Protocol, cast, get_args
from uuid import UUID

from abacus.kernel.classification import classified
from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainConflict, DomainForbidden
from abacus.kernel.uow import (
    DomainEvent,
    Ref,
    Scope,
    Target,
    UnitOfWork,
    audit_of_targets,
    uow,
)
from abacus.kernel.uow.relay import OutboxEvent

ClientApprovalKind = Literal[
    "proposed_entry", "uncorrected_misstatements", "fs_draft", "fs_package"
]
ClientDecisionWord = Literal["accept", "decline", "approve", "acknowledge"]
DeclineReason = Literal["number_looks_wrong", "something_missing", "other"]
ClientApprovalState = Literal[
    "waiting", "approved", "declined", "accepted", "not_recorded", "acknowledged", "question_sent"
]
DesignationBasis = Literal["owner", "approver_of_record", "ske_designee"]
CLIENT_APPROVAL_KINDS: Final = frozenset(get_args(ClientApprovalKind))


@dataclass(frozen=True)
class DeciderRule:
    """Who may decide a kind (DEC-63; OQ-1, DEC-2400). `any_of` is one of an owner grant or the
    approver-of-record designation; `attest_also` is what an attest-flagged client's decider must
    hold on top (P-13). Anyone else in scope gets 403 `not_decider`; out of scope, 404."""

    any_of: frozenset[DesignationBasis]
    attest_also: frozenset[DesignationBasis] = frozenset()


_OWNER_OR_AOR: Final = frozenset[DesignationBasis]({"owner", "approver_of_record"})
DECIDER_RULES: Final[Mapping[ClientApprovalKind, DeciderRule]] = {
    "proposed_entry": DeciderRule(_OWNER_OR_AOR),
    "uncorrected_misstatements": DeciderRule(_OWNER_OR_AOR),
    "fs_draft": DeciderRule(_OWNER_OR_AOR),
    "fs_package": DeciderRule(_OWNER_OR_AOR, frozenset[DesignationBasis]({"ske_designee"})),
}


class ApprovalKindNotRegistered(DomainConflict):
    """No provider is registered for this kind (AC-1): nothing is written."""

    code = "approval_kind_not_registered"


class ItemChanged(DomainConflict):
    """The decide call's `seen_hash` is not the item's current one (AC-4): reload."""

    code = "item_changed"


class NotDecider(DomainForbidden):
    """In scope, but not this kind's decider (AC-2)."""

    code = "not_decider"


@dataclass(frozen=True)
class ClientDecisionContext:
    """Attribution for every provider (AC-6). A client human with a live grant, always."""

    contact_id: UUID
    user_id: UUID
    grant_id: UUID
    designation_basis: DesignationBasis
    mfa_verified_at: datetime
    session_id: UUID
    channel: Literal["portal"] = "portal"
    ip: str | None = None
    device: str | None = None


@dataclass(frozen=True)
class ClientDecision:
    decision: ClientDecisionWord
    seen_hash: str
    reason_code: DeclineReason | None = None
    note: str | None = None


@dataclass(frozen=True)
class ApprovalLine:
    account: str
    debit: Decimal | None = None
    credit: Decimal | None = None


@dataclass(frozen=True)
class ApprovalItem:
    """What a provider reports. `sent_to_client` false hides the item from the portal (AC-1)."""

    kind: ClientApprovalKind
    item_id: UUID
    scope_kind: str
    scope_id: UUID
    sent_to_client: bool
    title: str
    state: ClientApprovalState
    seen_hash: str
    amount: Decimal | None = None
    lines: Sequence[ApprovalLine] = field(default_factory=tuple)
    legend: str | None = None
    highlights: str | None = None
    highlights_approved_by: str | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    reason_code: DeclineReason | None = None


@dataclass(frozen=True)
class ApprovalFacts:
    """A provider's facts for the decider rule."""

    attest_client: bool
    work_item_id: UUID | None = None


class ClientApprovalProvider(Protocol):
    """A kind's owner. It emits `client_approval.requested` when an item is sent and
    `client_approval.decided` after `decide()`, and its decision row is human-only."""

    async def items(self, tenant: TenantContext, scope_id: UUID) -> Sequence[ApprovalItem]: ...

    async def item(self, tenant: TenantContext, item_id: UUID) -> ApprovalItem | None: ...

    async def decide(
        self,
        tx: UnitOfWork,
        item_id: UUID,
        decision: ClientDecision,
        context: ClientDecisionContext,
    ) -> ApprovalItem: ...

    async def facts(self, tenant: TenantContext, item_id: UUID) -> ApprovalFacts: ...


_PROVIDERS: dict[str, ClientApprovalProvider] = {}


def register_client_approval_kind(
    kind: ClientApprovalKind, provider: ClientApprovalProvider
) -> None:
    if kind not in CLIENT_APPROVAL_KINDS:
        raise ValueError(f"client approval kind {kind!r} is unknown")
    if kind in _PROVIDERS and _PROVIDERS[kind] is not provider:
        raise ValueError(f"client approval kind {kind!r} is already registered")
    _PROVIDERS[kind] = provider


def client_approval_kinds() -> frozenset[str]:
    """The kinds registered right now."""
    return frozenset(_PROVIDERS)


def client_approval_provider(kind: str) -> ClientApprovalProvider:
    """Fail closed (AC-1): an unknown or unregistered kind answers 409."""
    provider = _PROVIDERS.get(kind)
    if provider is None:
        raise ApprovalKindNotRegistered(kind)
    return provider


# --- R-02-T07: the C18 events and A-06's delivery adapter ------------------------------------


class ClientApprovalRequested(DomainEvent):
    """C18's `client_approval.requested` (R-02 §4.6): an item is now before the client. Every
    provider emits it when an item is sent; identifiers only."""

    event_type: ClassVar[str] = "client_approval.requested"

    kind: Annotated[ClientApprovalKind, classified("internal")]
    item_id: Annotated[UUID, classified("internal")]
    scope_kind: Annotated[str, classified("internal")]
    scope_id: Annotated[UUID, classified("internal")]


class ClientApprovalDecided(DomainEvent):
    """C18's `client_approval.decided` (R-02 §4.6), after a provider's `decide()`."""

    event_type: ClassVar[str] = "client_approval.decided"

    kind: Annotated[ClientApprovalKind, classified("internal")]
    item_id: Annotated[UUID, classified("internal")]
    decision: Annotated[ClientDecisionWord, classified("internal")]


_DELIVERED: Final = "client_approval.requested"
_BATCH: Final = "approval_batch"


async def deliver_proposed_entries(tenant: TenantContext, event: OutboxEvent) -> None:
    """A-06's C18 port (`adjustments.register_client_delivery`): the send's grant was consumed
    after its 10-second Undo window, so each entry is now before the client on its work item.
    At-least-once safe: a batch already delivered (its audit event exists) emits nothing again."""
    batch_id = UUID(str(event.payload["approval_batch_id"]))
    work_item_id = UUID(str(event.payload["work_item_id"]))
    engagement_id = UUID(str(event.payload["engagement_id"]))
    entry_ids = [UUID(str(e)) for e in cast(list[object], event.payload["entry_ids"])]
    async with uow(tenant) as tx:
        seen = await audit_of_targets(tx.session, [(_BATCH, batch_id)], None, 1, action=_DELIVERED)
        if seen:
            return
        for entry_id in entry_ids:
            tx.emit(
                ClientApprovalRequested(
                    kind="proposed_entry",
                    item_id=entry_id,
                    scope_kind="work_item",
                    scope_id=work_item_id,
                )
            )
        tx.record(
            _DELIVERED,
            target=Target(_BATCH, batch_id),
            after=Ref(entries=len(entry_ids)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
