"""The Sheets engine core (K-03-T20; TASK-9014; K-03 §3.7; SHT-01 a, b, c, f; SPEC-721; ADR-050;
DEC-6020; amber).

A sheet is a typed grid on a work item, made from the engagement's linked template version's
sheet definition. Code computes every count and total; cells are written only through
`review.api.record_value`, so field history and sign-off staleness work as on designed papers.

- **Create** (`create_sheet`, `sheet.configure`): from the definition named on a procedure of the
  work item (the Board's procedure-start event calls the same service, K-04). Columns copy the
  definition's (origin `template`), sections its `sections`, plus a shared "Default" view. One
  sheet per work item and key: a second create answers the first.
- **Rows from a sample** (`add_rows_from_sample`, `sheet.edit`): the newest approved version's
  items, each in the section whose `stratum` it carries, with the cells the definition binds to
  the sample (`source_binding {"sample": "amount" | "record_key" | "display.<field>"}`) written as
  an import. Idempotent: an item already on the sheet is not added twice.
- **Manual rows** (`add_row`) and **cell edits** (`edit_row`, `sheet.edit`): an edit names the
  row version it saw; a moved row answers 412; a row a reviewer signed (current) answers 423
  `row_locked`. Each changed cell is one `record_value` and the row's version moves once.
- **Read** (`sheet_vm`, `rows`): sections with counts and totals (the section's
  `totals {"sum": "<column>"}`, else the first currency column), the status bar, and rows through
  a stored view's filters and sort. Views are server-stored (`save_view`).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, Literal, cast
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import (
    DomainConflict,
    DomainInvalid,
    DomainPreconditionFailed,
    NotFound,
)
from abacus.kernel.uow import Ref, Scope, Target, UnitOfWork, uow
from abacus.modules.engagements.api import engagement_resource_of, linked_template_version
from abacus.modules.identity.api import AuthContext, Forbidden, Resource, authorise
from abacus.modules.methodology.api import SheetDefinition, sheet_definition_of
from abacus.modules.review.api import content_hash, record_value, sign_off_states
from abacus.modules.sampling.api import SampleRow, approved_sample_rows, version_seed

TARGET: Final = "sheet_row"
_KEY: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,59}$")
_DECIMAL_TYPES: Final = frozenset({"number", "currency"})
EDIT_NOTE: Final = "Entered on the sheet"  # the cell edit's provenance (record_value's note)


class NoTemplateLink(DomainConflict):
    """The engagement follows no template version yet, so it has no sheet definitions."""

    code = "no_template_link"


class SampleAlreadyLinked(DomainConflict):
    """The sheet's rows come from another sample set."""

    code = "sample_already_linked"


class RowLocked(DomainConflict):
    """A reviewer signed this row off: reopen it before editing."""

    code = "row_locked"


class CellInvalid(DomainInvalid):
    """A cell value does not fit its column's type, or names no column of the sheet."""

    code = "cell_invalid"


@dataclass(frozen=True)
class Column:
    id: UUID
    key: str
    name: str
    type: str
    width: int
    frozen: bool
    config: Mapping[str, object]
    template_ref: UUID | None


@dataclass(frozen=True)
class Cell:
    value: str
    state: str
    by: UUID | None
    at: datetime | None
    exception: bool
    # K-03-T22 (DEC-6033): the agent's suggestion behind a suggested, adopted or edited cell.
    suggestion_id: UUID | None = None


@dataclass(frozen=True)
class SheetRow:
    id: UUID
    key: str
    section_key: str
    position: int
    version: int
    locked: bool
    cells: Mapping[str, Cell]


@dataclass(frozen=True)
class SheetSection:
    key: str
    title: str
    count: int
    total: Decimal | None


@dataclass(frozen=True)
class SheetView:
    id: UUID
    key: str
    name: str
    filters: tuple[Mapping[str, str], ...]
    sort: tuple[Mapping[str, str], ...]
    columns_off: tuple[str, ...]


@dataclass(frozen=True)
class SheetVm:
    id: UUID
    work_item_id: UUID
    title: str
    columns: tuple[Column, ...]
    sections: tuple[SheetSection, ...]
    rows: int
    exceptions: int
    view: str
    sample_seed: int | None
    engagement_id: UUID | None = None  # K-03-T23: the comment threads' engagement


# --- authorisation -------------------------------------------------------------------------------


@dataclass(frozen=True)
class _Sheet:
    id: UUID
    engagement_id: UUID
    work_item_id: UUID
    title: str
    kind: str
    template_version_id: UUID
    sheet_key: str
    sample_set_id: UUID | None
    sample_version: int | None


_SHEET: Final = text(
    "SELECT id, engagement_id, work_item_id, title, kind, template_version_id, sheet_key, "
    "sample_set_id, sample_version FROM sheets WHERE id = :s"
)


