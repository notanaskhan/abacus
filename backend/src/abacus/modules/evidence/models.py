"""Evidence items and versions (glossary). TASK-009 design §4."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import FetchedValue, Float, Integer, Numeric
from sqlalchemy.dialects.postgresql import ARRAY, INT4RANGE, JSONB, Range
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class EvidenceItem(Base):
    __tablename__ = "evidence_items"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    # Nullable in the schema since 0270 (ADR-158): a client-scoped item has none. Every path
    # here creates and reads engagement-scoped items only; client-scoped ones are read through
    # the Files read model (N-01-T19), never through these engagement-filtered queries.
    engagement_id: Mapped[UUID]
    title: Mapped[str]
    created_by_kind: Mapped[str]
    created_by_id: Mapped[str]
    created_at: Mapped[datetime]
    # 0270: filled from the engagement by trigger when an insert leaves them out.
    client_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    work_item_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    scope: Mapped[str] = mapped_column(server_default=FetchedValue())
    folder_kind: Mapped[str] = mapped_column(server_default=FetchedValue())


class EvidenceVersion(Base):
    __tablename__ = "evidence_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_item_id: Mapped[UUID]
    version_no: Mapped[int]
    fingerprint: Mapped[str]
    storage_key: Mapped[str]
    storage_version_id: Mapped[str]
    size_bytes: Mapped[int]
    media_type: Mapped[str]
    source: Mapped[str]
    method: Mapped[str]
    pulled_at: Mapped[datetime | None]
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    client_entity_id: Mapped[UUID | None]
    snapshot_id: Mapped[UUID | None]
    idempotency_key: Mapped[str | None]
    created_at: Mapped[datetime]
    # SPEC-023: where a file the firm added for the client came from (written once).
    upload_note: Mapped[str | None]
    # ADR-162 §5 (P-06-T18, 0144): a client-channel upload's own object and detached key.
    storage_mode: Mapped[str] = mapped_column(server_default=FetchedValue())
    # 0270 (ADR-158): how it arrived (filled by trigger), what it supersedes, virtual splits
    # (a page range of a parent version, no new bytes), its display name and classification.
    channel: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    supersedes_version_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    parent_version_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    # N-01-T19: a virtual split's pages (no new bytes); with `parent_version_id` only.
    page_range: Mapped[Range[int] | None] = mapped_column(INT4RANGE, server_default=FetchedValue())
    virtual_label: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    virtual_amount: Mapped[Decimal | None] = mapped_column(server_default=FetchedValue())
    display_name: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    classification_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())


class EvidenceObjectKey(Base):
    """A detached-key version's wrapped data key (ADR-162 §5; P-06-T18). Acceptance stamps
    `retained_at` (one-way); only the withdrawal purge's definer function clears `wrapped_key`
    and stamps `destroyed_at`."""

    __tablename__ = "evidence_object_keys"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    key_id: Mapped[str]
    wrapped_key: Mapped[bytes | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    retained_at: Mapped[datetime | None]
    destroyed_at: Mapped[datetime | None]


class EvidenceVersionVoid(Base):
    """A version retired with the rule link a person voided (R-01 Story 2.2; 0159): evidence
    reads leave it out as they do a withdrawn one. Insert-only."""

    __tablename__ = "evidence_version_voids"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID]
    fulfilment_id: Mapped[UUID]
    voided_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class EvidenceWithdrawal(Base):
    """A client's withdrawal of an unaccepted upload (ADR-162 §4; P-06-T19). Insert-only but for
    the purge's stamps (`erased_at` once; `erase_blocked_at` and `block_reason` on each retry)."""

    __tablename__ = "evidence_withdrawals"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID | None]
    withdrawn_by_user_id: Mapped[UUID]
    withdrawn_at: Mapped[datetime]
    erase_after: Mapped[datetime]
    erased_at: Mapped[datetime | None]
    erase_blocked_at: Mapped[datetime | None]
    block_reason: Mapped[str | None]


class ReviewDecision(Base):
    """A person's accept, reject or send back of one evidence version (SPEC-004; ADR-005), or
    their Undo of one (`undone`, P-01-T13). Insert-only and immutable; the database refuses a
    non-human actor."""

    __tablename__ = "review_decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    decision: Mapped[str]
    reason_code: Mapped[str | None]
    note: Mapped[str | None]
    screening_result_id: Mapped[UUID | None]
    corrects_proposal: Mapped[bool]
    actor_kind: Mapped[str]
    actor_id: Mapped[str]
    created_at: Mapped[datetime]
    # P-01-T13 (0117): decisions are odd, undo rows even; the highest odd row is effective.
    decision_seq: Mapped[int]
    undoes_decision_id: Mapped[UUID | None]
    # What the decision changed, for its Undo: the version's assignee, each item's status.
    prior_assignee_user_id: Mapped[UUID | None]
    prior_item_statuses: Mapped[dict[str, str] | None] = mapped_column(JSONB)


