"""Working papers, the audit core's first slice (A-04; SPEC-308; TASK-319).

A paper belongs to the engagement's assurance work item. Its grid is insert-only cells: an edit
appends a row and the newest row per cell is the value. Formulas are computed by code
(`formulas`), never by a model (ADR-050). A cell can cite an evidence version the engagement
holds. Sign-offs (L1-L5) come from the review module and record the content hash; each one
snapshots a numbered version, and any later change shows the sign-off as stale.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Final, cast
from uuid import UUID

from abacus.kernel._statuses import AuditSectionStatus
from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import DomainConflict, DomainInvalid, NotFound
from abacus.kernel.uow import Ref, Target, uow
from abacus.modules.engagements.api import assurance_item_id, get_ref, lock_ref
from abacus.modules.evidence.api import version_view
from abacus.modules.identity.api import AuthContext, authorise, engagement_team
from abacus.modules.ledger.api import TbLine, engagement_trial_balances, trial_balance_view
from abacus.modules.review.api import (
    Json,
    LevelState,
    Reviewable,
    ReviewableFacts,
    record_sign_off,
    sign_off_states,
)
from abacus.modules.review.api import content_hash as review_content_hash
from abacus.modules.workpapers.events import WorkpaperContentChanged
from abacus.modules.workpapers.formulas import TbSource, evaluate, is_formula
from abacus.modules.workpapers.models import Workpaper, WorkpaperCell, WorkpaperCellCitation
from abacus.modules.workpapers.repository import (
    cell_setters,
    citations_of,
    code_taken,
    engagement_papers,
    get_workpaper,
    insert_cells,
    insert_citation,
    insert_version,
    insert_workpaper,
    newest_cells,
    next_version_no,
    versions_of,
    workpapers_of,
)

TARGET: Final = "workpaper"
SHEET: Final = "main"
_CODE: Final = re.compile(r"^[A-Z0-9][A-Z0-9.-]{0,19}$")
_CELL: Final = re.compile(r"^[A-Z]{1,2}[1-9][0-9]{0,3}$")
TICKMARKS: Final = frozenset(
    {"agreed", "footed", "cross_footed", "recalculated", "traced", "vouched", "exception"}
)
MAX_EDITS: Final = 200


class WorkpaperInvalid(DomainInvalid):
    code = "workpaper_invalid"


class CodeTaken(DomainConflict):
    code = "workpaper_code_taken"


class NoAssuranceItem(DomainConflict):
    """Only an attest engagement (with its assurance work item) holds working papers."""

    code = "no_assurance_item"


@dataclass(frozen=True)
class CellEdit:
    cell_key: str
    raw: str | None
    tickmarks: tuple[str, ...]


@dataclass(frozen=True)
class CitationView:
    cell_key: str
    evidence_version_id: UUID
    locator: str | None
    added_by_name: str
    added_at: datetime


@dataclass(frozen=True)
class CellView:
    cell_key: str
    raw: str | None
    value: Decimal | None
    text: str | None  # plain text, or a formula error code
    error: bool
    formula: bool
    tickmarks: list[str]
    set_by_name: str
    set_at: datetime


@dataclass(frozen=True)
class LevelView:
    level: int
    name: str
    signed_by_name: str | None
    signed_at: datetime | None
    stale: bool


@dataclass(frozen=True)
class VersionView:
    version_no: int
    content_hash: str
    created_by_name: str
    created_at: datetime


@dataclass(frozen=True)
class WorkpaperSummary:
    id: UUID
    code: str
    title: str
    audit_area: str | None
    status: AuditSectionStatus
    levels: list[LevelView]
    cells: int
    citations: int
    created_at: datetime


@dataclass(frozen=True)
class TbLink:
    """The trial balance TB() reads (SPEC-310): the engagement's Standard trial balance with the
    latest period end (or its only one), at its current version."""

    id: UUID
    label: str
    period_end: date
    version_no: int
    source: TbSource
    accounts: list[TbLine]
    entries: frozenset[str] = frozenset()  # refs of the recorded entries in Final


@dataclass(frozen=True)
class WorkpaperDetail:
    summary: WorkpaperSummary
    content_hash: str
    cells: list[CellView]
    citations: list[CitationView]
    versions: list[VersionView]
    tb: TbLink | None
    tb_accounts: list[TbLine]  # the trial balance's accounts whose WP ref is this paper's code


def content_of(
    cells: Sequence[WorkpaperCell],
    citations: Sequence[WorkpaperCellCitation],
    tb: TbLink | None = None,
) -> dict[str, object]:
    """What a sign-off approves: each filled cell's raw text and tickmarks, the citations, and
    which trial balance version TB() read when any cell uses it (so a new version is a change).

    A-04-T04 (DEC-1762): a cell on another sheet than `main` is keyed `<sheet>!<cell>`, and a
    typed value joins its entry; a SPEC-308 paper's content, and so its hash, is unchanged."""
    content: dict[str, object] = {
        "cells": {
            cell_ref(c.sheet_key, c.cell_key): _entry(c)
            for c in sorted(cells, key=lambda c: (c.sheet_key != SHEET, c.sheet_key, c.cell_key))
            if is_filled(c)
        },
        "citations": sorted(
            [cell_ref(c.sheet_key, c.cell_key), str(c.evidence_version_id), c.locator or ""]
            for c in citations
        ),
    }
    if tb is not None and any(tb.source.uses(c.raw) for c in cells):
        content["tb"] = {"id": str(tb.id), "version_no": tb.version_no}
        if any(_uses_final(c.raw) for c in cells):  # SPEC-311: a newly recorded entry is a change
            content["tb"] = {**content["tb"], "entries": sorted(tb.entries)}
    return content


