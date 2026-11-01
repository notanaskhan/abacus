"""Working papers (A-04; SPEC-308; TASK-319). The paper, its sections, cells, citations and
versions are insert-only: a cell's newest row is its value, and sign-offs snapshot a numbered
version (ADR-004). 0581 (A-04-T03) adds attention flags, whose state moves, their insert-only
events, and the engagement's audit procedures."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import FetchedValue
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import Text

from abacus.kernel.db import Base


class Workpaper(Base):
    __tablename__ = "workpapers"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    code: Mapped[str]
    title: Mapped[str]
    audit_area: Mapped[str | None]
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # 0581 (A-04-T03): the A-04 kind and the program steps the paper answers.
    kind: Mapped[str | None]
    program_step_keys: Mapped[list[str]] = mapped_column(
        ARRAY(Text), server_default=FetchedValue()
    )


class WorkpaperSection(Base):
    __tablename__ = "workpaper_sections"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())  # 0581: trigger-set
    work_item_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    workpaper_id: Mapped[UUID]
    sheet_key: Mapped[str]
    title: Mapped[str]
    position: Mapped[int]
    band_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class WorkpaperCell(Base):
    __tablename__ = "workpaper_cells"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    workpaper_id: Mapped[UUID]
    sheet_key: Mapped[str]
    cell_key: Mapped[str]
    raw: Mapped[str | None]
    value_source: Mapped[str]
    tickmarks: Mapped[list[str]] = mapped_column(ARRAY(Text))
    set_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # 0581 (A-04-T03): the scope (trigger-set), the structured address, the typed value `{t, v}`
    # and its state.
    engagement_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    work_item_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    section_key: Mapped[str | None]
    row_key: Mapped[str | None]
    col_key: Mapped[str | None]
    value: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    value_state: Mapped[str] = mapped_column(server_default=FetchedValue())
    suggestion_id: Mapped[UUID | None]
    classification: Mapped[str] = mapped_column(server_default=FetchedValue())
    updated_version_no: Mapped[int | None]


class WorkpaperCellCitation(Base):
    __tablename__ = "workpaper_cell_citations"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    workpaper_id: Mapped[UUID]
    sheet_key: Mapped[str]
    cell_key: Mapped[str]
    evidence_version_id: Mapped[UUID]
    locator: Mapped[str | None]
    added_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class WorkpaperVersion(Base):
    __tablename__ = "workpaper_versions"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    workpaper_id: Mapped[UUID]
    version_no: Mapped[int]
    content_hash: Mapped[str]
    # The signed content snapshot, JSON of any shape.
    content: Mapped[dict[str, Any]] = mapped_column(JSONB)  # Any: JSON
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    # 0581 (A-04-T03): who produced the version and why.
    engagement_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    work_item_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    produced_by_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    agent_run_id: Mapped[UUID | None]
    on_behalf_of_user_id: Mapped[UUID | None]
    cause: Mapped[str | None]


class AttentionFlag(Base):
    """0581 (A-04-T03): a PBC gap raised on a section row; it converts to a request item or a
    review note, or is resolved. The scope columns follow the workpaper."""

    __tablename__ = "attention_flags"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    work_item_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    workpaper_id: Mapped[UUID]
    section_key: Mapped[str]
    row_key: Mapped[str | None]
    kind: Mapped[str]
    text: Mapped[str]
    state: Mapped[str] = mapped_column(server_default=FetchedValue())
    converted_to_kind: Mapped[str | None]
    converted_to_id: Mapped[UUID | None]
    created_by: Mapped[UUID]
    created_by_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    agent_run_id: Mapped[UUID | None]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class AttentionFlagEvent(Base):
    """0581: one insert-only event in a flag's life; the actor kind is the session's."""

    __tablename__ = "attention_flag_events"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    work_item_id: Mapped[UUID] = mapped_column(server_default=FetchedValue())
    workpaper_id: Mapped[UUID]
    flag_id: Mapped[UUID]
    event: Mapped[str]
    actor_kind: Mapped[str] = mapped_column(server_default=FetchedValue())
    actor_user_id: Mapped[UUID | None]
    agent_run_id: Mapped[UUID | None]
    ref: Mapped[dict[str, Any] | None] = mapped_column(JSONB)  # Any: JSON
    at: Mapped[datetime] = mapped_column(server_default=FetchedValue())


class ProgramProcedure(Base):
    """0581: one program step on the engagement's pinned methodology version (A-04 §4.2's
    `procedures`); a mandatory step is never tailored."""

    __tablename__ = "program_procedures"

    id: Mapped[UUID] = mapped_column(primary_key=True, server_default=FetchedValue())
    tenant_id: Mapped[UUID]
    engagement_id: Mapped[UUID]
    work_item_id: Mapped[UUID]
    methodology_version_id: Mapped[UUID]
    program_step_key: Mapped[str]
    level: Mapped[str]
    mandatory: Mapped[bool]
    tailored: Mapped[bool] = mapped_column(server_default=FetchedValue())
    tailored_rationale: Mapped[str | None]
    status: Mapped[str] = mapped_column(server_default=FetchedValue())
    # Any: JSON; SQL NULL for None (the column's CHECK refuses a JSON null).
    linked_work: Mapped[dict[str, Any] | None] = mapped_column(JSONB(none_as_null=True))
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=FetchedValue())
    row_version: Mapped[int] = mapped_column(server_default=FetchedValue())  # 0614
