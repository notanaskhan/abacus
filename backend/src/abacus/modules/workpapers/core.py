"""The A-04 workpaper core service (A-04-T04, TASK-2711; A-04 §3.1, §4.3; DEC-1762).

On SPEC-308's insert-only store (0072, widened by 0581): a paper with an A-04 `kind`, its sections,
cells (the newest row per sheet and cell is the value) and numbered versions.

- **Projection** (`record`): sections with their state, cells with tick and suggestion state and
  the citation ids, attention flags, the sign-off ladder (staleness from the owner's content hash,
  C3) and `allowed_actions`, at the current version or an earlier one (each cell row carries the
  version it was written in).
- **Cell edits** (`edit_cells`): the caller names the version it read (`expected_version`, 409
  `version_conflict`); overriding an agent value needs a reason (422 `reason_required`). Each cell
  goes through `review.api.record_value` (the field history, SHL-09) and appends its cell row;
  the edit makes the next version (`cause` edit) and emits `workpaper.version_created`, so an
  earlier sign-off reads stale.
- **Export** (`export_xlsx`): byte-identical for identical data (ADR-042: fixed properties and ZIP
  time), client strings written as text, never formulas (ADR-052); audited `workpaper.exported`.
- **Citable** (`workpaper_cell`, C4): `{sheet_id, sheet_key?, row_key, column_key,
  sheet_version?}`; the verifier authorises `workpaper.read` on the paper's engagement, which must
  be the anchor's, and checks a claimed value or quote against the cell by code.
- **Field owner** (`workpaper_cell`): a cell's current typed value for SHL-09; a tray edit lands as
  the cell's next row.
"""

from __future__ import annotations

import hashlib
import io
import re
import zipfile
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Final, cast
from uuid import UUID

from openpyxl import Workbook
from openpyxl.worksheet.worksheet import Worksheet
from sqlalchemy.ext.asyncio import AsyncSession

from abacus.kernel._statuses import (
    AttentionFlagStatus,
    AuditSectionStatus,
    WorkpaperValueStateStatus,
)
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork, uow
from abacus.modules.engagements.api import engagement_resource_of, get_ref, lock_ref
from abacus.modules.evidence.api import (
    CitationAnchor,
    CitationClaim,
    CitationLabel,
    CitationVerdict,
    normalised_text,
)
from abacus.modules.identity.api import (
    Actor,
    AuthContext,
    Forbidden,
    allowed_actions,
    authorise,
    engagement_team,
)
from abacus.modules.review.api import FieldOwner, ReviewableFacts, record_value, sign_off_states
from abacus.modules.workpapers.contract import (
    AttentionFlagOut,
    CellsEditIn,
    SectionStateOut,
    SignOffRungOut,
    TypedValue,
    WorkpaperAction,
    WorkpaperCellOut,
    WorkpaperKind,
    WorkpaperRecordOut,
    WorkpaperStateOut,
    WorkpaperVersionOut,
)
from abacus.modules.workpapers.events import WorkpaperContentChanged, WorkpaperVersionCreated
from abacus.modules.workpapers.layouts import designed_layout, is_cell_key
from abacus.modules.workpapers.models import (
    AttentionFlag,
    Workpaper,
    WorkpaperCell,
    WorkpaperCellCitation,
    WorkpaperSection,
)
from abacus.modules.workpapers.repository import (
    cells_up_to,
    citations_of,
    core_papers,
    flags_of,
    get_workpaper,
    insert_cells,
    insert_version,
    next_version_no,
    sections_for,
    sections_of,
    versions_of,
)
from abacus.modules.workpapers.service import (
    SHEET,
    TARGET,
    cell_ref,
    content_hash,
    content_of,
    is_filled,
    status_of,
    tb_link,
    workpaper_facts,
)