def cell_ref(sheet_key: str, cell_key: str) -> str:
    """A cell's address in the signed content and the field history: the key alone on `main`."""
    return cell_key if sheet_key == SHEET else f"{sheet_key}!{cell_key}"


def is_filled(cell: WorkpaperCell) -> bool:
    return bool(cell.raw or cell.tickmarks or (cell.value is not None and cell.value.get("v")))


def _entry(cell: WorkpaperCell) -> dict[str, object]:
    entry: dict[str, object] = {"raw": cell.raw, "tickmarks": sorted(cell.tickmarks)}
    if cell.value is not None:
        entry["value"] = {"t": cell.value.get("t"), "v": cell.value.get("v")}
    return entry


async def tb_link(tenant: TenantContext, engagement_id: UUID) -> TbLink | None:
    """For callers authorised on the engagement (`workpaper.read` implies the team)."""
    found = await engagement_trial_balances(tenant, engagement_id)
    if not found:
        return None
    standard = [t for t in found if t.label == "standard"] or found
    tb = max(standard, key=lambda t: t.period_end)
    view = await trial_balance_view(tenant, engagement_id, tb.id)
    eoy = {line.account_code.upper(): line.eoy for line in view.lines}
    boy = (
        {line.account_code.upper(): line.boy or Decimal(0) for line in view.lines}
        if view.boy is not None
        else None
    )
    final = (
        {line.account_code.upper(): line.final for line in view.lines if line.final is not None}
        if view.final is not None
        else None
    )
    return TbLink(
        tb.id,
        tb.label,
        tb.period_end,
        tb.current_version_no,
        TbSource(eoy, boy, final),
        view.lines,
        frozenset(ref for line in view.lines for ref in line.refs),
    )


def content_hash(content: dict[str, object]) -> str:
    """The review grammar's one content hash (P-04-T14: RFC 8785 canonical JSON, SHA-256). For
    ASCII content it is byte for byte the sorted compact `json.dumps` used before (DEC-215)."""
    return review_content_hash(cast(Json, content))


def status_of(has_content: bool, levels: Sequence[LevelState]) -> AuditSectionStatus:
    """By code: a stale sign-off wins, then the highest current level."""
    if any(s.stale for s in levels):
        return AuditSectionStatus.CHANGED_AFTER_SIGNOFF
    current = {s.level for s in levels if s.signed_by is not None}
    if current & {4, 5}:
        return AuditSectionStatus.SIGNED_OFF
    if current & {2, 3}:
        return AuditSectionStatus.REVIEWED
    if 1 in current:
        return AuditSectionStatus.PREPARED
    return AuditSectionStatus.IN_PROGRESS if has_content else AuditSectionStatus.NOT_STARTED


def _uses_final(raw: str | None) -> bool:
    return _uses_tb(raw) and '"FINAL"' in (raw or "").upper()


