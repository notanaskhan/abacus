"""Fieldwork records (SPEC-037; TASK-077; ADR-116, ADR-117)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import ARRAY, FetchedValue, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB
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
