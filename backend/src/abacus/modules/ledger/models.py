"""Ledger snapshots and trial balance lines (glossary; ADR-004, ADR-038). TASK-010 design §4."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import FetchedValue, Numeric
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from abacus.kernel.db import Base


class LedgerSnapshot(Base):
    __tablename__ = "ledger_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    period_start: Mapped[date]
    period_end: Mapped[date]
    pulled_at: Mapped[datetime]
    source: Mapped[str]
    raw_fingerprint: Mapped[str]
    line_count: Mapped[int]
    total_debit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    total_credit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    created_at: Mapped[datetime]


class TrialBalanceLineRow(Base):
    __tablename__ = "trial_balance_lines"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    snapshot_id: Mapped[UUID]
    account_code: Mapped[str]
    account_name: Mapped[str]
    debit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    credit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    source_ref: Mapped[str]


# --- General ledger detail (SPEC-034; TASK-069) -------------------------------------------------


class GlSnapshot(Base):
    __tablename__ = "gl_snapshots"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    period_start: Mapped[date]
    period_end: Mapped[date]
    source: Mapped[str]
    raw_fingerprint: Mapped[str]
    tb_snapshot_id: Mapped[UUID | None]  # None only for a subsequent-period ledger (SPEC-038)
    kind: Mapped[str] = mapped_column(server_default=FetchedValue())  # year | subsequent
    line_count: Mapped[int]
    total_debit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    total_credit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    created_at: Mapped[datetime]


class GlAccountBalance(Base):
    __tablename__ = "gl_account_balances"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    snapshot_id: Mapped[UUID] = mapped_column(primary_key=True)
    account_code: Mapped[str] = mapped_column(primary_key=True)
    account_name: Mapped[str]
    opening: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    debit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    credit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    closing: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    tb_closing: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    opening_derived: Mapped[bool]


class GlEntryRow(Base):
    __tablename__ = "gl_entries"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    snapshot_id: Mapped[UUID] = mapped_column(primary_key=True)
    line_no: Mapped[int] = mapped_column(primary_key=True)
    account_code: Mapped[str]
    posted_on: Mapped[date]
    reference: Mapped[str | None]
    kind: Mapped[str | None]
    counterparty: Mapped[str | None]
    description: Mapped[str | None]
    debit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    credit: Mapped[Decimal] = mapped_column(Numeric(20, 2))
    source_ref: Mapped[str]


# --- The trial balance of record (SPEC-309; TASK-320; A-02) -------------------------------------


class TrialBalance(Base):
    __tablename__ = "trial_balances"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    label: Mapped[str]
    period_start: Mapped[date]
    period_end: Mapped[date]
    display_unit: Mapped[str]
    current_version_no: Mapped[int] = mapped_column(server_default=FetchedValue())
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class TrialBalanceVersion(Base):
    __tablename__ = "trial_balance_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    trial_balance_id: Mapped[UUID]
    client_entity_id: Mapped[UUID]
    version_no: Mapped[int]
    snapshot_id: Mapped[UUID]
    prior_snapshot_id: Mapped[UUID | None]
    adopted_by: Mapped[UUID]
    actor_kind: Mapped[str]
    reason: Mapped[str | None]
    content_fingerprint: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class TrialBalanceAnnotation(Base):
    __tablename__ = "trial_balance_annotations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    trial_balance_id: Mapped[UUID]
    account_code: Mapped[str]
    area: Mapped[str | None]
    wp_ref: Mapped[str | None]
    reason: Mapped[str | None]
    set_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


# --- Account mapping (SPEC-316; TASK-345; A-03) -------------------------------------------------


class GroupingSet(Base):
    __tablename__ = "grouping_sets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    key: Mapped[str]
    name: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class GroupingSetVersion(Base):
    __tablename__ = "grouping_set_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    grouping_set_id: Mapped[UUID]
    version: Mapped[int]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    payload_hash: Mapped[str]
    problems: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)  # Any: JSON
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    published_by: Mapped[UUID | None]
    published_at: Mapped[datetime | None]
    published_actor_kind: Mapped[str | None]


class Grouping(Base):
    __tablename__ = "groupings"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    version_id: Mapped[UUID]
    key: Mapped[str]
    label: Mapped[str]
    class_: Mapped[str] = mapped_column("class")
    position: Mapped[int]


class FsLine(Base):
    __tablename__ = "fs_lines"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    version_id: Mapped[UUID]
    grouping_id: Mapped[UUID]
    key: Mapped[str]
    label: Mapped[str]
    normal_balance: Mapped[str]
    position: Mapped[int]


class FsLineRangeRule(Base):
    __tablename__ = "fs_line_range_rules"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    version_id: Mapped[UUID]
    position: Mapped[int]
    account_from: Mapped[str]
    account_to: Mapped[str]
    fs_line_id: Mapped[UUID]


class MappingSet(Base):
    __tablename__ = "mapping_sets"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    trial_balance_id: Mapped[UUID]
    grouping_set_version_id: Mapped[UUID]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class MappingSetEdit(Base):
    __tablename__ = "mapping_set_edits"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    mapping_set_id: Mapped[UUID]
    account_code: Mapped[str]
    fs_line_id: Mapped[UUID | None]
    edited_by: Mapped[UUID]
    actor_kind: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