CELL_TARGET: Final = "workpaper_cell"
SOURCE: Final = "workpaper_sheet"
NIL: Final = UUID(int=0)
RUNGS: Final = {1: "L1", 2: "L2", 3: "L3", 4: "L4", 5: "EQR"}
CANDIDATES: Final[tuple[WorkpaperAction, ...]] = (
    "workpaper.edit",
    "workpaper.draft",
    "workpaper.export",
    "attention_flag.convert",
    "sign_off.prepare",
    "sign_off.review",
)
# Types the field history takes (review's four); a percent is a decimal there, an empty cell a
# text with no value.
_HISTORY_TYPE: Final = {"percent": "decimal", "empty": "text"}
_FORMULA_LEAD: Final = ("=", "+", "-", "@", "\t", "\r")
_ZIP_TIME: Final = (1980, 1, 1, 0, 0, 0)
_EPOCH: Final = datetime(2026, 1, 1)
_A1: Final = re.compile(r"^([A-Z]{1,2})([1-9][0-9]{0,3})$")
_SHEET_KEY: Final = re.compile(r"^[a-z][a-z0-9_]{0,39}$")
_PART: Final = re.compile(r"^[A-Za-z0-9_]{1,40}$")
_PLAIN_NOTE: Final = "Entered on the workpaper"
XLSX: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class VersionConflict(DomainConflict):
    """The paper moved on since the caller read it (AC1.6)."""

    code = "version_conflict"


class ReasonRequired(DomainInvalid):
    """Overriding an agent value needs the person's reason (AC1.6)."""

    code = "reason_required"


class CellInvalid(DomainInvalid):
    code = "workpaper_invalid"


@dataclass(frozen=True)
class _Loaded:
    paper: Workpaper
    sections: Sequence[WorkpaperSection]
    cells: Sequence[WorkpaperCell]
    citations: Sequence[WorkpaperCellCitation]
    flags: Sequence[AttentionFlag]
    version_no: int
    current_version_no: int


def _core(paper: Workpaper | None, engagement_id: UUID) -> Workpaper:
    """An A-04 paper (one with a kind) on this engagement, else 404."""
    if paper is None or paper.engagement_id != engagement_id or paper.kind is None:
        raise NotFound("workpaper")
    return paper


async def _load(
    session: AsyncSession, engagement_id: UUID, workpaper_id: UUID, version: int | None
) -> _Loaded:
    paper = _core(await get_workpaper(session, workpaper_id), engagement_id)
    current = await next_version_no(session, paper.id) - 1
    if version is not None and not 1 <= version <= current:
        raise NotFound("workpaper_version")
    at = version if version is not None and version != current else None
    cells = await cells_up_to(session, paper.id, at)
    citations = await citations_of(session, [paper.id])
    return _Loaded(
        paper,
        await sections_of(session, paper.id),
        cells,
        citations,
        await flags_of(session, paper.id),
        version if version is not None else current,
        current,
    )


def _typed(cell: WorkpaperCell) -> TypedValue:
    if cell.value is not None:
        raw = cell.value.get("v")
        return TypedValue(t=cast(str, cell.value.get("t")), v=None if raw is None else str(raw))  # pyright: ignore[reportArgumentType] -- checked by the CHECK and the edit path
    if cell.raw is None:
        return TypedValue(t="empty", v=None)
    return TypedValue(t="text", v=cell.raw)


def _cell_out(cell: WorkpaperCell, citations: Sequence[WorkpaperCellCitation]) -> WorkpaperCellOut:
    return WorkpaperCellOut(
        sheet_key=cell.sheet_key,
        cell_key=cell.cell_key,
        section_key=cell.section_key,
        row_key=cell.row_key,
        col_key=cell.col_key,
        value=_typed(cell),
        value_source=cell.value_source,  # pyright: ignore[reportArgumentType] -- the CHECK's set
        value_state=WorkpaperValueStateStatus(cell.value_state),
        suggestion_id=cell.suggestion_id,
        tickmarks=sorted(cell.tickmarks),
        citation_ids=[
            c.id for c in citations if (c.sheet_key, c.cell_key) == (cell.sheet_key, cell.cell_key)
        ],
        updated_version_no=max(cell.updated_version_no or 1, 1),
    )