class ReviewAssignment(Base):
    """Who has taken a queued version (advisory, SPEC-004 Q3); None once released."""

    __tablename__ = "review_assignments"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID]
    assignee_user_id: Mapped[UUID | None]
    assigned_by: Mapped[UUID]
    assigned_at: Mapped[datetime]


class InboxFile(Base):
    """A file dropped at the engagement level, waiting to be assigned to an item (SPEC-023)."""

    __tablename__ = "inbox_files"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    file_name: Mapped[str]
    media_type: Mapped[str]
    size_bytes: Mapped[int]
    fingerprint: Mapped[str]
    storage_key: Mapped[str]
    storage_version_id: Mapped[str]
    uploaded_by: Mapped[UUID]
    uploaded_by_staff: Mapped[bool]
    note: Mapped[str | None]
    status: Mapped[str]
    assigned_item_id: Mapped[UUID | None]
    assigned_version_id: Mapped[UUID | None]
    decided_by: Mapped[UUID | None]
    decided_at: Mapped[datetime | None]
    created_at: Mapped[datetime]
    # R-01-T09 (0153): a portal drop, waiting for the code-rule sort.
    channel: Mapped[str] = mapped_column(server_default=FetchedValue())
    drop_batch_id: Mapped[UUID | None]
    drop_binder_id: Mapped[UUID | None]
    drop_key: Mapped[str | None]
    duplicate_of_version_id: Mapped[UUID | None]
    sort_outcome: Mapped[str | None]


class UploadExtraction(Base):
    """What code read from an upload (SPEC-029; TASK-054): a derived record, insert-only."""

    __tablename__ = "upload_extractions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    inbox_file_id: Mapped[UUID | None]
    extractor_version: Mapped[str]
    status: Mapped[str]
    reason: Mapped[str | None]
    page_count: Mapped[int | None]
    truncated: Mapped[bool] = mapped_column(server_default=FetchedValue())
    storage_key: Mapped[str | None]
    storage_version_id: Mapped[str | None]
    fingerprint: Mapped[str | None]
    size_bytes: Mapped[int | None]
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    as_of: Mapped[date | None]
    entity_name: Mapped[str | None]
    account_last4: Mapped[str | None]
    opening: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    closing: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    credits: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    debits: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    grand_total: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class UploadCheck(Base):
    """One mechanical check or ledger cross-check of an upload (SPEC-029; TASK-055)."""

    __tablename__ = "upload_checks"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    checker_version: Mapped[str]
    document_kind: Mapped[str | None]
    check_code: Mapped[str]
    outcome: Mapped[str]
    audience: Mapped[str]
    reason: Mapped[str | None]
    expected_date: Mapped[date | None]
    found_date: Mapped[date | None]
    amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    difference: Mapped[Decimal | None] = mapped_column(Numeric(20, 2))
    account_code: Mapped[str | None]
    ref_item_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class UploadPreview(Base):
    """What the viewer shows for an upload (SPEC-029 goal 8; TASK-056). Insert-only."""

    __tablename__ = "upload_previews"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    inbox_file_id: Mapped[UUID | None]
    renderer_version: Mapped[str]
    kind: Mapped[str]
    reason: Mapped[str | None]
    page_count: Mapped[int] = mapped_column(server_default=FetchedValue())
    truncated: Mapped[bool] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # 0109 (P-03-T04): an unlock's derived preview, and the masker that burned its boxes. Only a
    # preview with `mask_version` set is a masked rendition (P-03-T09, T15).
    derivation_id: Mapped[UUID | None]
    mask_version: Mapped[str | None]


class UploadPreviewPage(Base):
    """One server-made PNG of a preview (TASK-056). Insert-only."""

    __tablename__ = "upload_preview_pages"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    preview_id: Mapped[UUID] = mapped_column(primary_key=True)
    page_no: Mapped[int] = mapped_column(primary_key=True)
    storage_key: Mapped[str]
    storage_version_id: Mapped[str]
    fingerprint: Mapped[str]
    size_bytes: Mapped[int]
    width: Mapped[int]
    height: Mapped[int]


class StatementDataset(Base):
    """An approved statement's transactions (SPEC-312; TASK-324). Insert-only."""

    __tablename__ = "statement_datasets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    format: Mapped[str]
    account_kind: Mapped[str]
    issuer: Mapped[str | None]
    last4: Mapped[str | None]
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    opening: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    closing: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    opening_source: Mapped[str]
    closing_source: Mapped[str]
    included_total: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    line_count: Mapped[int]
    excluded_count: Mapped[int]
    signs_flipped: Mapped[bool]
    field_sources: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    approved_by: Mapped[UUID]
    actor_kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class StatementTransaction(Base):
    __tablename__ = "statement_transactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    dataset_id: Mapped[UUID]
    position: Mapped[int]
    posted_on: Mapped[date | None]
    description: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    page: Mapped[int | None]
    excluded: Mapped[bool]
    exclusion_reason: Mapped[str | None]
    box: Mapped[list[float] | None] = mapped_column(ARRAY(Float(asdecimal=False)))  # TASK-334


