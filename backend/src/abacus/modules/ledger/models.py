"""Ledger snapshots and trial balance lines (glossary; ADR-004, ADR-038). TASK-010 design §4."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import FetchedValue, Numeric
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
