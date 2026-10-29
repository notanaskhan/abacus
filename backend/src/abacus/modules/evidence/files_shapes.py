"""Files browser v1 shapes (N-01-T02 stubs, N-01-T19 live; N-01 §4.3; ADR-158; FIL-01).
Contract: `docs/contracts/files-browser.md`. The routes are `files_contract`'s; the read model that
fills these is `files`'.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from abacus.kernel._statuses import FileDocumentStatus
from abacus.kernel.classification import classified
from abacus.kernel.listing import ListPage
from abacus.modules.engagements.api import MaskedTinOut

NodeKind = Literal["client", "permanent_file", "year", "work_item", "folder"]
FolderKind = Literal[
    "source_documents", "workpapers", "correspondence", "deliverables", "signed_authorizations"
]
Channel = Literal[
    "portal",
    "email",
    "firm_upload",
    "retrieval",
    "import",
    "mobile",
    "internal_handoff",
    "generated",
    "confirmation_response",
]
LinkKind = Literal["request", "workpaper_cell", "return_line", "notice", "envelope"]


class TreeNode(BaseModel):
    """One tree row: client > permanent file or year > work item > folder."""

    model_config = ConfigDict(frozen=True)

    ref: Annotated[str, classified("internal")]
    kind: Annotated[NodeKind, classified("internal")]
    label: Annotated[str, classified("confidential")]
    folder_kind: Annotated[FolderKind | None, classified("internal")]
    count: Annotated[int, classified("internal")]
    has_children: Annotated[bool, classified("internal")]
    on_hold: Annotated[bool, classified("internal")]
    locked: Annotated[bool, classified("internal")]
    children: Annotated[list[TreeNode], classified("internal")]


class FileTreeOut(BaseModel):
    """`GET /v1/files/tree`: only clients the viewer's teams and walls allow."""

    model_config = ConfigDict(frozen=True)

    nodes: Annotated[list[TreeNode], classified("internal")]


class VirtualChild(BaseModel):
    """A virtual split of a combined PDF: a page range with a label and an amount, no new bytes."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("confidential")]
    first_page: Annotated[int, classified("internal")]
    last_page: Annotated[int, classified("internal")]
    amount: Annotated[Decimal | None, classified("confidential")]


class FileRow(BaseModel):
    """One list row of a folder."""

    model_config = ConfigDict(frozen=True)

    evidence_item_id: Annotated[UUID, classified("internal")]
    version_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    classification_label: Annotated[str | None, classified("internal")]
    channel: Annotated[Channel | None, classified("internal")]
    status: Annotated[FileDocumentStatus, classified("internal")]
    superseded_by_name: Annotated[str | None, classified("confidential")]
    superseded_on: Annotated[date | None, classified("internal")]
    supports: Annotated[str | None, classified("confidential")]
    received_at: Annotated[datetime, classified("internal")]
    virtual_children: Annotated[list[VirtualChild], classified("internal")]


class FolderItemsOut(ListPage[FileRow]):
    """`GET /v1/files/folders/{folder_ref}/items`, with the folder's count line."""

    documents: Annotated[int, classified("internal")]
    virtual: Annotated[int, classified("internal")]


class TieOut(BaseModel):
    """Virtual documents' total against a mapped TB account; computed by code (ADR-050, DV-13)."""

    model_config = ConfigDict(frozen=True)

    total: Annotated[Decimal, classified("confidential")]
    account_number: Annotated[str | None, classified("internal")]
    ties: Annotated[bool | None, classified("internal")]


class LinkOut(BaseModel):
    """What the document supports, as a deep link."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[LinkKind, classified("internal")]
    label: Annotated[str, classified("confidential")]
    route: Annotated[str, classified("internal")]


class FileVersionOut(BaseModel):
    """One version of the document; earlier versions stay (ADR-004)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version_no: Annotated[int, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    channel: Annotated[Channel | None, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    superseded: Annotated[bool, classified("internal")]


class RetentionOut(BaseModel):
    """The retention policy, eligible date and any legal hold (read only)."""

    model_config = ConfigDict(frozen=True)

    policy_label: Annotated[str | None, classified("internal")]
    eligible_on: Annotated[date | None, classified("internal")]
    hold_label: Annotated[str | None, classified("internal")]
    hold_placed_by: Annotated[str | None, classified("internal")]
    hold_placed_on: Annotated[date | None, classified("internal")]


class SignOffSlotOut(BaseModel):
    """A P or R slot, read only in N-01."""

    model_config = ConfigDict(frozen=True)

    level: Annotated[Literal["preparer", "reviewer"], classified("internal")]
    initials: Annotated[str | None, classified("internal")]
    signed_at: Annotated[datetime | None, classified("internal")]


class DrawerOut(BaseModel):
    """`GET /v1/evidence-items/{id}/drawer` (O2); content fields null without `evidence.read`."""

    model_config = ConfigDict(frozen=True)

    evidence_item_id: Annotated[UUID, classified("internal")]
    display_name: Annotated[str, classified("confidential")]
    status: Annotated[FileDocumentStatus, classified("internal")]
    folder_kind: Annotated[FolderKind, classified("internal")]
    scope: Annotated[Literal["client", "engagement"], classified("internal")]
    page_count: Annotated[int | None, classified("internal")]
    size_bytes: Annotated[int, classified("internal")]
    fingerprint: Annotated[str, classified("internal")]
    masked_tin: Annotated[
        MaskedTinOut | None, classified("restricted")
    ]  # P-12: kind and last four
    thumbnail_ref: Annotated[str | None, classified("internal")]
    virtual_children: Annotated[list[VirtualChild], classified("internal")]
    tie: Annotated[TieOut | None, classified("internal")]
    linked_to: Annotated[list[LinkOut], classified("internal")]
    versions: Annotated[list[FileVersionOut], classified("internal")]
    retention: Annotated[RetentionOut, classified("internal")]
    sign_off_slots: Annotated[list[SignOffSlotOut], classified("internal")]
    client_access: Annotated[Literal["off", "view", "view_download"], classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class AccessLogRow(BaseModel):
    """One audit event targeting the item's versions, in the actor grammar."""

    model_config = ConfigDict(frozen=True)

    occurred_at: Annotated[datetime, classified("internal")]
    actor_display: Annotated[str, classified("internal")]
    verb: Annotated[str, classified("internal")]
    version_no: Annotated[int | None, classified("internal")]
