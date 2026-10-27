"""Review grammar records (P-04; ADR-136). First table: sign-offs (SPEC-308; TASK-319)."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class SignOff(Base):
    """L1 preparer to L5 EQR on a registered reviewable, with the content hash signed.
    Insert-only; staleness is computed against the target's current hash."""

    __tablename__ = "sign_offs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    target_type: Mapped[str]
    target_id: Mapped[UUID]
    level: Mapped[int]
    content_hash: Mapped[str]
    signed_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # P-04-T03 (migration 0093): what was true at signing, written by P-04-T18's service.
    kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    work_item_id: Mapped[UUID | None]
    initials: Mapped[str | None]
    engagement_role_at_sign: Mapped[str | None]
    function_at_sign: Mapped[str | None]
    version_no: Mapped[int | None]
    statement_version: Mapped[str | None]
    adopted_run_id: Mapped[UUID | None]
    independence_checked_at: Mapped[datetime | None]
    bulk_request_id: Mapped[UUID | None]  # P-04-T22: the bulk request that wrote it


class ReviewableNote(Base):
    """A review note on a registered reviewable (SPEC-313; TASK-331). Insert-only."""

    __tablename__ = "reviewable_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    target_type: Mapped[str]
    target_id: Mapped[UUID]
    anchor: Mapped[str | None]
    # SPEC-313 rows hold `body`; from P-04-T21 (migration 0210) a note holds `body_sealed`.
    body: Mapped[str | None]
    raised_by: Mapped[UUID]
    # P-04-T03 (migration 0093; ADR-160 clause 6): authoritative, written with each event.
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    assignee_user_id: Mapped[UUID | None]
    anchor_ref: Mapped[dict[str, str] | None] = mapped_column(JSONB)
    body_sealed: Mapped[bytes | None]


class ReviewableNoteEvent(Base):
    __tablename__ = "reviewable_note_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    note_id: Mapped[UUID]
    kind: Mapped[str]
    body: Mapped[str | None]
    by_user: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    body_sealed: Mapped[bytes | None]  # P-04-T21 (migration 0210)


class HumanGate(Base):
    """What waits on a person (P-04-T03 table, T16 projector; C13). A rebuildable projection of
    owners' domain events: the projector writes `state` and `updated_at` only."""

    __tablename__ = "human_gates"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    kind: Mapped[str]
    subject_ref: Mapped[dict[str, str]] = mapped_column(JSONB)
    engagement_id: Mapped[UUID | None]
    work_item_id: Mapped[UUID | None]
    client_id: Mapped[UUID | None]
    assignee_user_id: Mapped[UUID | None]
    role: Mapped[str | None]
    due_on: Mapped[date | None]
    state: Mapped[str] = mapped_column(server_default=FetchedValue())
    source_event_id: Mapped[UUID]
    updated_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # I-01-T04 (migration 0223): the owner's registered name and what Home sorts and bands on.
    subkind: Mapped[str]
    office_id: Mapped[UUID | None]
    blocked: Mapped[bool] = mapped_column(server_default=FetchedValue())
    blocked_reason_code: Mapped[str | None]
    sort_hint: Mapped[int | None]


class HumanGateSnooze(Base):
    """A person's snooze of a gate, for them alone (I-01-T04, 0223). Insert-only: the latest row
    per (gate, person) wins; an unsnooze is a row whose `until` is the moment it was written."""

    __tablename__ = "human_gate_snoozes"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    gate_id: Mapped[UUID]
    user_id: Mapped[UUID]
    until: Mapped[datetime]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    actor_kind: Mapped[str]
    actor_id: Mapped[str]


class HumanGateReassignment(Base):
    """Who moved a gate from whom to whom (I-01-T04, 0223). Insert-only and a person's alone."""

    __tablename__ = "human_gate_reassignments"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    gate_id: Mapped[UUID]
    subject_ref: Mapped[dict[str, str]] = mapped_column(JSONB)
    from_user_id: Mapped[UUID | None]
    to_user_id: Mapped[UUID]
    reason_code: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    actor_kind: Mapped[str]
    actor_id: Mapped[str]


class DecisionCard(Base):
    """One question reserved to a role (P-04-T04 table, T23 service; ADR-160 clause 8). Only
    `status` changes; a new card supersedes the last."""

    __tablename__ = "decision_cards"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID | None]
    kind: Mapped[str]
    version_no: Mapped[int]
    question_key: Mapped[str]
    reserved_role: Mapped[str]
    reserved_user_id: Mapped[UUID | None]
    options: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    context: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    factors: Mapped[list[dict[str, object]]] = mapped_column(JSONB)
    recommendation_suggestion_id: Mapped[UUID | None]
    blocking_refs: Mapped[list[dict[str, str]]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    supersedes_id: Mapped[UUID | None]
    raised_by_kind: Mapped[str]
    raised_by_id: Mapped[str]
    run_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Decision(Base):
    """The one decision on a card: insert-only and human-only; the rationale is sealed."""

    __tablename__ = "decisions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    card_id: Mapped[UUID]
    option_key: Mapped[str]
    rationale_sealed: Mapped[bytes]
    factors: Mapped[list[str]] = mapped_column(JSONB)
    seen_card_version: Mapped[int]
    decided_by: Mapped[UUID]
    mfa_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class DecisionCardVersion(Base):
    """A card's numbered history (P-04-T23, migration 0211): proposed, decided, reassessed."""

    __tablename__ = "decision_card_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    card_id: Mapped[UUID]
    version_no: Mapped[int]
    event: Mapped[str]
    option_key: Mapped[str | None]
    changed: Mapped[bool | None]
    figures: Mapped[dict[str, str]] = mapped_column(JSONB)
    decision_id: Mapped[UUID | None]
    superseded_by_card_id: Mapped[UUID | None]
    actor_user_id: Mapped[UUID | None]
    actor_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class DecisionAnalysisRequest(Base):
    """ "Request more analysis" on a card (P-04-T23): a person's, sealed."""

    __tablename__ = "decision_analysis_requests"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    card_id: Mapped[UUID]
    text_sealed: Mapped[bytes]
    requested_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class FieldValueVersion(Base):
    """A field's version (0093; written only through `review.api.record_value`). Mapped for
    reads; the write is `field_values.record_value`'s."""

    __tablename__ = "field_value_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID | None]
    target_type: Mapped[str]
    target_id: Mapped[UUID]
    field_key: Mapped[str]
    seq: Mapped[int]
