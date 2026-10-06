"""Ledger snapshots and trial balance lines (glossary; ADR-004, ADR-038). TASK-010 design §4."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Numeric
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
