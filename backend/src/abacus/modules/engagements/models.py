"""Engagements (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class Engagement(Base):
    __tablename__ = "engagements"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    name: Mapped[str]
    type: Mapped[str]
    # F-03-T12 (0069): set by the database from the type; office and standards set to come.
    service_line: Mapped[str] = mapped_column(server_default=FetchedValue())
    office_id: Mapped[UUID | None]
    standards_set_id: Mapped[UUID | None]
    fiscal_period_start: Mapped[date]
    fiscal_period_end: Mapped[date]
    status: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]
    # The pinned methodology version (SPEC-008): set once, null until then.
    methodology_version_id: Mapped[UUID | None]
    # SPEC-025 (TASK-048): the engagement this one was rolled forward from, set at creation.
    prior_engagement_id: Mapped[UUID | None]
    # SPEC-036 (TASK-076): the engagement partner switched AI off for this engagement.
    ai_excluded_at: Mapped[datetime | None]
    ai_excluded_by: Mapped[UUID | None]
    ai_excluded_reason: Mapped[str | None]
    # P-07-T15 (0124): bumped by a trigger on any change; the wizard's label (P-07-T16).
    version: Mapped[int] = mapped_column(server_default=FetchedValue())
    period_label: Mapped[str | None] = mapped_column(server_default=FetchedValue())
    # TASK-1198 (0155): the reason code while on hold, cleared on resume.
    hold_reason: Mapped[str | None] = mapped_column(server_default=FetchedValue())


# --- Acceptance, independence and the letter (SPEC-025; TASK-044) ------------------------------


class EngagementAcceptance(Base):
    """One decision record; the newest row is the live one (rows are never changed)."""

    __tablename__ = "engagement_acceptance"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    kind: Mapped[str]
    decision: Mapped[str]
    decided_by: Mapped[str]
    documented_at: Mapped[str]
    predecessor_auditor: Mapped[str | None]
    predecessor_communicated_on: Mapped[date | None]
    independence_concluded_by: Mapped[str | None]
    independence_concluded_at: Mapped[datetime | None]
    independence_documented_at: Mapped[str | None]
    file_key: Mapped[str | None]
    file_version_id: Mapped[str | None]
    file_fingerprint: Mapped[str | None]
    file_size: Mapped[int | None]
    file_media_type: Mapped[str | None]
    file_name: Mapped[str | None]
    before_act_1: Mapped[bool] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # 0175 (DEC-429): true only on rows written before independence v2 (or outside the app);
    # SPEC-025's conclusion counts for G2 only there.
    legacy_g2: Mapped[bool] = mapped_column(server_default=FetchedValue())


class IndependenceConfirmation(Base):
    __tablename__ = "independence_confirmations"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID] = mapped_column(primary_key=True)
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    statement_version: Mapped[str | None]
    note: Mapped[str | None]
    before_act_1: Mapped[bool] = mapped_column(server_default=FetchedValue())
    requested_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    answered_at: Mapped[datetime | None]
    # P-07-T41 (0175): the statements ticked, sealed notes, reminders.
    statements: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    interests_note: Mapped[bytes | None]
    decline_note: Mapped[bytes | None]
    reminder_count: Mapped[int] = mapped_column(server_default=FetchedValue())
    last_reminded_at: Mapped[datetime | None]


class EngagementLetter(Base):
    __tablename__ = "engagement_letters"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    engagement_id: Mapped[UUID] = mapped_column(primary_key=True)
    status: Mapped[str]
    letter_date: Mapped[date | None]
    reason: Mapped[str | None]
    link: Mapped[str | None]
    file_key: Mapped[str | None]
    file_version_id: Mapped[str | None]
    file_fingerprint: Mapped[str | None]
    file_size: Mapped[int | None]
    file_media_type: Mapped[str | None]
    file_name: Mapped[str | None]
    recorded_by: Mapped[str]
    recorded_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # P-07-T15 (0124): the interim recorded letter (G3 until C7).
    client_signed_on: Mapped[date | None] = mapped_column(server_default=FetchedValue())
    firm_signed_on: Mapped[date | None] = mapped_column(server_default=FetchedValue())
    client_signer_contact_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    firm_signer_user_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    signed_copy_version_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())
    recorded_by_user_id: Mapped[UUID | None] = mapped_column(server_default=FetchedValue())


class WorkItem(Base):
    """A unit of work inside an engagement (F-03-T05; migration 0068)."""

    __tablename__ = "work_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    client_id: Mapped[UUID]
    client_entity_id: Mapped[UUID | None]
    kind: Mapped[str]
    name: Mapped[str]
    period_start: Mapped[date | None]
    period_end: Mapped[date | None]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    office_id: Mapped[UUID | None]
    due_on: Mapped[date | None]
    archived_at: Mapped[datetime | None]
    archive_locked_at: Mapped[datetime | None]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class AssuranceWorkItem(Base):
    """The assurance subtype of a work item (F-03-T05)."""

    __tablename__ = "assurance_work_items"

    work_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    assurance_type: Mapped[str]
    phase: Mapped[str] = mapped_column(server_default=FetchedValue())
    standards_set_id: Mapped[UUID | None]
    auto_mode: Mapped[bool] = mapped_column(server_default=FetchedValue())
    is_group_audit: Mapped[bool] = mapped_column(server_default=FetchedValue())
    # A-01-T05 (0134): the EBP profile facts and the record-mode phase stamps.
    ebp_plan_kind: Mapped[str | None]
    limited_scope_103a3c: Mapped[bool] = mapped_column(server_default=FetchedValue())
    phase_source: Mapped[str] = mapped_column(server_default=FetchedValue())
    phase_changed_at: Mapped[datetime | None]
    version: Mapped[int] = mapped_column(server_default=FetchedValue())