async def _resource(ctx: AuthContext, engagement_id: UUID, work_item_id: UUID) -> Resource:
    resource = await engagement_resource_of(ctx.tenant, engagement_id)
    return replace(resource, work_item_id=work_item_id)


async def _sheet(ctx: AuthContext, sheet_id: UUID, action: str) -> _Sheet:
    """The sheet, authorised on its work item; 404 when absent or walled (INV-3)."""
    async with tenant_session(ctx.tenant) as session:
        row = (await session.execute(_SHEET, {"s": sheet_id})).first()
    if row is None:
        raise NotFound("sheet")
    found = _Sheet(
        row.id, row.engagement_id, row.work_item_id, str(row.title), str(row.kind),
        row.template_version_id, str(row.sheet_key), row.sample_set_id, row.sample_version,
    )  # fmt: skip
    try:
        await authorise(ctx, action, await _resource(ctx, found.engagement_id, found.work_item_id))
    except Forbidden:
        if action == "sheet.read":
            raise NotFound("sheet") from None
        await authorise(ctx, "sheet.read", await _resource(ctx, found.engagement_id,
                                                           found.work_item_id))  # fmt: skip
        raise
    return found


# --- creating a sheet ----------------------------------------------------------------------------

_PROCEDURE: Final = text(
    "SELECT id, engagement_id, work_item_id, linked_work FROM program_procedures WHERE id = :p"
)
_EXISTING: Final = text("SELECT id FROM sheets WHERE work_item_id = :w AND sheet_key = :k")
_INSERT_SHEET: Final = text(
    "INSERT INTO sheets (id, tenant_id, engagement_id, work_item_id, procedure_id, sheet_key, "
    "title, template_version_id, sheet_definition_id, kind, created_by) VALUES (:id, :t, :e, :w, "
    ":p, :k, :title, :v, :d, :kind, :by)"
)
_INSERT_COLUMN: Final = text(
    "INSERT INTO sheet_columns (id, tenant_id, engagement_id, work_item_id, sheet_id, column_key, "
    "name, type, config, required, client_visible, classification, classification_reason, "
    "origin, template_column_ref, position) VALUES (:id, :t, :e, :w, :s, :key, :name, :type, "
    "CAST(:config AS jsonb), :required, :visible, :classification, :reason, 'template', :ref, "
    ":position)"
)
_INSERT_SECTION: Final = text(
    "INSERT INTO sheet_sections (tenant_id, engagement_id, work_item_id, sheet_id, section_key, "
    "title, position, totals_spec) VALUES (:t, :e, :w, :s, :key, :title, :position, "
    "CAST(:totals AS jsonb))"
)
_INSERT_VIEW: Final = text(
    "INSERT INTO sheet_views (id, tenant_id, engagement_id, work_item_id, sheet_id, view_key, "
    "name, filters, sort, visible_columns, created_by, shared) VALUES (:id, :t, :e, :w, :s, "
    ":key, :name, CAST(:filters AS jsonb), CAST(:sort AS jsonb), :off, :by, :shared)"
)


def _sections_of(definition: SheetDefinition) -> list[tuple[str, str, Mapping[str, object]]]:
    """(key, title, totals) per definition section; one "rows" section when it names none."""
    out: list[tuple[str, str, Mapping[str, object]]] = []
    for raw in definition.sections:
        key, title = str(raw.get("key", "")), str(raw.get("title", "")).strip()
        if _KEY.fullmatch(key) and title:
            totals = raw.get("totals")
            out.append((key, title[:200], cast(Mapping[str, object], totals or {})))
    return out or [("rows", definition.title, {})]


