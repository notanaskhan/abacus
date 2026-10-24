"""Agent runs and screening results (TASK-011 design §6)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, FetchedValue, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    agent_id: Mapped[str]
    spec_version: Mapped[int]
    engagement_id: Mapped[UUID | None]  # None: a firm-level run (TASK-074 D1)
    methodology_version_id: Mapped[UUID | None]  # a firm-level run's template version
    evidence_version_id: Mapped[UUID | None]
    inbox_file_id: Mapped[UUID | None]  # SPEC-033 (TASK-066): a matcher run's file
    shadow: Mapped[bool] = mapped_column(server_default=FetchedValue())  # SPEC-036: never shown
    initiator_user_id: Mapped[UUID]
    source_event_id: Mapped[UUID | None]
    task_scope: Mapped[list[str]] = mapped_column(ARRAY(String))
    status: Mapped[str]
    context_hash: Mapped[str | None]
    output: Mapped[dict[str, object] | None] = mapped_column(JSONB)
    failure_code: Mapped[str | None]
    # Waiting for a work slot (SPEC-003 AC-13): the run is still `running`, reported as queued.
    queued_reason: Mapped[str | None]
    estimated_start_at: Mapped[datetime | None]
    started_at: Mapped[datetime]
    finished_at: Mapped[datetime | None]


class ScreeningResult(Base):
    """One agent run's proposal on one version (`subject_kind = 'version'`), or, since 0154, the
    code-composed aggregate of a request batch (`request_batch`, P-06-T20). The per-run columns
    are typed for `version` rows: every reader of them filters `subject_kind = 'version'`
    (`repository._version_rows()`); aggregates are read column by column (DEC-324)."""

    __tablename__ = "screening_results"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    agent_run_id: Mapped[UUID]
    action: Mapped[str]
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    rationale: Mapped[str]
    citations: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    unverified: Mapped[list[str]] = mapped_column(JSONB)
    created_by_kind: Mapped[str]
    created_at: Mapped[datetime]
    subject_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    # P-06-T20 (0154): the aggregate's columns, NULL on `version` rows.
    request_item_id: Mapped[UUID | None]
    batch_no: Mapped[int | None]
    source_result_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    source_review_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    evidence_version_ids: Mapped[list[UUID] | None] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    checks: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    file_flags: Mapped[list[dict[str, object]] | None] = mapped_column(JSONB)
    verdict: Mapped[str | None]
    supersedes_id: Mapped[UUID | None]


class ScreeningFeedback(Base):
    """A person's thumbs up or down on a screening aggregate (SHL-20 f; P-06-T20, 0154).
    Insert-only; a thumbs-down carries a reason; the note is sealed."""

    __tablename__ = "screening_feedback"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    screening_result_id: Mapped[UUID]
    user_id: Mapped[UUID]
    thumb: Mapped[str]
    reason_code: Mapped[str | None]
    note_sealed: Mapped[bytes | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class KnowledgeDocument(Base):
    """A firm's methodology document (SPEC-009). Text lives in its chunks."""

    __tablename__ = "knowledge_documents"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    title: Mapped[str]
    source_kind: Mapped[str]
    media_type: Mapped[str]
    fingerprint: Mapped[str]
    char_count: Mapped[int]
    status: Mapped[str]
    failure_code: Mapped[str | None]
    added_by: Mapped[UUID]
    created_at: Mapped[datetime]
    withdrawn_at: Mapped[datetime | None]


class KnowledgeChunk(Base):
    __tablename__ = "knowledge_chunks"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    document_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    heading_path: Mapped[str]
    text: Mapped[str]
    char_count: Mapped[int]
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024))
    embedding_model: Mapped[str | None]
    embedded_at: Mapped[datetime | None]


class EngagementAgentState(Base):
    """SPEC-027 (TASK-050): an engagement's agent paused or resumed (partner or manager)."""

    __tablename__ = "engagement_agents"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(primary_key=True)
    paused_at: Mapped[datetime | None]
    paused_by: Mapped[UUID | None]
    reason: Mapped[str | None]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # SPEC-027 AC-8 (TASK-051): set when the agent pauses itself (no active partner).
    self_paused_reason: Mapped[str | None]


class AgentActivity(Base):
    """SPEC-027 AC-7: one automatic action, by which policy and why. Insert-only; references
    only, never client content."""

    __tablename__ = "agent_activity"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    policy: Mapped[str]
    policy_version: Mapped[int]
    action: Mapped[str]
    outcome: Mapped[str]
    reason: Mapped[str | None]
    record_type: Mapped[str | None]
    record_id: Mapped[UUID | None]
    item_count: Mapped[int | None]
    for_user: Mapped[UUID | None]
    source_event_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class FollowUpSchedule(Base):
    """SPEC-027 P-4 (TASK-051): one reminder sent or drafted to one client contact."""

    __tablename__ = "follow_up_schedules"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    recipient_user_id: Mapped[UUID]
    status: Mapped[str]
    note: Mapped[str | None]
    agent_run_id: Mapped[UUID | None]
    decided_by: Mapped[UUID | None]
    decided_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # Follow-ups v2 (P-06-T14, migration 0121).
    binder_id: Mapped[UUID | None]
    recipient_contact_id: Mapped[UUID | None]
    kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    template_key: Mapped[str | None]
    body_sealed: Mapped[bytes | None]
    body_fingerprint: Mapped[str | None]
    edit_fingerprint: Mapped[str | None]
    drafted_by_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    sent_by: Mapped[UUID | None]
    sent_at: Mapped[datetime | None]
    not_before: Mapped[datetime | None]
    undone_at: Mapped[datetime | None]