def _sections(
    sections: Sequence[WorkpaperSection], cells: Sequence[WorkpaperCell], paper_state: str
) -> list[SectionStateOut]:
    """A section with content shows the paper's state; one without, Not started. Waiting on
    inputs arrives with the drafter's output (A-04-T11)."""
    out: list[SectionStateOut] = []
    for s in sections:
        mine = [
            c
            for c in cells
            if is_filled(c)
            and (
                c.section_key == s.sheet_key
                or (s.band_kind == "sheet" and c.sheet_key == s.sheet_key)
            )
        ]
        out.append(
            SectionStateOut(
                key=s.sheet_key,
                title=s.title,
                band_kind=s.band_kind,  # pyright: ignore[reportArgumentType] -- the CHECK's set
                sheet_key=s.sheet_key if s.band_kind == "sheet" else None,
                state=AuditSectionStatus(paper_state) if mine else AuditSectionStatus.NOT_STARTED,
                waiting_on_request_ids=[],
            )
        )
    return out


def _flag_out(flag: AttentionFlag) -> AttentionFlagOut:
    return AttentionFlagOut(
        id=flag.id,
        section_key=flag.section_key,
        row_key=flag.row_key,
        kind="pbc_gap",
        text=flag.text,
        state=AttentionFlagStatus(flag.state),
        converted_to_kind=flag.converted_to_kind,  # pyright: ignore[reportArgumentType] -- CHECK
        converted_to_id=flag.converted_to_id,
    )


def _initials(name: str | None) -> str | None:
    if not name:
        return None
    return "".join(part[0] for part in name.split() if part[:1].isalpha())[:3].upper() or None


async def record(
    ctx: AuthContext,
    engagement_id: UUID,
    workpaper_id: UUID,
    *,
    tab: str | None,
    version: int | None,
) -> WorkpaperRecordOut:
    """AUD-04 a-f, AUD-05, AUD-09: the record projection (the route authorised the read)."""
    ref = await get_ref(ctx, engagement_id)
    async with tenant_session(ctx.tenant) as session:
        loaded = await _load(session, engagement_id, workpaper_id, version)
    tb = await tb_link(ctx.tenant, engagement_id)
    digest = content_hash(content_of(loaded.cells, loaded.citations, tb))
    current_cells = loaded.cells
    if loaded.version_no != loaded.current_version_no:
        async with tenant_session(ctx.tenant) as session:
            current_cells = await cells_up_to(session, loaded.paper.id, None)
    live = content_hash(content_of(current_cells, loaded.citations, tb))
    states = (
        await sign_off_states(ctx.tenant, TARGET, [loaded.paper.id], {loaded.paper.id: live})
    )[loaded.paper.id]
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    paper_state = status_of(any(is_filled(c) for c in current_cells), states)
    sections = _sections(loaded.sections, loaded.cells, paper_state)
    shown = [c for c in loaded.cells if tab is None or c.sheet_key == tab or c.section_key == tab]
    resource = ref.resource()
    actions = await allowed_actions(ctx, resource, CANDIDATES)
    if loaded.version_no != loaded.current_version_no:
        actions = actions & {"workpaper.export"}  # an earlier version is read-only
    return WorkpaperRecordOut(
        id=loaded.paper.id,
        code=loaded.paper.code,
        kind=cast(WorkpaperKind, loaded.paper.kind),
        title=loaded.paper.title,
        audit_area=loaded.paper.audit_area,
        program_step_keys=list(loaded.paper.program_step_keys),
        version_no=loaded.version_no,
        current_version_no=loaded.current_version_no,
        content_hash=digest,
        tab=tab,
        sections=sections,
        cells=[
            _cell_out(c, loaded.citations)
            for c in shown
            if is_filled(c) or c.value_state != "human"
        ],
        flags=[_flag_out(f) for f in loaded.flags if tab is None or f.section_key == tab],
        sign_offs=[
            SignOffRungOut(
                level=RUNGS[s.level],  # pyright: ignore[reportArgumentType] -- the five rungs
                initials=_initials(names.get(s.signed_by)) if s.signed_by else None,
                signed_at=s.signed_at,
                stale=s.stale,
            )
            for s in states
        ],
        allowed_actions=[a for a in CANDIDATES if a in actions],
    )