async def create_sheet(
    ctx: AuthContext, work_item_id: UUID, procedure_id: UUID, sheet_key: str
) -> UUID:
    async with tenant_session(ctx.tenant) as session:
        procedure = (await session.execute(_PROCEDURE, {"p": procedure_id})).first()
    if procedure is None or procedure.work_item_id != work_item_id:
        raise NotFound("procedure")
    engagement_id = cast(UUID, procedure.engagement_id)
    await authorise(ctx, "sheet.configure", await _resource(ctx, engagement_id, work_item_id))
    version = await linked_template_version(ctx.tenant, engagement_id)
    if version is None:
        raise NoTemplateLink(facts={"engagement": str(engagement_id)})
    definition = await sheet_definition_of(ctx.tenant, version, sheet_key)
    if definition is None:
        raise NotFound("sheet_definition")
    async with uow(ctx.tenant) as tx:
        existing = await tx.session.scalar(_EXISTING, {"w": work_item_id, "k": sheet_key})
        if existing is not None:
            tx.record(
                "sheet.opened",
                target=Target("sheet", existing),
                scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
            )
            return cast(UUID, existing)
        sheet_id = uuid4()
        base = {"t": ctx.tenant_id, "e": engagement_id, "w": work_item_id, "s": sheet_id}
        await tx.session.execute(
            _INSERT_SHEET,
            {"id": sheet_id, "t": ctx.tenant_id, "e": engagement_id, "w": work_item_id,
             "p": procedure_id, "k": definition.key, "title": definition.title, "v": version,
             "d": definition.id, "kind": "internal", "by": ctx.user_id},
        )  # fmt: skip
        for c in definition.columns:
            await tx.session.execute(
                _INSERT_COLUMN,
                base
                | {
                    "id": uuid4(),
                    "key": c.key,
                    "name": c.name,
                    "type": c.type,
                    "config": json.dumps(dict(c.config)),
                    "required": c.required,
                    "visible": False,
                    "classification": c.classification,
                    "reason": c.classification_reason,
                    "ref": c.id,
                    "position": c.position,
                },
            )  # fmt: skip  (internal sheet: never client-visible, 1012's guard)
        for position, (key, title, totals) in enumerate(_sections_of(definition)):
            await tx.session.execute(
                _INSERT_SECTION,
                base | {"key": key, "title": title, "position": position,
                        "totals": json.dumps(dict(totals))},
            )  # fmt: skip
        await tx.session.execute(
            _INSERT_VIEW,
            base | {"id": uuid4(), "key": "default", "name": "Default", "filters": "[]",
                    "sort": "[]", "off": [], "by": ctx.user_id, "shared": True},
        )  # fmt: skip
        tx.record(
            "sheet.created",
            target=Target("sheet", sheet_id),
            after=Ref(template_version=version, columns=len(definition.columns)),
            scope=Scope(engagement_id=engagement_id, work_item_id=work_item_id),
        )
    return sheet_id


# --- columns, cells and values -------------------------------------------------------------------

_COLUMNS: Final = text(
    "SELECT id, column_key, name, type, width, frozen, config, template_column_ref "
    "FROM sheet_columns WHERE sheet_id = :s AND deleted_at IS NULL ORDER BY position, id"
)


async def _columns(session: AsyncSession, sheet_id: UUID) -> list[Column]:
    return [
        Column(
            r.id, str(r.column_key), str(r.name), str(r.type), int(r.width), bool(r.frozen),
            cast(Mapping[str, object], r.config or {}), r.template_column_ref,
        )
        for r in await session.execute(_COLUMNS, {"s": sheet_id})
    ]  # fmt: skip


def typed(column: Column, raw: str) -> dict[str, object]:
    """A cell's text as `record_value`'s `{t, v}` by the column's type (422 when it does not fit);
    an empty string empties the cell."""
    text_value = raw.strip()
    if column.type in _DECIMAL_TYPES:
        if not text_value:
            return {"t": "decimal", "v": None}
        try:
            number = Decimal(text_value.replace(",", ""))
        except InvalidOperation:
            raise CellInvalid(facts={"column": column.key}) from None
        if not number.is_finite():
            raise CellInvalid(facts={"column": column.key})
        return {"t": "decimal", "v": str(number)}
    if column.type == "date":
        if text_value and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text_value):
            raise CellInvalid(facts={"column": column.key})
        return {"t": "date", "v": text_value or None}
    return {"t": "text", "v": text_value[:4000] or None}


def _shown(value: Mapping[str, object] | None) -> str:
    if value is None or value.get("v") is None:
        return ""
    return str(value["v"])


def _exception(column: Column, shown: str) -> bool:
    marker = column.config.get("exception_value")
    return isinstance(marker, str) and shown != "" and shown == marker


# --- rows ----------------------------------------------------------------------------------------

_ROW_COUNT: Final = text("SELECT count(*) FROM sheet_rows WHERE sheet_id = :s")
_INSERT_ROW: Final = text(
    "INSERT INTO sheet_rows (id, tenant_id, engagement_id, work_item_id, sheet_id, row_key, "
    "section_key, position, source_ref, created_by) VALUES (:id, :t, :e, :w, :s, :key, :section, "
    ":position, CAST(:source AS jsonb), :by) "
    "ON CONFLICT (tenant_id, sheet_id, row_key) DO NOTHING RETURNING id"
)
_UPSERT_CELL: Final = text(
    "INSERT INTO sheet_cells (tenant_id, engagement_id, work_item_id, sheet_id, row_id, "
    "column_id, value, value_state, last_edited_by, last_edited_at) VALUES (:t, :e, :w, :s, :r, "
    ":c, CAST(:value AS jsonb), :state, :by, now()) ON CONFLICT (row_id, column_id) DO UPDATE SET "
    "previous_value = sheet_cells.value, value = EXCLUDED.value, value_state = "
    "EXCLUDED.value_state, last_edited_by = EXCLUDED.last_edited_by, last_edited_at = now()"
)
_SECTION_KEYS: Final = text("SELECT section_key FROM sheet_sections WHERE sheet_id = :s")


