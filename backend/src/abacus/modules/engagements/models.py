"""Engagements (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

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
    fiscal_period_start: Mapped[date]
    fiscal_period_end: Mapped[date]
    status: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]
    # The pinned methodology version (SPEC-008): set once, null until then.
    methodology_version_id: Mapped[UUID | None]


class MethodologyTemplate(Base):
    __tablename__ = "methodology_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    name: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]


class MethodologyVersion(Base):
    __tablename__ = "methodology_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    template_id: Mapped[UUID]
    version: Mapped[int]
    source_fingerprint: Mapped[str]
    imported_by: Mapped[UUID]
    created_at: Mapped[datetime]


class MethodologyArea(Base):
    __tablename__ = "methodology_areas"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(primary_key=True)
    name: Mapped[str]
    position: Mapped[int]


class MethodologyRequestItem(Base):
    __tablename__ = "methodology_request_items"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    area_code: Mapped[str]
    description: Mapped[str]
    retrievability_tier: Mapped[str]


class MethodologyAccountRule(Base):
    __tablename__ = "methodology_account_rules"

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    position: Mapped[int] = mapped_column(primary_key=True)
    area_code: Mapped[str]
    account_from: Mapped[str]
    account_to: Mapped[str]