async def states(
    ctx: AuthContext, engagement_id: UUID, kind: WorkpaperKind | None
) -> list[WorkpaperStateOut]:
    """`GET …/workpaper-states`: every A-04 paper with its sections' states (the cockpit rail)."""
    async with tenant_session(ctx.tenant) as session:
        papers = [
            p
            for p in await core_papers(session, ctx, engagement_id)
            if kind is None or p.kind == kind
        ]
        ids = [p.id for p in papers]
        sections = await sections_for(session, ids)
        cells = {p.id: await cells_up_to(session, p.id, None) for p in papers}
        citations = await citations_of(session, ids)
        versions = {p.id: await next_version_no(session, p.id) - 1 for p in papers}
    if not papers:
        return []
    tb = await tb_link(ctx.tenant, engagement_id)
    hashes = {
        p.id: content_hash(
            content_of(cells[p.id], [c for c in citations if c.workpaper_id == p.id], tb)
        )
        for p in papers
    }
    ladder = await sign_off_states(ctx.tenant, TARGET, ids, hashes)
    out: list[WorkpaperStateOut] = []
    for p in papers:
        state = status_of(any(is_filled(c) for c in cells[p.id]), ladder[p.id])
        out.append(
            WorkpaperStateOut(
                id=p.id,
                code=p.code,
                kind=cast(WorkpaperKind, p.kind),
                title=p.title,
                current_version_no=versions[p.id],
                sections=_sections(
                    [s for s in sections if s.workpaper_id == p.id], cells[p.id], state
                ),
            )
        )
    return out


async def versions(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID
) -> list[WorkpaperVersionOut]:
    """Newest first, with the producer: "<person> via Agent" for a draft (INV-5)."""
    async with tenant_session(ctx.tenant) as session:
        paper = _core(await get_workpaper(session, workpaper_id), engagement_id)
        rows = await versions_of(session, paper.id)
    names = {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}
    return [
        WorkpaperVersionOut(
            version_no=v.version_no,
            content_hash=v.content_hash,
            produced_by_kind=v.produced_by_kind,  # pyright: ignore[reportArgumentType] -- CHECK
            agent_run_id=v.agent_run_id,
            created_by_name=names.get(v.created_by, "Former member"),
            on_behalf_of_name=(
                names.get(v.on_behalf_of_user_id, "Former member")
                if v.on_behalf_of_user_id is not None
                else None
            ),
            cause=v.cause or "edit",  # pyright: ignore[reportArgumentType] -- CHECK
            created_at=v.created_at,
        )
        for v in rows
    ]


def _history_value(value: TypedValue) -> dict[str, object]:
    return {"t": _HISTORY_TYPE.get(value.t, value.t), "v": value.v}


def _checked_value(value: TypedValue) -> dict[str, object]:
    """By code: a decimal or percent is a finite decimal string; empty has no value."""
    if value.t == "empty":
        return {"t": "empty", "v": None}
    if value.v is not None and value.t in ("decimal", "percent"):
        try:
            number = Decimal(value.v)
        except InvalidOperation:
            raise CellInvalid(facts={"field": "value"}) from None
        if not number.is_finite():
            raise CellInvalid(facts={"field": "value"})
    if value.v is not None and value.t == "bool" and value.v not in ("true", "false"):
        raise CellInvalid(facts={"field": "value"})
    return {"t": value.t, "v": value.v}


def _structure(cell_key: str) -> tuple[str | None, str | None, str | None]:
    """A structured key "S1.R3.value" names its section, row and column; an A1 key none."""
    parts = cell_key.split(".")
    if len(parts) == 3:
        return parts[0].lower(), parts[1], parts[2]
    return None, None, None