async def _write_cell(
    tx: UnitOfWork, sheet: _Sheet, ctx: AuthContext, row_id: UUID, column: Column,
    value: dict[str, object], *, imported: bool,
) -> None:  # fmt: skip
    await record_value(
        tx, engagement_id=sheet.engagement_id, target_type=TARGET, target_id=row_id,
        field_key=column.key, value=value,
        value_source="engine_import" if imported else "human",
        cause="import" if imported else "edit",
        citation_note=None if imported else EDIT_NOTE,
    )  # fmt: skip
    empty = value.get("v") is None
    await tx.session.execute(
        _UPSERT_CELL,
        {"t": ctx.tenant_id, "e": sheet.engagement_id, "w": sheet.work_item_id, "s": sheet.id,
         "r": row_id, "c": column.id, "value": None if empty else json.dumps(value),
         "state": "empty" if empty else "human", "by": None if empty else ctx.user_id},
    )  # fmt: skip


def _bound_value(binding: Mapping[str, object] | None, item: SampleRow) -> str | None:
    field = (binding or {}).get("sample")
    if field == "amount":
        return None if item.amount is None else str(item.amount)
    if field == "record_key":
        return str(item.record_key)
    if isinstance(field, str) and field.startswith("display."):
        found = item.display.get(field.removeprefix("display."))
        return None if found is None else str(found)
    return None


async def add_rows_from_sample(
    ctx: AuthContext, sheet_id: UUID, sample_set_id: UUID
) -> list[UUID]:
    """The approved sample's items as rows, in their strata's sections; answers the new rows."""
    sheet = await _sheet(ctx, sheet_id, "sheet.edit")
    if sheet.sample_set_id is not None and sheet.sample_set_id != sample_set_id:
        raise SampleAlreadyLinked(facts={"sample_set": str(sheet.sample_set_id)})
    sample = await approved_sample_rows(ctx, sample_set_id)
    definition = await sheet_definition_of(ctx.tenant, sheet.template_version_id, sheet.sheet_key)
    bindings = {} if definition is None else {c.id: c.source_binding for c in definition.columns}
    stratum_section = {} if definition is None else _stratum_sections(definition)
    async with tenant_session(ctx.tenant) as session:
        columns = await _columns(session, sheet_id)
        keys = await session.execute(_SECTION_KEYS, {"s": sheet_id})
        sections = {str(r.section_key) for r in keys}
    added: list[UUID] = []
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("UPDATE sheets SET sample_set_id = :set, sample_version = :v, "
                 "version = version + 1 WHERE id = :s"),
            {"set": sample_set_id, "v": sample.version_no, "s": sheet_id},
        )  # fmt: skip
        for item in sample.rows:
            section = stratum_section.get(item.stratum or 0) or next(iter(sorted(sections)))
            row_id = await tx.session.scalar(
                _INSERT_ROW,
                {"id": uuid4(), "t": ctx.tenant_id, "e": sheet.engagement_id,
                 "w": sheet.work_item_id, "s": sheet_id, "key": f"S{item.position:04d}",
                 "section": section, "position": item.position,
                 "source": json.dumps({"kind": "sample_item", "id": str(item.id)}),
                 "by": ctx.user_id},
            )  # fmt: skip
            if row_id is None:  # already on the sheet
                continue
            added.append(cast(UUID, row_id))
            for column in columns:
                ref = column.template_ref
                bound = _bound_value(None if ref is None else bindings.get(ref), item)
                if bound is not None:
                    await _write_cell(tx, sheet, ctx, cast(UUID, row_id), column,
                                      typed(column, bound), imported=True)  # fmt: skip
        tx.record(
            "sheet_rows.added_from_sample",
            target=Target("sheet", sheet_id),
            after=Ref(sample_set=sample_set_id, version=sample.version_no, rows=len(added),
                      seed=sample.seed),
            scope=Scope(engagement_id=sheet.engagement_id, work_item_id=sheet.work_item_id),
        )  # fmt: skip
    return added


def _stratum_sections(definition: SheetDefinition) -> dict[int, str]:
    """Section key per stratum, from the definition sections' `stratum` (1, 2, …)."""
    out: dict[int, str] = {}
    for section in definition.sections:
        stratum, key = section.get("stratum"), section.get("key")
        if isinstance(stratum, int) and isinstance(key, str):
            out[stratum] = key
    return out


