"""A methodology version's template wrapper (K-03-T19; TASK-9013; K-03 F5; DEC-6019).

1010 wrapped every published methodology version (and every pinned one) in a published template
version; engagements' link points at that wrapper. These reads answer which wrapper a methodology
version has, and which methodology version a template version carries, inside the caller's
session (engagements' unit of work), so the link and the pin see one transaction.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import TenantContext, tenant_session

_WRAPPER: Final = text(
    "SELECT template_id, id FROM template_versions WHERE methodology_version_id = :m "
    "AND status = 'published' ORDER BY seq DESC LIMIT 1"
)
_CARRIED: Final = text("SELECT methodology_version_id FROM template_versions WHERE id = :v")


async def template_wrapper_of(
    session: AsyncSession, methodology_version_id: UUID
) -> tuple[UUID, UUID] | None:
    """(template, template version) wrapping the methodology version, or None."""
    row = (await session.execute(_WRAPPER, {"m": methodology_version_id})).first()
    return None if row is None else (cast(UUID, row.template_id), cast(UUID, row.id))


async def wrapped_methodology_version(session: AsyncSession, version_id: UUID) -> UUID | None:
    """The methodology version a template version carries, or None."""
    return cast(UUID | None, await session.scalar(_CARRIED, {"v": version_id}))


# --- a template version's sheet definition (K-03-T20; DEC-6020) ----------------------------------


@dataclass(frozen=True)
class SheetColumnDef:
    id: UUID
    key: str
    name: str
    type: str
    config: Mapping[str, object]
    required: bool
    client_visible: bool
    classification: str
    classification_reason: str | None
    source_binding: Mapping[str, object] | None
    position: int


@dataclass(frozen=True)
class SheetDefinition:
    id: UUID
    key: str
    title: str
    step_key: str | None
    row_source: str
    sections: tuple[Mapping[str, object], ...]
    columns: tuple[SheetColumnDef, ...]


_DEFINITION: Final = text(
    "SELECT id, sheet_key, title, step_key, row_source, sections FROM template_sheet_definitions "
    "WHERE template_version_id = :v AND sheet_key = :k"
)
_COLUMNS: Final = text(
    "SELECT id, column_key, name, type, config, required, client_visible, classification, "
    "classification_reason, source_binding, position FROM template_sheet_columns "
    "WHERE sheet_definition_id = :d ORDER BY position, id"
)


async def sheet_definition_of(
    tenant: TenantContext, version_id: UUID, sheet_key: str
) -> SheetDefinition | None:
    """The version's sheet definition by key, with its columns; for a caller that authorised on
    the engagement using it (template content is firm-wide, no wall applies)."""
    async with tenant_session(tenant) as session:
        row = (await session.execute(_DEFINITION, {"v": version_id, "k": sheet_key})).first()
        if row is None:
            return None
        columns = list(await session.execute(_COLUMNS, {"d": row.id}))
    sections = cast(list[Mapping[str, object]], row.sections or [])
    return SheetDefinition(
        cast(UUID, row.id), str(row.sheet_key), str(row.title),
        None if row.step_key is None else str(row.step_key), str(row.row_source),
        tuple(sections),
        tuple(
            SheetColumnDef(
                cast(UUID, c.id), str(c.column_key), str(c.name), str(c.type),
                cast(Mapping[str, object], c.config or {}), bool(c.required),
                bool(c.client_visible), str(c.classification),
                None if c.classification_reason is None else str(c.classification_reason),
                cast(Mapping[str, object] | None, c.source_binding), int(c.position),
            )
            for c in columns
        ),
    )  # fmt: skip


__all__ = [
    "SheetColumnDef",
    "SheetDefinition",
    "sheet_definition_of",
    "template_wrapper_of",
    "wrapped_methodology_version",
]