async def edit_cells(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID, body: CellsEditIn
) -> int:
    """AC1.6, AC1.3: the edit as the paper's next version. Returns the new version number."""
    seen: set[tuple[str, str]] = set()
    for c in body.cells:
        if (c.sheet_key, c.cell_key) in seen:
            raise CellInvalid(facts={"field": "cells"})
        seen.add((c.sheet_key, c.cell_key))
    tb = await tb_link(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "workpaper.edit", ref.resource())
        paper = _core(await get_workpaper(tx.session, workpaper_id), engagement_id)
        current = await next_version_no(tx.session, paper.id) - 1
        if body.expected_version != current:
            raise VersionConflict(facts={"current_version": current})
        now = {(c.sheet_key, c.cell_key): c for c in await cells_up_to(tx.session, paper.id, None)}
        version_no = current + 1
        rows: list[dict[str, object]] = []
        for c in body.cells:
            old = now.get((c.sheet_key, c.cell_key))
            from_agent = old is not None and (
                old.value_source == "agent" or old.value_state in ("suggested", "adopted")
            )
            reason = (c.reason or "").strip()
            if from_agent and not reason:
                raise ReasonRequired
            value = _checked_value(c.value)
            section, row, col = _structure(c.cell_key)
            await record_value(
                tx,
                engagement_id=engagement_id,
                target_type=CELL_TARGET,
                target_id=paper.id,
                field_key=cell_ref(c.sheet_key, c.cell_key),
                value=_history_value(c.value),
                value_source="human",
                cause="edit",
                # A plain entry's note is where it was entered; an override carries the reason.
                citation_note=reason or _PLAIN_NOTE,
            )
            rows.append(
                {
                    "tenant_id": ctx.tenant_id,
                    "workpaper_id": paper.id,
                    "sheet_key": c.sheet_key,
                    "cell_key": c.cell_key,
                    "raw": None if value["v"] is None else str(value["v"]),
                    "value_source": "human",
                    "tickmarks": list(old.tickmarks) if old is not None else [],
                    "set_by": ctx.user_id,
                    "section_key": old.section_key if old is not None else section,
                    "row_key": old.row_key if old is not None else row,
                    "col_key": old.col_key if old is not None else col,
                    "value": value,
                    "value_state": "edited" if from_agent else "human",
                    "classification": old.classification if old is not None else "confidential",
                    "updated_version_no": version_no,
                }
            )
        await insert_cells(tx.session, rows)
        cells = await cells_up_to(tx.session, paper.id, None)
        citations = await citations_of(tx.session, [paper.id])
        content = content_of(cells, citations, tb)
        await insert_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            workpaper_id=paper.id,
            version_no=version_no,
            content_hash=content_hash(content),
            content=content,
            created_by=ctx.user_id,
            produced_by_kind="human",
            cause="edit",
        )
        tx.record(
            "workpaper.cells_edited",
            target=Target(TARGET, paper.id),
            after=Ref(version=version_no, cells=len(rows)),
        )
        tx.emit(WorkpaperContentChanged(workpaper_id=paper.id, engagement_id=engagement_id))
        tx.emit(
            WorkpaperVersionCreated(
                workpaper_id=paper.id,
                engagement_id=engagement_id,
                work_item_id=paper.work_item_id,
                version_no=version_no,
            )
        )
    return version_no


# --- export (ADR-042, ADR-052) ---------------------------------------------------------------


def _write(ws: Worksheet, row: Sequence[object]) -> None:
    ws.append(list(row))
    for cell in ws[ws.max_row]:
        if isinstance(cell.value, str) and cell.value.startswith(_FORMULA_LEAD):
            cell.data_type = "s"  # client text stays text: never evaluated as a formula


def _rebuild(raw: bytes) -> bytes:
    out = io.BytesIO()
    with (
        zipfile.ZipFile(io.BytesIO(raw)) as source,
        zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as target,
    ):
        for name in sorted(source.namelist()):
            entry = zipfile.ZipInfo(name, date_time=_ZIP_TIME)
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o644 << 16
            entry.create_system = 3
            target.writestr(entry, source.read(name))
    return out.getvalue()