async def add_row(
    ctx: AuthContext, sheet_id: UUID, section_key: str, cells: Mapping[str, str]
) -> UUID:
    sheet = await _sheet(ctx, sheet_id, "sheet.edit")
    async with tenant_session(ctx.tenant) as session:
        columns = {c.key: c for c in await _columns(session, sheet_id)}
        keys = await session.execute(_SECTION_KEYS, {"s": sheet_id})
        sections = {str(r.section_key) for r in keys}
        count = int(await session.scalar(_ROW_COUNT, {"s": sheet_id}) or 0)
    if section_key not in sections:
        raise CellInvalid(facts={"section": "unknown"})
    unknown = set(cells) - set(columns)
    if unknown:
        raise CellInvalid(facts={"columns": len(unknown)})
    async with uow(ctx.tenant) as tx:
        row_id = cast(UUID, await tx.session.scalar(
            _INSERT_ROW,
            {"id": uuid4(), "t": ctx.tenant_id, "e": sheet.engagement_id, "w": sheet.work_item_id,
             "s": sheet_id, "key": f"M{count + 1:04d}-{uuid4().hex[:6]}", "section": section_key,
             "position": count + 1, "source": json.dumps({"kind": "manual"}), "by": ctx.user_id},
        ))  # fmt: skip
        for key, raw in cells.items():
            await _write_cell(tx, sheet, ctx, row_id, columns[key], typed(columns[key], raw),
                              imported=False)  # fmt: skip
        tx.record(
            "sheet_row.added",
            target=Target("sheet_row", row_id),
            after=Ref(sheet=sheet_id, cells=len(cells)),
            scope=Scope(engagement_id=sheet.engagement_id, work_item_id=sheet.work_item_id),
        )
    return row_id


_ROW_FOR_UPDATE: Final = text(
    "SELECT id, row_version FROM sheet_rows WHERE id = :r AND sheet_id = :s FOR UPDATE"
)
_BUMP_ROW: Final = text("UPDATE sheet_rows SET row_version = row_version + 1 WHERE id = :r")


async def edit_row(
    ctx: AuthContext, sheet_id: UUID, row_id: UUID, cells: Mapping[str, str], version: int
) -> None:
    """Cell edits at the row version the editor saw: 412 when it moved, 423 `row_locked` when
    a reviewer's sign-off is current."""
    sheet = await _sheet(ctx, sheet_id, "sheet.edit")
    async with tenant_session(ctx.tenant) as session:
        columns = {c.key: c for c in await _columns(session, sheet_id)}
    unknown = set(cells) - set(columns)
    if unknown:
        raise CellInvalid(facts={"columns": len(unknown)})
    values = {k: typed(columns[k], v) for k, v in cells.items()}
    current = {r.id: r for r in await _row_views(ctx, sheet, columns, [row_id])}
    if row_id not in current:
        raise NotFound("sheet_row")
    if current[row_id].locked:
        raise RowLocked(facts={"row": str(row_id)})
    async with uow(ctx.tenant) as tx:
        row = (await tx.session.execute(_ROW_FOR_UPDATE, {"r": row_id, "s": sheet_id})).first()
        if row is None:
            raise NotFound("sheet_row")
        if int(row.row_version) != version:
            raise DomainPreconditionFailed(facts={"version": int(row.row_version)})
        changed = 0
        for key, value in values.items():
            if _shown(value) == current[row_id].cells.get(key, _EMPTY).value:
                continue
            await _write_cell(tx, sheet, ctx, row_id, columns[key], value, imported=False)
            changed += 1
        await tx.session.execute(_BUMP_ROW, {"r": row_id})
        tx.record(
            "sheet_row.cell_edited",
            target=Target("sheet_row", row_id),
            after=Ref(sheet=sheet_id, cells=changed, version=version + 1),
            scope=Scope(engagement_id=sheet.engagement_id, work_item_id=sheet.work_item_id),
        )


_EMPTY: Final = Cell("", "empty", None, None, False)


# --- reading -------------------------------------------------------------------------------------

_ROWS: Final = text(
    "SELECT id, row_key, section_key, position, row_version FROM sheet_rows WHERE sheet_id = :s "
    "AND (CAST(:ids AS uuid[]) IS NULL OR id = ANY(CAST(:ids AS uuid[]))) ORDER BY position, id"
)
_CELLS: Final = text(
    "SELECT row_id, column_id, value, value_state, last_edited_by, last_edited_at, "
    "suggestion_id FROM sheet_cells "
    "WHERE sheet_id = :s AND (CAST(:ids AS uuid[]) IS NULL OR row_id = ANY(CAST(:ids AS uuid[])))"
)


