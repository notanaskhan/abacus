"""Working papers (A-04; SPEC-308; TASK-319). Every table is insert-only: a cell's newest row
is its value, and sign-offs snapshot a numbered version (ADR-004)."""

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