def workbook(view: WorkpaperRecordOut, titles: Mapping[str, str]) -> bytes:
    """The paper at one version: a cover sheet, then one sheet per sheet key, cells by key."""
    book = Workbook()
    cover = book.active
    if cover is None:  # a new Workbook always has its first sheet
        cover = book.create_sheet()
    cover.title = "Workpaper"
    for label, value in (
        ("Workpaper", view.code),
        ("Title", view.title),
        ("Kind", view.kind),
        ("Audit area", view.audit_area or ""),
        ("Version", str(view.version_no)),
        ("Content hash", view.content_hash),
    ):
        _write(cover, (label, value))
    by_sheet: dict[str, list[WorkpaperCellOut]] = {}
    for cell in view.cells:
        by_sheet.setdefault(cell.sheet_key, []).append(cell)
    # A-05-T09 (SPEC-641): a designed paper writes each cell at its own address on its sheet, so
    # `EBP-04!C14` in the app is C14 on sheet "EBP-04" in Excel; anything else stays a list.
    layout = designed_layout(view.kind)
    if layout is not None:
        for placed in layout.sheets:
            sheet = book.create_sheet(placed.title)
            for c in sorted(by_sheet.pop(placed.sheet_key, []), key=lambda c: c.cell_key):
                if is_cell_key(c.cell_key):
                    sheet[c.cell_key] = c.value.v or ""
    for sheet_key in sorted(by_sheet):
        title = re.sub(r"[\[\]:*?/\\]", " ", titles.get(sheet_key, sheet_key))[:31] or sheet_key
        sheet = book.create_sheet(title if title not in book.sheetnames else sheet_key[:31])
        _write(
            sheet,
            ("Cell", "Section", "Row", "Column", "Type", "Value", "Source", "State", "Tickmarks"),
        )
        for c in sorted(by_sheet[sheet_key], key=lambda c: c.cell_key):
            _write(
                sheet,
                (
                    c.cell_key,
                    c.section_key or "",
                    c.row_key or "",
                    c.col_key or "",
                    c.value.t,
                    c.value.v or "",
                    c.value_source,
                    c.value_state,
                    ", ".join(c.tickmarks),
                ),
            )
    props = book.properties
    props.creator = "abacus"
    props.lastModifiedBy = "abacus"
    props.title = view.code
    props.created = _EPOCH
    props.modified = _EPOCH
    raw = io.BytesIO()
    book.save(raw)
    return _rebuild(raw.getvalue())


async def export_xlsx(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID, version: int | None
) -> tuple[bytes, str]:
    """AC1.7: "Open in Excel". Returns the bytes and the file name."""
    view = await record(ctx, engagement_id, workpaper_id, tab=None, version=version)
    async with tenant_session(ctx.tenant) as session:
        titles = {s.sheet_key: s.title for s in await sections_of(session, view.id)}
    data = workbook(view, titles)
    async with uow(ctx.tenant) as tx:
        tx.record(
            "workpaper.exported",
            target=Target(TARGET, view.id),
            after=Ref(version=view.version_no, sha256=hashlib.sha256(data).hexdigest()),
        )
    return data, f"{view.code}-v{view.version_no}.xlsx"


# --- the `workpaper_cell` citable (C4 §3.1; ADR-166) ---------------------------------------------


@dataclass(frozen=True)
class _CellAt:
    sheet_id: UUID
    sheet_key: str
    row_key: str
    column_key: str
    sheet_version: int | None


def _cell_locator(locator: Mapping[str, object]) -> _CellAt | None:
    raw_id, sheet = locator.get("sheet_id"), locator.get("sheet_key", SHEET)
    row, col, version = (
        locator.get("row_key"),
        locator.get("column_key"),
        locator.get("sheet_version"),
    )
    if (
        not isinstance(raw_id, str)
        or not isinstance(sheet, str)
        or not _SHEET_KEY.fullmatch(sheet)
    ):
        return None
    if not isinstance(row, str) or not isinstance(col, str):
        return None
    if not _PART.fullmatch(row) or not _PART.fullmatch(col):
        return None
    if version is not None and (
        not isinstance(version, int) or isinstance(version, bool) or version < 1
    ):
        return None
    try:
        return _CellAt(UUID(raw_id), sheet, row, col, version)
    except ValueError:
        return None