async def _row_views(
    ctx: AuthContext, sheet: _Sheet, columns: Mapping[str, Column], ids: Sequence[UUID] | None
) -> list[SheetRow]:
    by_id = {c.id: c for c in columns.values()}
    params = {"s": sheet.id, "ids": None if ids is None else list(ids)}
    async with tenant_session(ctx.tenant) as session:
        rows = list(await session.execute(_ROWS, params))
        cells = list(await session.execute(_CELLS, params))
    grid: dict[UUID, dict[str, Cell]] = {r.id: {} for r in rows}
    for c in cells:
        column = by_id.get(c.column_id)
        if column is None or c.row_id not in grid:
            continue
        shown = _shown(cast(Mapping[str, object] | None, c.value))
        grid[c.row_id][column.key] = Cell(
            shown, str(c.value_state), c.last_edited_by, c.last_edited_at,
            _exception(column, shown), c.suggestion_id,
        )  # fmt: skip
    hashes = {
        r.id: content_hash({k: v.value for k, v in sorted(grid[r.id].items())}) for r in rows
    }
    states = (
        await sign_off_states(ctx.tenant, TARGET, [r.id for r in rows], hashes) if rows else {}
    )
    return [
        SheetRow(
            r.id, str(r.row_key), str(r.section_key or ""), int(r.position), int(r.row_version),
            any(s.level >= 2 and s.signed_by is not None and not s.stale
                for s in states.get(r.id, [])),
            grid[r.id],
        )
        for r in rows
    ]  # fmt: skip


_VIEWS: Final = text(
    "SELECT id, view_key, name, filters, sort, visible_columns FROM sheet_views "
    "WHERE sheet_id = :s AND (shared OR created_by = :me) ORDER BY view_key = 'default' DESC, "
    "name, id"
)


async def views(ctx: AuthContext, sheet_id: UUID) -> list[SheetView]:
    await _sheet(ctx, sheet_id, "sheet.read")
    async with tenant_session(ctx.tenant) as session:
        found = list(await session.execute(_VIEWS, {"s": sheet_id, "me": ctx.user_id}))
    return [
        SheetView(
            r.id, str(r.view_key), str(r.name),
            tuple(cast(list[Mapping[str, str]], r.filters or [])),
            tuple(cast(list[Mapping[str, str]], r.sort or [])),
            tuple(r.visible_columns or ()),
        )
        for r in found
    ]  # fmt: skip


def _passes(row: SheetRow, columns: Mapping[str, Column], rule: Mapping[str, str]) -> bool:
    key, op, want = rule.get("column", ""), rule.get("op", "is"), rule.get("value", "")
    if key == "exception":
        return any(c.exception for c in row.cells.values()) == (want != "false")
    have = row.cells.get(key, _EMPTY).value
    if op == "is_empty":
        return have == ""
    if op == "is":
        return have == want
    if op == "is_not":
        return have != want
    column = columns.get(key)
    if column is None or column.type not in _DECIMAL_TYPES or have == "":
        return False
    try:
        left, right = Decimal(have), Decimal(want)
    except InvalidOperation:
        return False
    return {"gte": left >= right, "lte": left <= right, "gt": left > right,
            "lt": left < right}.get(op, False)  # fmt: skip


def apply_view(
    found: Sequence[SheetRow], columns: Mapping[str, Column], view: SheetView | None
) -> list[SheetRow]:
    """A view's filters (AND) and sort, by code."""
    if view is None:
        return list(found)
    out = [r for r in found if all(_passes(r, columns, f) for f in view.filters)]
    for rule in reversed(view.sort):
        key, descending = rule.get("column", ""), rule.get("dir") == "desc"
        column = columns.get(key)

        def sort_key(r: SheetRow, k: str = key, c: Column | None = column) -> tuple[int, object]:
            shown = r.cells.get(k, _EMPTY).value
            if c is not None and c.type in _DECIMAL_TYPES and shown:
                return (0, Decimal(shown))
            return (0 if shown else 1, shown)

        out.sort(key=sort_key, reverse=descending)
    return out


async def rows(
    ctx: AuthContext, sheet_id: UUID, view_id: UUID | None = None
) -> tuple[list[SheetRow], SheetView | None]:
    sheet = await _sheet(ctx, sheet_id, "sheet.read")
    async with tenant_session(ctx.tenant) as session:
        columns = {c.key: c for c in await _columns(session, sheet_id)}
    chosen = None
    if view_id is not None:
        chosen = next((v for v in await views(ctx, sheet_id) if v.id == view_id), None)
        if chosen is None:
            raise NotFound("sheet_view")
    return apply_view(await _row_views(ctx, sheet, columns, None), columns, chosen), chosen


_SECTIONS: Final = text(
    "SELECT section_key, title, totals_spec FROM sheet_sections WHERE sheet_id = :s "
    "ORDER BY position, section_key"
)


def totals(
    sections: Sequence[tuple[str, str, Mapping[str, object]]],
    found: Sequence[SheetRow],
    columns: Sequence[Column],
) -> list[SheetSection]:
    """Per section: its rows and the sum of its total column (code's arithmetic, ADR-050)."""
    default = next((c.key for c in columns if c.type == "currency"), None)
    out: list[SheetSection] = []
    for key, title, spec in sections:
        mine = [r for r in found if r.section_key == key]
        column = spec.get("sum") if isinstance(spec.get("sum"), str) else default
        total: Decimal | None = None
        if column is not None:
            total = sum(
                (Decimal(r.cells[cast(str, column)].value) for r in mine
                 if r.cells.get(cast(str, column), _EMPTY).value),
                Decimal("0.00"),
            ).quantize(Decimal("0.01"))  # fmt: skip
        out.append(SheetSection(key, title, len(mine), total))
    return out


