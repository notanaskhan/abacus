"""Fieldwork records (SPEC-037; TASK-083; ADR-131, ADR-132)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ARRAY, FetchedValue, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class EngagementMateriality(Base):
    __tablename__ = "engagement_materiality"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    overall: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    performance: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    trivial: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    benchmark: Mapped[str]
    set_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class FieldworkSettings(Base):
    __tablename__ = "fieldwork_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    settings: Mapped[dict[str, object]] = mapped_column(JSONB)
    set_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Procedure(Base):
    __tablename__ = "procedures"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    definition: Mapped[str]
    definition_version: Mapped[int]
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB)
    status: Mapped[str]
    failure_code: Mapped[str | None]
    started_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class PopulationRow(Base):
    __tablename__ = "populations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    procedure_id: Mapped[UUID]
    gl_snapshot_id: Mapped[UUID]
    rule_version: Mapped[int]
    entry_count: Mapped[int]
    line_count: Mapped[int]
    total_debit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    total_credit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    tied: Mapped[bool]
    failure: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class SelectionRow(Base):
    __tablename__ = "selections"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    procedure_id: Mapped[UUID]
    population_id: Mapped[UUID]
    parameters: Mapped[dict[str, object]] = mapped_column(JSONB)
    criteria_version: Mapped[int]
    random_method: Mapped[str]
    seed: Mapped[int]
    item_count: Mapped[int]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class SelectedItem(Base):
    __tablename__ = "selected_items"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    selection_id: Mapped[UUID]
    position: Mapped[int]
    posted_on: Mapped[date]
    kind: Mapped[str]
    reference: Mapped[str]
    counterparty: Mapped[str]
    line_nos: Mapped[list[int]] = mapped_column(ARRAY(Integer))
    accounts: Mapped[list[str]] = mapped_column(ARRAY(String))
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    descriptions: Mapped[list[str]] = mapped_column(ARRAY(String))
    rules: Mapped[list[str]] = mapped_column(ARRAY(String))
    reason: Mapped[str | None]
    band: Mapped[int | None]  # SPEC-038: a payment's timing band
    recorded_bill_reference: Mapped[str | None]
    recorded_bill_date: Mapped[date | None]


class ItemResult(Base):
    __tablename__ = "item_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    selected_item_id: Mapped[UUID]
    result: Mapped[str]
    note: Mapped[str | None]
    evidence_version_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    recorded_by: Mapped[UUID]
    relates_to_year: Mapped[str | None]  # SPEC-038: yes | no | unclear
    adopted_assessment_id: Mapped[UUID | None]  # SPEC-044: the agent proposal a person adopted
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ItemSupportRequest(Base):
    __tablename__ = "item_support_requests"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    selected_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    request_item_id: Mapped[UUID] = mapped_column(primary_key=True)
    requested_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ProcedureConclusion(Base):
    __tablename__ = "procedure_conclusions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    procedure_id: Mapped[UUID]
    text: Mapped[str]
    written_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class WorkpaperVersion(Base):
    __tablename__ = "workpaper_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    procedure_id: Mapped[UUID]
    version: Mapped[int]
    selection_id: Mapped[UUID]
    result_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    conclusion_id: Mapped[UUID]
    materiality_id: Mapped[UUID]
    sha256: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class WorkpaperSignature(Base):
    __tablename__ = "workpaper_signatures"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    workpaper_version_id: Mapped[UUID] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(primary_key=True)
    signed_by: Mapped[UUID]
    role: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class EngagementAccount(Base):
    """Bank or payables accounts a person confirmed (SPEC-038; TASK-086). Insert-only."""

    __tablename__ = "engagement_accounts"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    role: Mapped[str]
    account_codes: Mapped[list[str]] = mapped_column(ARRAY(String))
    confirmed_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class SelectionApproval(Base):
    """A manager's or partner's approval of one selection (SPEC-040; TASK-100). Insert-only."""

    __tablename__ = "selection_approvals"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    selection_id: Mapped[UUID]
    approved_by: Mapped[UUID]
    note: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ItemSignoff(Base):
    """A preparer's or reviewer's sign-off on one row, bound to the result it signed (SPEC-040;
    TASK-100). Insert-only; stale when a newer result exists."""

    __tablename__ = "item_signoffs"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    selected_item_id: Mapped[UUID]
    item_result_id: Mapped[UUID]
    level: Mapped[str]
    signed_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReviewNote(Base):
    """A reviewer's note on a row or the workpaper (SPEC-041; TASK-103). Insert-only."""

    __tablename__ = "review_notes"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    procedure_id: Mapped[UUID]
    selected_item_id: Mapped[UUID | None]
    body: Mapped[str]
    raised_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ReviewNoteEvent(Base):
    """A response, reopening or clearing of a note (SPEC-041). Insert-only; the newest counts."""

    __tablename__ = "review_note_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    review_note_id: Mapped[UUID]
    kind: Mapped[str]
    body: Mapped[str | None]
    by_user: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Finding(Base):
    """A finding on the engagement (SPEC-043; TASK-107). Insert-only."""

    __tablename__ = "findings"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    procedure_id: Mapped[UUID | None]
    selected_item_id: Mapped[UUID | None]
    title: Mapped[str]
    description: Mapped[str | None]
    raised_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class Misstatement(Base):
    """A misstatement on a finding (SPEC-043). Insert-only; the newest per finding counts."""

    __tablename__ = "misstatements"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    finding_id: Mapped[UUID]
    kind: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2))
    account_code: Mapped[str | None]
    corrected: Mapped[bool]
    recorded_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ProcedureSessionEvent(Base):
    """A person approving a procedure session's plan (SPEC-044; TASK-109). Insert-only."""

    __tablename__ = "procedure_session_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    procedure_id: Mapped[UUID]
    kind: Mapped[str]
    by_user: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