class EvidencePage(Base):
    """One page of a version's (or inbox file's) word layer and its geometry (P-03-T04, T05).
    The words themselves are a sealed object in storage. Insert-only."""

    __tablename__ = "evidence_pages"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    inbox_file_id: Mapped[UUID | None]
    derivation_id: Mapped[UUID | None]
    page_no: Mapped[int]
    width_pt: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    height_pt: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    rotation: Mapped[int] = mapped_column(server_default=FetchedValue())
    has_text_layer: Mapped[bool]
    word_count: Mapped[int] = mapped_column(server_default=FetchedValue())
    text_layer_key: Mapped[str | None]
    text_layer_version_id: Mapped[str | None]
    text_layer_fingerprint: Mapped[str | None]
    text_layer_size: Mapped[int | None]  # 0119
    ocr_used: Mapped[bool] = mapped_column(server_default=FetchedValue())
    extractor_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Citation(Base):
    """A cited value, verified by code before anyone sees it (P-03-T04, T06; ADR-166). No quote
    text: only the hash of the words read from the layer. Insert-only."""

    __tablename__ = "citations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID | None]
    work_item_id: Mapped[UUID | None]
    client_id: Mapped[UUID | None]
    cited_from_type: Mapped[str]
    cited_from_id: Mapped[UUID]
    cited_from_ref: Mapped[str | None]
    cited_from_locator: Mapped[dict[str, Any] | None] = mapped_column(  # Any: JSON
        JSONB(none_as_null=True)
    )
    n: Mapped[int]
    kind: Mapped[str]
    source_type: Mapped[str]
    source_id: Mapped[UUID]
    source_version: Mapped[str | None]
    locator: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    match_id: Mapped[str | None]
    quote_sha256: Mapped[bytes | None]
    value_text: Mapped[str | None]
    verified: Mapped[bool]
    verification_reason: Mapped[str | None]
    verifier_version: Mapped[str]
    supersedes_id: Mapped[UUID | None]
    created_by_kind: Mapped[str]
    created_by_user_id: Mapped[UUID | None]
    created_by_run_id: Mapped[UUID | None]
    on_behalf_of_user_id: Mapped[UUID | None]
    # SPEC-036 AC-5 (0158): written by a shadow run, or succeeds one that was; never shown.
    shadow: Mapped[bool] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class CitationEvent(Base):
    """A citation moved, broke or was relinked (P-03-T04): its state is computed from these, the
    citation itself is never updated. Insert-only."""

    __tablename__ = "citation_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    citation_id: Mapped[UUID]
    kind: Mapped[str]
    cause_ref: Mapped[str | None]
    successor_citation_id: Mapped[UUID | None]
    actor_kind: Mapped[str]
    actor_user_id: Mapped[UUID | None]
    at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class EvidenceDerivation(Base):
    """What a password unlock derived from a protected file (P-03-T04, T19): the anchor of the
    derived word layer, PII scan and masked rendition. The evidence object is never touched.
    Insert-only; always a person (`created_by_user_id` NOT NULL)."""

    __tablename__ = "evidence_derivations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    kind: Mapped[str]
    created_by_user_id: Mapped[UUID]
    extractor_version: Mapped[str]
    renderer_version: Mapped[str]
    detector_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class PiiScanRun(Base):
    """Which pages of a source the PII detector scanned, and which it couldn't (P-03-T04, T13).
    Insert-only."""

    __tablename__ = "pii_scan_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    inbox_file_id: Mapped[UUID | None]
    derivation_id: Mapped[UUID | None]
    detector_version: Mapped[str]
    pages_scanned: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    pages_not_scannable: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    region_count: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class PiiRegion(Base):
    """Where a detected PII value sits on a page (P-03-T04, T13). Deliberately maps no
    `value_sealed`: nothing but the reveal service ever reads the sealed value (P-03 §4.2).
    Insert-only."""

    __tablename__ = "pii_regions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID | None]
    inbox_file_id: Mapped[UUID | None]
    derivation_id: Mapped[UUID | None]
    page_no: Mapped[int]
    bbox: Mapped[list[Decimal]] = mapped_column(ARRAY(Numeric(10, 2)))
    kind: Mapped[str]
    last4: Mapped[str | None]
    label_anchored: Mapped[bool]
    detector_version: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