def _uses_tb(raw: str | None) -> bool:
    return TbSource({}, None).uses(raw)


def clean_edits(edits: Sequence[CellEdit]) -> list[CellEdit]:
    if not edits or len(edits) > MAX_EDITS:
        raise WorkpaperInvalid("edits")
    seen: set[str] = set()
    out: list[CellEdit] = []
    for e in edits:
        if not _CELL.match(e.cell_key) or e.cell_key in seen:
            raise WorkpaperInvalid("cell_key")
        seen.add(e.cell_key)
        raw = (e.raw or "").strip() or None
        if raw is not None and len(raw) > 2000:
            raise WorkpaperInvalid("raw")
        marks = tuple(sorted(set(e.tickmarks)))
        if any(m not in TICKMARKS for m in marks):
            raise WorkpaperInvalid("tickmarks")
        out.append(CellEdit(e.cell_key, raw, marks))
    return out


def _paper(session_get: Workpaper | None, engagement_id: UUID) -> Workpaper:
    if session_get is None or session_get.engagement_id != engagement_id:
        raise NotFound("workpaper")
    return session_get


async def _names(ctx: AuthContext, engagement_id: UUID) -> dict[UUID, str]:
    return {m.user_id: m.display_name for m in await engagement_team(ctx, engagement_id)}


def _levels(states: Sequence[LevelState], names: dict[UUID, str]) -> list[LevelView]:
    return [
        LevelView(
            s.level,
            s.name,
            names.get(s.signed_by, "Former member") if s.signed_by else None,
            s.signed_at,
            s.stale,
        )
        for s in states
    ]


async def workpapers_for(ctx: AuthContext, engagement_id: UUID) -> list[WorkpaperSummary]:
    """AC-1: the engagement's papers with status and sign-off levels, by code."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "workpaper.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        papers = await workpapers_of(session, ctx, engagement_id)
        ids = [p.id for p in papers]
        cells = await newest_cells(session, ids)
        citations = await citations_of(session, ids)
    tb = await tb_link(ctx.tenant, engagement_id) if papers else None
    hashes = {
        p.id: content_hash(
            content_of(
                [c for c in cells if c.workpaper_id == p.id],
                [c for c in citations if c.workpaper_id == p.id],
                tb,
            )
        )
        for p in papers
    }
    states = await sign_off_states(ctx.tenant, TARGET, ids, hashes)
    names = await _names(ctx, engagement_id)
    out: list[WorkpaperSummary] = []
    for p in papers:
        filled = sum(1 for c in cells if c.workpaper_id == p.id and is_filled(c))
        cited = sum(1 for c in citations if c.workpaper_id == p.id)
        out.append(
            WorkpaperSummary(
                p.id,
                p.code,
                p.title,
                p.audit_area,
                status_of(filled > 0 or cited > 0, states[p.id]),
                _levels(states[p.id], names),
                filled,
                cited,
                p.created_at,
            )
        )
    return out


async def create_workpaper(
    ctx: AuthContext, engagement_id: UUID, code: str, title: str, audit_area: str | None
) -> UUID:
    """AC-2: a new paper on the engagement's assurance work item; codes unique per engagement."""
    code, title = code.strip().upper(), title.strip()
    area = (audit_area or "").strip() or None
    if not _CODE.match(code):
        raise WorkpaperInvalid("code")
    if not 1 <= len(title) <= 200 or (area is not None and len(area) > 120):
        raise WorkpaperInvalid("title")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "workpaper.edit", ref.resource())
        item = await assurance_item_id(ctx.tenant, engagement_id)
        if item is None:
            raise NoAssuranceItem(str(engagement_id))
        if await code_taken(tx.session, engagement_id, code):
            raise CodeTaken(code)
        workpaper_id = await insert_workpaper(
            tx.session,
            tenant_id=ctx.tenant_id,
            engagement_id=engagement_id,
            work_item_id=item,
            code=code,
            title=title,
            audit_area=area,
            created_by=ctx.user_id,
        )
        tx.record("workpaper.created", target=Target(TARGET, workpaper_id))
    return workpaper_id