async def sheet_vm(ctx: AuthContext, sheet_id: UUID, view_id: UUID | None = None) -> SheetVm:
    sheet = await _sheet(ctx, sheet_id, "sheet.read")
    async with tenant_session(ctx.tenant) as session:
        columns = await _columns(session, sheet_id)
        sections = [
            (str(r.section_key), str(r.title), cast(Mapping[str, object], r.totals_spec or {}))
            for r in await session.execute(_SECTIONS, {"s": sheet_id})
        ]
    seed: int | None = None
    if sheet.sample_set_id is not None and sheet.sample_version is not None:
        seed = await version_seed(ctx.tenant, sheet.sample_set_id, sheet.sample_version)
    found, view = await rows(ctx, sheet_id, view_id)
    return SheetVm(
        sheet.id, sheet.work_item_id, sheet.title, tuple(columns),
        tuple(totals(sections, found, columns)), len(found),
        sum(1 for r in found if any(c.exception for c in r.cells.values())),
        "Default" if view is None else view.name, seed, sheet.engagement_id,
    )  # fmt: skip


def status_line(vm: SheetVm, tested: int = 0) -> str:
    """SHT-01's status bar: "40 rows · 0 tested · seed 0x7C31B4" (a zero-row sheet: "0 rows ·
    View: Default")."""
    if vm.rows == 0:
        return f"0 rows · View: {vm.view}"
    parts = [f"{vm.rows} row{'s' if vm.rows != 1 else ''}", f"{tested} tested"]
    if vm.sample_seed is not None:
        parts.append(f"seed 0x{vm.sample_seed:06X}")
    return " · ".join(parts)


# --- views ---------------------------------------------------------------------------------------


