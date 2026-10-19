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


class ItemResult(Base):
    __tablename__ = "item_results"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    selected_item_id: Mapped[UUID]
    result: Mapped[str]
    note: Mapped[str | None]
    evidence_version_ids: Mapped[list[UUID]] = mapped_column(ARRAY(PgUUID(as_uuid=True)))
    recorded_by: Mapped[UUID]
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