async def workpaper_detail(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID
) -> WorkpaperDetail:
    """AC-3: the grid with computed values, citations, sign-off levels and versions."""
    ref = await get_ref(ctx, engagement_id)
    await authorise(ctx, "workpaper.read", ref.resource())
    async with tenant_session(ctx.tenant) as session:
        paper = _paper(await get_workpaper(session, workpaper_id), engagement_id)
        cells = [c for c in await newest_cells(session, [paper.id]) if is_filled(c)]
        citations = await citations_of(session, [paper.id])
        versions = await versions_of(session, paper.id)
    tb = await tb_link(ctx.tenant, engagement_id)
    digest = content_hash(content_of(cells, citations, tb))
    states = (await sign_off_states(ctx.tenant, TARGET, [paper.id], {paper.id: digest}))[paper.id]
    names = await _names(ctx, engagement_id)
    values = evaluate({c.cell_key: c.raw for c in cells}, tb.source if tb else None)
    cell_views: list[CellView] = []
    for c in cells:
        v = values.get(c.cell_key, "")
        number = v if isinstance(v, Decimal) else None
        text = v if isinstance(v, str) and v else None
        cell_views.append(
            CellView(
                c.cell_key,
                c.raw,
                number,
                text,
                text is not None and is_formula(c.raw) and text.startswith("#"),
                is_formula(c.raw),
                sorted(c.tickmarks),
                names.get(c.set_by, "Former member"),
                c.created_at,
            )
        )
    summary = WorkpaperSummary(
        paper.id,
        paper.code,
        paper.title,
        paper.audit_area,
        status_of(bool(cells) or bool(citations), states),
        _levels(states, names),
        len(cells),
        len(citations),
        paper.created_at,
    )
    return WorkpaperDetail(
        summary,
        digest,
        cell_views,
        [
            CitationView(
                c.cell_key,
                c.evidence_version_id,
                c.locator,
                names.get(c.added_by, "Former member"),
                c.created_at,
            )
            for c in citations
        ],
        [
            VersionView(
                v.version_no,
                v.content_hash,
                names.get(v.created_by, "Former member"),
                v.created_at,
            )
            for v in versions
        ],
        tb,
        [a for a in tb.accounts if a.wp_ref == paper.code] if tb else [],
    )


async def set_cells(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID, edits: Sequence[CellEdit]
) -> int:
    """AC-3: append the changed cells (an unchanged edit writes nothing). Returns rows written."""
    clean = clean_edits(edits)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "workpaper.edit", ref.resource())
        paper = _paper(await get_workpaper(tx.session, workpaper_id), engagement_id)
        current = {c.cell_key: c for c in await newest_cells(tx.session, [paper.id])}
        rows: list[dict[str, object]] = []
        for e in clean:
            old = current.get(e.cell_key)
            if (
                old is not None
                and old.raw == e.raw
                and tuple(sorted(old.tickmarks)) == e.tickmarks
            ):
                continue
            if old is None and e.raw is None and not e.tickmarks:
                continue
            rows.append(
                {
                    "tenant_id": ctx.tenant_id,
                    "workpaper_id": paper.id,
                    "sheet_key": SHEET,
                    "cell_key": e.cell_key,
                    "raw": e.raw,
                    "value_source": (
                        "tb_linked"
                        if _uses_tb(e.raw)
                        else "formula"
                        if is_formula(e.raw)
                        else "human"
                    ),
                    "tickmarks": list(e.tickmarks),
                    "set_by": ctx.user_id,
                }
            )
        await insert_cells(tx.session, rows)
        if rows:
            tx.record(
                "workpaper.cells_set", target=Target(TARGET, paper.id), after=Ref(cells=len(rows))
            )
            tx.emit(WorkpaperContentChanged(workpaper_id=paper.id, engagement_id=engagement_id))
    return len(rows)