def _matches(cell: WorkpaperCell, at: _CellAt) -> bool:
    if cell.sheet_key != at.sheet_key:
        return False
    a1 = _A1.fullmatch(cell.cell_key)
    if a1 is not None:
        return (a1.group(1), a1.group(2)) == (at.column_key.upper(), at.row_key)
    return (cell.row_key, cell.col_key) == (at.row_key, at.column_key)


def _amount(text: str) -> Decimal | None:
    cleaned = text.replace(",", "").replace("$", "").strip()
    negative = cleaned.startswith("(") and cleaned.endswith(")")
    try:
        number = Decimal(cleaned.strip("()"))
    except InvalidOperation:
        return None
    return -number if negative else number


def _locator_out(at: _CellAt) -> dict[str, object]:
    out: dict[str, object] = {
        "sheet_id": str(at.sheet_id),
        "sheet_key": at.sheet_key,
        "row_key": at.row_key,
        "column_key": at.column_key,
    }
    if at.sheet_version is not None:
        out["sheet_version"] = at.sheet_version
    return out


async def _may_read(ctx: AuthContext, engagement_id: UUID) -> bool:
    try:
        await authorise(
            ctx, "workpaper.read", await engagement_resource_of(ctx.tenant, engagement_id)
        )
    except (Forbidden, NotFound):
        return False
    return True


async def verify_workpaper_cell(
    tx: UnitOfWork, actor: Actor, claim: CitationClaim, anchor: CitationAnchor
) -> CitationVerdict:
    at = _cell_locator(claim.locator)
    if at is None:
        return CitationVerdict("locator_invalid", SOURCE, NIL)
    paper = await get_workpaper(tx.session, at.sheet_id)
    if paper is None:
        return CitationVerdict("source_not_found", SOURCE, at.sheet_id)
    if anchor.engagement_id is None or anchor.engagement_id != paper.engagement_id:
        return CitationVerdict("source_not_visible", SOURCE, at.sheet_id)
    # A paper is a person's to read (`workpaper.read` is never the agent's, ADR-005): an agent
    # or any other non-person actor cannot cite a cell.
    if not isinstance(actor, AuthContext) or not await _may_read(actor, paper.engagement_id):
        return CitationVerdict("source_not_visible", SOURCE, at.sheet_id)
    current = await next_version_no(tx.session, paper.id) - 1
    if at.sheet_version is not None and at.sheet_version > current:
        return CitationVerdict("source_not_found", SOURCE, at.sheet_id)
    cells = await cells_up_to(
        tx.session, paper.id, at.sheet_version if at.sheet_version != current else None
    )
    found = next((c for c in cells if _matches(c, at)), None)
    text = None if found is None else _typed(found).v
    if found is None or text is None:
        return CitationVerdict("cell_not_found", SOURCE, at.sheet_id, _locator_out(at))
    quote_sha: bytes | None = None
    if claim.value is not None:
        claimed, held = _amount(claim.value), _amount(text)
        same = (
            claimed == held
            if claimed is not None and held is not None
            else normalised_text(claim.value) == normalised_text(text)
        )
        if not same:
            return CitationVerdict("value_mismatch", SOURCE, at.sheet_id, _locator_out(at))
    if claim.quote is not None:
        folded = normalised_text(claim.quote)
        if folded == "" or folded not in normalised_text(text):
            return CitationVerdict("quote_not_found", SOURCE, at.sheet_id, _locator_out(at))
        quote_sha = hashlib.sha256(folded.encode()).digest()
    version = at.sheet_version or current
    return CitationVerdict(
        None,
        SOURCE,
        at.sheet_id,
        locator=_locator_out(at),
        source_version=f"v{version}" if version else None,
        match_id=f"wp:{paper.id}!{at.sheet_key}.{at.row_key}.{at.column_key}",
        quote_sha256=quote_sha,
        value_text=text,
    )