def _view_key(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", name.casefold()).strip("_")[:50] or "view"
    return slug if slug[0].isalpha() else f"v_{slug}"


async def save_view(
    ctx: AuthContext,
    sheet_id: UUID,
    name: str,
    filters: Sequence[Mapping[str, str]],
    sort: Sequence[Mapping[str, str]],
    columns_off: Sequence[str],
    view_id: UUID | None = None,
) -> UUID:
    """A new shared view, or a change to one (server-stored, URL-addressable by id)."""
    sheet = await _sheet(ctx, sheet_id, "sheet.edit")
    values = {"name": name.strip()[:80], "filters": json.dumps(list(map(dict, filters))),
              "sort": json.dumps(list(map(dict, sort))), "off": list(columns_off)}  # fmt: skip
    async with uow(ctx.tenant) as tx:
        if view_id is None:
            view_id = uuid4()
            await tx.session.execute(
                _INSERT_VIEW,
                values | {"id": view_id, "t": ctx.tenant_id, "e": sheet.engagement_id,
                          "w": sheet.work_item_id, "s": sheet_id,
                          "key": f"{_view_key(name)}_{uuid4().hex[:4]}", "by": ctx.user_id,
                          "shared": True},
            )  # fmt: skip
        else:
            found = await tx.session.scalar(
                text("UPDATE sheet_views SET name = :name, filters = CAST(:filters AS jsonb), "
                     "sort = CAST(:sort AS jsonb), visible_columns = :off, version = version + 1 "
                     "WHERE id = :id AND sheet_id = :s RETURNING id"),
                values | {"id": view_id, "s": sheet_id},
            )  # fmt: skip
            if found is None:
                raise NotFound("sheet_view")
        tx.record(
            "sheet_view.saved",
            target=Target("sheet", sheet_id),
            after=Ref(view=view_id, filters=len(filters)),
            scope=Scope(engagement_id=sheet.engagement_id, work_item_id=sheet.work_item_id),
        )
    return view_id


# --- row links -----------------------------------------------------------------------------------

LinkKind = Literal["evidence", "request", "risk"]


async def link_row(ctx: AuthContext, sheet_id: UUID, row_id: UUID, kind: LinkKind,
                   target_id: UUID) -> None:  # fmt: skip
    """A row's link to evidence, a request or a risk (SHT-01's drawer tabs); idempotent."""
    sheet = await _sheet(ctx, sheet_id, "sheet.edit")
    async with uow(ctx.tenant) as tx:
        await tx.session.execute(
            text("INSERT INTO sheet_row_links (tenant_id, engagement_id, work_item_id, sheet_id, "
                 "row_id, kind, target_id, linked_by) SELECT :t, :e, :w, :s, :r, :k, :target, "
                 ":by WHERE EXISTS (SELECT 1 FROM sheet_rows WHERE id = :r AND sheet_id = :s) "
                 "ON CONFLICT (tenant_id, row_id, kind, target_id) DO NOTHING"),
            {"t": ctx.tenant_id, "e": sheet.engagement_id, "w": sheet.work_item_id,
             "s": sheet_id, "r": row_id, "k": kind, "target": target_id, "by": ctx.user_id},
        )  # fmt: skip
        tx.record(
            "sheet_row.linked",
            target=Target("sheet_row", row_id),
            after=Ref(target=target_id),  # the link kind is the row link's own column
            scope=Scope(engagement_id=sheet.engagement_id, work_item_id=sheet.work_item_id),
        )


@dataclass(frozen=True)
class SheetScope:
    engagement_id: UUID
    work_item_id: UUID


async def sheet_scope(ctx: AuthContext, sheet_id: UUID) -> SheetScope:
    """A sheet's engagement and work item, after `sheet.read` (the comment anchors' check)."""
    found = await _sheet(ctx, sheet_id, "sheet.read")
    return SheetScope(found.engagement_id, found.work_item_id)


# --- K-03-T22: SHT-01's row drawer --------------------------------------------------------------

# Columns the drawer's Details card draws as facts; links, sign-offs and the agent's own column
# have their tabs and the Why card (DEC-6033).
_FACT_TYPES: Final = frozenset({"text", "number", "currency", "date", "single_select", "person"})


@dataclass(frozen=True)
class RowFact:
    label: str
    type: str
    value: str


@dataclass(frozen=True)
class RowWhy:
    """The agent's reason for one suggested cell, as the agents module serves it (agent text)."""

    column_key: str
    suggestion_id: UUID
    status: str
    version: int
    rationale: str | None
    citation_count: int
    agent_run_id: UUID | None


@dataclass(frozen=True)
class RowLink:
    kind: str
    target_id: UUID
    linked_at: datetime
    label: str | None


@dataclass(frozen=True)
class RowDetail:
    engagement_id: UUID
    row: SheetRow
    facts: list[RowFact]
    why: list[RowWhy]
    links: list[RowLink]


_LINKS: Final = text(
    "SELECT kind, target_id, linked_at FROM sheet_row_links WHERE sheet_id = :s AND row_id = :r "
    "ORDER BY kind, linked_at, target_id"
)


async def _why(ctx: AuthContext, column: Column, cell: Cell) -> RowWhy | None:
    from abacus.modules.agents.api import suggestion_view

    if cell.suggestion_id is None:
        return None
    try:
        found = await suggestion_view(ctx, cell.suggestion_id)
    except (NotFound, Forbidden):
        return None  # a walled suggestion: no reason and no hidden count (INV-3)
    return RowWhy(column.key, found.id, found.status, found.version, found.rationale,
                  len(found.citation_ids), found.agent_run_id)  # fmt: skip


async def row_detail(ctx: AuthContext, sheet_id: UUID, row_id: UUID) -> RowDetail:
    """One row as SHT-01's drawer reads it (K-03-T22, DEC-6033): its facts in column order, the
    agent's reason for each suggested cell, and the evidence, requests and risks it links to.
    Values are stored text; the browser formats them by type, as the grid does."""
    from abacus.modules.evidence.api import version_display_name

    sheet = await _sheet(ctx, sheet_id, "sheet.read")
    async with tenant_session(ctx.tenant) as session:
        ordered = await _columns(session, sheet_id)
        linked = list(await session.execute(_LINKS, {"s": sheet_id, "r": row_id}))
    found = await _row_views(ctx, sheet, {c.key: c for c in ordered}, [row_id])
    if not found:
        raise NotFound("sheet_row")
    row = found[0]
    facts = [
        RowFact(c.name, c.type, row.cells[c.key].value if c.key in row.cells else "")
        for c in ordered
        if c.type in _FACT_TYPES
    ]
    why = [
        w
        for c in ordered
        if c.key in row.cells
        for w in [await _why(ctx, c, row.cells[c.key])]
        if w is not None
    ]
    links = [
        RowLink(
            str(link.kind), link.target_id, link.linked_at,
            await version_display_name(ctx.tenant, link.target_id)
            if link.kind == "evidence" else None,
        )
        for link in linked
    ]  # fmt: skip
    return RowDetail(sheet.engagement_id, row, facts, why, links)


__all__ = [
    "CellInvalid",
    "NoTemplateLink",
    "RowDetail",
    "RowLocked",
    "SampleAlreadyLinked",
    "SheetRow",
    "SheetVm",
    "add_row",
    "add_rows_from_sample",
    "apply_view",
    "create_sheet",
    "edit_row",
    "link_row",
    "row_detail",
    "rows",
    "save_view",
    "sheet_scope",
    "sheet_vm",
    "status_line",
    "totals",
    "typed",
    "views",
]
