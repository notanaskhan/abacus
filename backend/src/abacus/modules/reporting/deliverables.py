"""C10's service seam (R-02-T02 stub; R-02 §3.5, §4.3; SPEC-646 AC-17 to AC-20). Contract:
`docs/contracts/deliverables.md`.

A provider publishes inside its own unit of work (A-07's ReleaseWorkflow under the EP's approval
grant, A-06's send-draft; later C-02 and X-01). One deliverable per `(source_module, source_ref)`
and one insert-only version per evidence version; a repeat with the same source version is a
no-op returning the same ids. Publishing is never flagged. The service lands with R-02-T09; until
then every call raises `NotImplementedYet`, so a consumer's own test can bind to the signature.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from abacus.kernel.db import TenantContext
from abacus.kernel.errors import DomainInvalid, NotImplementedYet
from abacus.kernel.uow import UnitOfWork

AudienceScope = Literal["client", "client_entity", "engagement", "work_item", "governance_room"]
ActorKind = Literal["human", "system"]
WithdrawReason = Literal["wrong_file", "reissued", "other"]
DeliveryState = Literal["not_opened", "delivered", "viewed", "downloaded"]


class DraftWithoutWatermark(DomainInvalid):
    """A draft version whose P-11 generated document carries no DRAFT watermark (AC-18)."""

    code = "draft_without_watermark"


@dataclass(frozen=True)
class DeliverableAudience:
    scope_kind: AudienceScope
    scope_id: UUID


@dataclass(frozen=True)
class DeliverableSpec:
    """One publish. `kind` is one of `portal.deliverables_contract.DeliverableKind`; the actor is
    a person, or the system on a person's behalf (`on_behalf_of_user_id` is then required)."""

    client_id: UUID
    kind: str
    title: str
    source_module: str
    source_ref: str
    evidence_version_id: UUID
    render_hash: str
    page_count: int
    audiences: Sequence[DeliverableAudience]
    published_by_user_id: UUID
    actor_kind: ActorKind = "human"
    on_behalf_of_user_id: UUID | None = None
    client_entity_id: UUID | None = None
    engagement_id: UUID | None = None
    work_item_id: UUID | None = None
    generated_document_id: UUID | None = None
    is_draft: bool = False
    page_comments: bool = False
    restricted_use: bool = False
    legend_kind: Literal["ar_c_70"] | None = None
    approval_kind: str | None = None
    approval_item_id: UUID | None = None


@dataclass(frozen=True)
class PublishedDeliverable:
    deliverable_id: UUID
    version_id: UUID
    version_no: int
    created: bool


@dataclass(frozen=True)
class AudienceReceipt:
    """Per audience contact: "Delivered", "Viewed Oct 9, 10:22 AM", "Downloaded" (AC-20)."""

    contact_id: UUID
    state: DeliveryState
    first_viewed_at: datetime | None = None
    first_downloaded_at: datetime | None = None
    download_count: int = 0


@dataclass(frozen=True)
class WorkItemDeliverable:
    deliverable_id: UUID
    kind: str
    title: str
    latest_version_no: int
    is_draft: bool
    receipts: Sequence[AudienceReceipt] = field(default_factory=tuple)


@dataclass(frozen=True)
class ExpectedDeliverable:
    """POR-09's Coming next, from C1's client-visible milestones."""

    label: str
    expected_on: date | None = None


async def publish_deliverable(tx: UnitOfWork, spec: DeliverableSpec) -> PublishedDeliverable:
    raise NotImplementedYet


async def supersede_deliverable(
    tx: UnitOfWork, deliverable_id: UUID, spec: DeliverableSpec
) -> PublishedDeliverable:
    raise NotImplementedYet


async def withdraw_deliverable(
    tx: UnitOfWork,
    version_id: UUID,
    reason: WithdrawReason,
    actor_user_id: UUID,
    note: str | None = None,
) -> None:
    raise NotImplementedYet


async def deliverables_for_work_item(
    tenant: TenantContext, work_item_id: UUID
) -> list[WorkItemDeliverable]:
    raise NotImplementedYet


async def expected_deliverables(
    tenant: TenantContext, work_item_id: UUID
) -> list[ExpectedDeliverable]:
    raise NotImplementedYet
