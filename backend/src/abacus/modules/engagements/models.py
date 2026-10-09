"""Engagements (glossary). TASK-008 design §1."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import ARRAY, FetchedValue, String
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
    # SPEC-025 (TASK-048): the engagement this one was rolled forward from, set at creation.
    prior_engagement_id: Mapped[UUID | None]


class MethodologyTemplate(Base):
    __tablename__ = "methodology_templates"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    tenant_id: Mapped[UUID]
    name: Mapped[str]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime]
    # SPEC-024: the engagement types it serves, fixed when the template is created.
    engagement_types: Mapped[list[str]] = mapped_column(ARRAY(String))


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