class FollowUpReturn(Base):
    """A file a screening-return follow-up returns, with its reason (P-06-T14). Insert-only."""

    __tablename__ = "follow_up_returns"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    follow_up_id: Mapped[UUID] = mapped_column(primary_key=True)
    evidence_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    reason_code: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class FollowUpItem(Base):
    """An item a follow-up named, with its due date then and its place in the sequence (1-4)."""

    __tablename__ = "follow_up_items"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    follow_up_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    due_on: Mapped[date]
    sequence: Mapped[int]


class UploadReview(Base):
    """One upload reviewer run's review (SPEC-030; TASK-058). Insert-only."""

    __tablename__ = "upload_reviews"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    evidence_version_id: Mapped[UUID]
    agent_run_id: Mapped[UUID]
    prompt_ref: Mapped[str]
    document_kind: Mapped[str | None]
    no_concerns: Mapped[bool]
    truncated: Mapped[bool] = mapped_column(server_default=FetchedValue())
    created_by_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class UploadReviewFlag(Base):
    """A flag of an upload review, with code-verified citations (TASK-058). Insert-only."""

    __tablename__ = "upload_review_flags"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    review_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str]
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    rationale: Mapped[str]
    citations: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    shown: Mapped[bool]


class InboxMatchRun(Base):
    """One matcher run's proposals for an inbox file (SPEC-033; TASK-065). Insert-only."""

    __tablename__ = "inbox_match_runs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    inbox_file_id: Mapped[UUID]
    agent_run_id: Mapped[UUID]
    prompt_ref: Mapped[str]
    none_fit: Mapped[bool]
    truncated: Mapped[bool] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class InboxMatchProposal(Base):
    """A proposed request for an inbox file, with code-verified citations. Insert-only."""

    __tablename__ = "inbox_match_proposals"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    match_id: Mapped[UUID] = mapped_column(primary_key=True)
    rank: Mapped[int] = mapped_column(primary_key=True)
    request_item_id: Mapped[UUID]
    confidence: Mapped[Decimal] = mapped_column(Numeric(4, 3))
    rationale: Mapped[str]
    citations: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    shown: Mapped[bool]


class GuidanceDraftRow(Base):
    """One guidance drafter run's draft for a request item (SPEC-035; TASK-072). Insert-only."""

    __tablename__ = "guidance_drafts"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    request_item_id: Mapped[UUID]
    agent_run_id: Mapped[UUID]
    prompt_ref: Mapped[str]
    why: Mapped[str]
    good_looks_like: Mapped[str]
    effort: Mapped[str | None]
    effort_reason: Mapped[str | None]
    blocks_fieldwork: Mapped[bool | None]
    blocks_reason: Mapped[str | None]
    passed_checks: Mapped[bool]
    check_reasons: Mapped[list[str]] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class GuidanceDraftDecision(Base):
    """A person approved or discarded a guidance draft (SPEC-035; TASK-073). Insert-only."""

    __tablename__ = "guidance_draft_decisions"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    draft_id: Mapped[UUID] = mapped_column(primary_key=True)
    decision: Mapped[str]
    edited: Mapped[bool]
    confirmed_read: Mapped[bool]
    decided_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class TemplateGuidanceDraft(Base):
    """A guidance drafter run's draft for a template item (SPEC-035 Q3; TASK-074). Insert-only."""

    __tablename__ = "template_guidance_drafts"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    methodology_version_id: Mapped[UUID]
    position: Mapped[int]
    agent_run_id: Mapped[UUID]
    prompt_ref: Mapped[str]
    why: Mapped[str]
    good_looks_like: Mapped[str]
    effort: Mapped[str | None]
    effort_reason: Mapped[str | None]
    blocks_fieldwork: Mapped[bool | None]
    blocks_reason: Mapped[str | None]
    passed_checks: Mapped[bool]
    check_reasons: Mapped[list[str]] = mapped_column(ARRAY(String))
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class TemplateGuidanceDecision(Base):
    """A person approved (with the final text) or discarded a template draft (TASK-074).
    Insert-only; approved text reaches engagements through a new template version (D2)."""

    __tablename__ = "template_guidance_decisions"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    draft_id: Mapped[UUID] = mapped_column(primary_key=True)
    decision: Mapped[str]
    why: Mapped[str | None]
    good_looks_like: Mapped[str | None]
    effort: Mapped[str | None]
    blocks_fieldwork: Mapped[bool | None]
    edited: Mapped[bool]
    confirmed_read: Mapped[bool]
    decided_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class AgentStage(Base):
    """An agent's stage for the firm (SPEC-036; TASK-076): the newest row is the stage. Written
    only by the founder's operations command through the owner role (D1)."""

    __tablename__ = "agent_stages"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    agent_id: Mapped[str]
    stage: Mapped[str]
    changed_by: Mapped[str]
    note: Mapped[str]
    created_at: Mapped[datetime]


class EntryAssessmentRow(Base):
    """The entry assessor's proposal on a selected entry (SPEC-037 Q4; TASK-085). Insert-only."""

    __tablename__ = "entry_assessments"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    selected_item_id: Mapped[UUID]
    agent_run_id: Mapped[UUID]
    prompt_ref: Mapped[str]
    verdict: Mapped[str]
    shown_verdict: Mapped[str]
    rationale: Mapped[str]
    citations: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