async def cite(
    ctx: AuthContext,
    engagement_id: UUID,
    workpaper_id: UUID,
    cell_key: str,
    evidence_version_id: UUID,
    locator: str | None,
) -> None:
    """AC-4: cite an evidence version this engagement holds on a cell."""
    locator = (locator or "").strip() or None
    if not _CELL.match(cell_key) or (locator is not None and len(locator) > 120):
        raise WorkpaperInvalid("citation")
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        await authorise(ctx, "workpaper.edit", ref.resource())
        paper = _paper(await get_workpaper(tx.session, workpaper_id), engagement_id)
        version = await version_view(ctx.tenant, evidence_version_id)
        if version.engagement_id != engagement_id:
            raise NotFound("evidence_version")
        await insert_citation(
            tx.session,
            tenant_id=ctx.tenant_id,
            workpaper_id=paper.id,
            sheet_key=SHEET,
            cell_key=cell_key,
            evidence_version_id=evidence_version_id,
            locator=locator,
            added_by=ctx.user_id,
        )
        tx.record(
            "workpaper.cited",
            target=Target(TARGET, paper.id),
            after=Ref(evidence=evidence_version_id),
        )
        tx.emit(WorkpaperContentChanged(workpaper_id=paper.id, engagement_id=engagement_id))


async def sign_off(ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID, level: int) -> None:
    """AC-5: sign the paper's current content at a level; snapshots a numbered version."""
    tb = await tb_link(ctx.tenant, engagement_id)
    async with uow(ctx.tenant) as tx:
        ref = await lock_ref(tx, engagement_id)
        paper = _paper(await get_workpaper(tx.session, workpaper_id), engagement_id)
        cells = await newest_cells(tx.session, [paper.id])
        citations = await citations_of(tx.session, [paper.id])
        content = content_of(cells, citations, tb)
        if not content["cells"] and not content["citations"]:
            raise WorkpaperInvalid("empty")
        digest = content_hash(content)
        await record_sign_off(
            tx, ctx, ref.resource(), engagement_id, TARGET, paper.id, level, digest
        )
        await insert_version(
            tx.session,
            tenant_id=ctx.tenant_id,
            workpaper_id=paper.id,
            version_no=await next_version_no(tx.session, paper.id),
            content_hash=digest,
            content=content,
            created_by=ctx.user_id,
        )


async def workpaper_facts(tenant: TenantContext, workpaper_id: UUID) -> ReviewableFacts | None:
    """P-04-T14: one paper's facts for the sign-off rules, for callers authorised on its
    engagement. Its preparers (P-04-T15; DEC-216) are everyone who ever set a cell or added a
    citation, from the paper's own records; the review module adds its L1 signers."""
    async with tenant_session(tenant) as session:
        paper = await get_workpaper(session, workpaper_id)
        if paper is None:
            return None
        cells = await newest_cells(session, [paper.id])
        citations = await citations_of(session, [paper.id])
        setters = await cell_setters(session, paper.id)
        version_no = await next_version_no(session, paper.id) - 1
    tb = await tb_link(tenant, paper.engagement_id)
    filled = [c for c in cells if is_filled(c)]
    cited = {c.cell_key for c in citations}
    return ReviewableFacts(
        TARGET,
        paper.id,
        paper.engagement_id,
        content_hash(content_of(cells, citations, tb)),
        version_no,
        frozenset(setters | {c.added_by for c in citations}),
        # P-04-T18 (SHL-12): the sheet's card and R-SO-6's uncited agent values (INV-2).
        label=paper.title,
        context_label=paper.code,
        work_item_id=paper.work_item_id,
        cell_count=len(filled),
        citation_count=len(citations),
        cited_count=sum(1 for c in filled if c.cell_key in cited),
        uncited_count=sum(
            1 for c in filled if c.value_source == "agent" and c.cell_key not in cited
        ),
    )


async def workpaper_reviewables(tenant: TenantContext, engagement_id: UUID) -> list[Reviewable]:
    """SPEC-313: each paper with its current content hash, for the matrix and G5."""
    async with tenant_session(tenant) as session:
        papers = await engagement_papers(session, engagement_id)
        ids = [p.id for p in papers]
        cells = await newest_cells(session, ids)
        citations = await citations_of(session, ids)
    if not papers:
        return []
    tb = await tb_link(tenant, engagement_id)
    out: list[Reviewable] = []
    for p in papers:
        mine = [c for c in cells if c.workpaper_id == p.id]
        cited = [c for c in citations if c.workpaper_id == p.id]
        content = content_of(mine, cited, tb)
        out.append(
            Reviewable(
                TARGET,
                p.id,
                p.code,
                p.title,
                content_hash(content),
                bool(content["cells"]) or bool(content["citations"]),
            )
        )
    return out