async def display_workpaper_cell(
    session: AsyncSession, locator: Mapping[str, object], engagement_id: UUID | None
) -> CitationLabel:
    """The paper's code and the cell's address; a paper outside the engagement is not named."""
    at = _cell_locator(locator)
    paper = None if at is None else await get_workpaper(session, at.sheet_id)
    if at is None or paper is None or paper.engagement_id != engagement_id:
        return CitationLabel("Workpaper", "cell no longer available")
    titles = {s.sheet_key: s.title for s in await sections_of(session, paper.id)}
    sheet = titles.get(at.sheet_key, at.sheet_key)
    a1 = at.column_key.isalpha() and at.row_key.isdigit()
    cell = f"{at.column_key.upper()}{at.row_key}" if a1 else f"{at.row_key}.{at.column_key}"
    return CitationLabel(f"{paper.code} · {paper.title}", f"{sheet}!{cell}")


# --- the `workpaper_cell` field owner (C3 `register_field_owner`; SHL-09) -----------------------


def _field(field_key: str) -> tuple[str, str]:
    sheet, sep, cell = field_key.partition("!")
    return (sheet, cell) if sep else (SHEET, field_key)


async def cell_value(
    tenant: TenantContext, workpaper_id: UUID, field_key: str
) -> dict[str, object] | None:
    """A cell's current value `{t, v}` in the field history's types (review's four)."""
    sheet, cell = _field(field_key)
    async with tenant_session(tenant) as session:
        paper = await get_workpaper(session, workpaper_id)
        if paper is None:
            return None
        found = next(
            (
                c
                for c in await cells_up_to(session, paper.id, None)
                if (c.sheet_key, c.cell_key) == (sheet, cell)
            ),
            None,
        )
    if found is None:
        return None
    return _history_value(_typed(found))


async def apply_cell_edit(
    tx: UnitOfWork, ctx: AuthContext, workpaper_id: UUID, field_key: str, value: dict[str, object]
) -> str | None:
    """SHL-09's tray edit: the cell's next row, as the person; the paper's hash after it."""
    sheet, cell = _field(field_key)
    paper = await get_workpaper(tx.session, workpaper_id)
    if paper is None or paper.kind is None:
        raise NotFound("workpaper")
    await authorise(ctx, "workpaper.edit", (await lock_ref(tx, paper.engagement_id)).resource())
    old = next(
        (
            c
            for c in await cells_up_to(tx.session, paper.id, None)
            if (c.sheet_key, c.cell_key) == (sheet, cell)
        ),
        None,
    )
    if old is None:
        raise NotFound("workpaper_cell")
    raw = value.get("v")
    await insert_cells(
        tx.session,
        [
            {
                "tenant_id": ctx.tenant_id,
                "workpaper_id": paper.id,
                "sheet_key": sheet,
                "cell_key": cell,
                "raw": None if raw is None else str(raw),
                "value_source": "human",
                "tickmarks": list(old.tickmarks),
                "set_by": ctx.user_id,
                "section_key": old.section_key,
                "row_key": old.row_key,
                "col_key": old.col_key,
                "value": {"t": value.get("t"), "v": raw},
                "value_state": "edited"
                if old.value_state in ("suggested", "adopted")
                else "human",
                "classification": old.classification,
                "updated_version_no": old.updated_version_no,
            }
        ],
    )
    tx.emit(WorkpaperContentChanged(workpaper_id=paper.id, engagement_id=paper.engagement_id))
    cells = await cells_up_to(tx.session, paper.id, None)
    citations = await citations_of(tx.session, [paper.id])
    return content_hash(
        content_of(cells, citations, await tb_link(ctx.tenant, paper.engagement_id))
    )


def cell_label(field_key: str) -> str:
    sheet, cell = _field(field_key)
    return cell if sheet == SHEET else f"{sheet}!{cell}"


CELL_OWNER: Final = FieldOwner(
    CELL_TARGET, cell_value, label_of=cell_label, apply_edit=apply_cell_edit
)


async def cell_facts(tenant: TenantContext, workpaper_id: UUID) -> ReviewableFacts | None:
    """The paper's facts under the cell target (SHL-09 authorises a cell edit on them)."""
    facts = await workpaper_facts(tenant, workpaper_id)
    return None if facts is None else replace(facts, target_type=CELL_TARGET)
