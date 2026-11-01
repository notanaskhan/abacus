"""A-04-T11: what the section drafter reads, where an adopted value lands, and how a person starts
a draft (A-04 §3.1 AC1.1, §6 AC6.1; DEC-1868).

- **Draft context** (`draft_paper`): an A-04 paper's kind, current version, the step keys it is
  bound to, and the cells of the section being drafted (keys, row and column labels, current typed
  value). The caller has authorised `workpaper.read` on the paper's engagement.
- **Adoption** (`apply_cell_suggestion`, the `workpaper_cell` suggestion applier agents registers):
  a person adopting a suggestion writes the cell's next row (`adopted`, or `edited` when the person
  changed the value), records the value through `review.api.record_value` (cause
  `suggestion_adopted` or `edit`) and makes the paper's next version (cause `adopt`), so an earlier
  sign-off reads stale. The agent never writes a cell (AC1.1).
- **Pack** (`pack_problem`, `bound`): the steps a paper is bound to and the first reference they
  can't resolve, for the drafter's code check before any model call (AC6.1).
Workpapers registers these with agents (`register_section_source`) and registers the applier
(`register_suggestion_applier`): workpapers depends on agents, never the reverse (BOUND-002).
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from abacus.kernel.db import TenantContext, tenant_session
from abacus.kernel.errors import NotFound
from abacus.kernel.uow import Ref, Target, UnitOfWork
from abacus.modules.agents.api import (
    AdoptedValue,
    PackProblem,
    SectionSource,
    SourceCell,
    SourcePaper,
)
from abacus.modules.engagements.api import lock_ref
from abacus.modules.identity.api import AuthContext, authorise
from abacus.modules.methodology.api import VersionStep
from abacus.modules.review.api import record_value
from abacus.modules.workpapers.core import CELL_TARGET
from abacus.modules.workpapers.events import WorkpaperContentChanged, WorkpaperVersionCreated
from abacus.modules.workpapers.models import WorkpaperCell
from abacus.modules.workpapers.procedures import bound_steps, pack_errors
from abacus.modules.workpapers.repository import (
    cells_up_to,
    citations_of,
    get_workpaper,
    insert_cells,
    insert_version,
    next_version_no,
    sections_of,
)
from abacus.modules.workpapers.service import (
    SHEET,
    TARGET,
    cell_ref,
    content_hash,
    content_of,
    tb_link,
)


def _in_section(cell: WorkpaperCell, section_key: str | None) -> bool:
    return section_key is None or section_key in (cell.section_key, cell.sheet_key)


async def draft_paper(
    tenant: TenantContext, engagement_id: UUID, workpaper_id: UUID, section_key: str | None
) -> SourcePaper:
    """The paper as the drafter reads it (404 for a paper with no kind, another engagement's, or
    a section it doesn't have)."""
    async with tenant_session(tenant) as session:
        paper = await get_workpaper(session, workpaper_id)
        if paper is None or paper.engagement_id != engagement_id or paper.kind is None:
            raise NotFound("workpaper")
        sections = {s.sheet_key for s in await sections_of(session, paper.id)}
        if section_key is not None and section_key not in sections:
            raise NotFound("workpaper_section")
        cells = await cells_up_to(session, paper.id, None)
        version_no = await next_version_no(session, paper.id) - 1
    return SourcePaper(
        paper.id,
        paper.engagement_id,
        paper.work_item_id,
        paper.code,
        paper.title,
        paper.kind,
        version_no,
        tuple(paper.program_step_keys),
        section_key,
        tuple(
            SourceCell(c.sheet_key, c.cell_key, c.row_key, c.col_key, c.value)
            for c in sorted(cells, key=lambda c: (c.sheet_key, c.cell_key))
            if _in_section(c, section_key)
        ),
    )


async def paper_engagement(tenant: TenantContext, workpaper_id: UUID) -> UUID | None:
    """Which engagement a `workpaper_cell` suggestion's paper belongs to (P-04-T24 M4)."""
    async with tenant_session(tenant) as session:
        paper = await get_workpaper(session, workpaper_id)
    return None if paper is None else paper.engagement_id


def _field(field_key: str) -> tuple[str, str]:
    sheet, sep, cell = field_key.partition("!")
    return (sheet, cell) if sep else (SHEET, field_key)


async def apply_cell_suggestion(tx: UnitOfWork, ctx: AuthContext, adopted: AdoptedValue) -> None:
    """A person adopted (or edited and adopted) the agent's value for one cell."""
    sheet, cell = _field(adopted.field_key)
    paper = await get_workpaper(tx.session, adopted.target_id)
    if paper is None or paper.kind is None:
        raise NotFound("workpaper")
    ref = await lock_ref(tx, paper.engagement_id)
    await authorise(ctx, "workpaper.edit", ref.resource())
    now = {(c.sheet_key, c.cell_key): c for c in await cells_up_to(tx.session, paper.id, None)}
    old = now.get((sheet, cell))
    if old is None:
        raise NotFound("workpaper_cell")
    version_no = await next_version_no(tx.session, paper.id)
    edited = adopted.value_source == "human"
    await record_value(
        tx,
        engagement_id=paper.engagement_id,
        target_type=CELL_TARGET,
        target_id=paper.id,
        field_key=cell_ref(sheet, cell),
        value=adopted.value,
        value_source=adopted.value_source,
        cause=adopted.cause,
        suggestion_id=adopted.suggestion_id,
        checkpoint_id=adopted.checkpoint_id,
        citation_ids=adopted.citation_ids,
        citation_note=adopted.citation_note,
    )
    raw = adopted.value.get("v")
    await insert_cells(
        tx.session,
        [
            {
                "tenant_id": ctx.tenant_id,
                "workpaper_id": paper.id,
                "sheet_key": sheet,
                "cell_key": cell,
                "raw": None if raw is None else str(raw),
                "value_source": "human" if edited else "agent",
                "tickmarks": list(old.tickmarks),
                "set_by": ctx.user_id,
                "section_key": old.section_key,
                "row_key": old.row_key,
                "col_key": old.col_key,
                "value": dict(adopted.value),
                "value_state": "edited" if edited else "adopted",
                "suggestion_id": adopted.suggestion_id,
                "classification": old.classification,
                "updated_version_no": version_no,
            }
        ],
    )
    cells = await cells_up_to(tx.session, paper.id, None)
    citations = await citations_of(tx.session, [paper.id])
    content = content_of(cells, citations, await tb_link(ctx.tenant, paper.engagement_id))
    await insert_version(
        tx.session,
        tenant_id=ctx.tenant_id,
        workpaper_id=paper.id,
        version_no=version_no,
        content_hash=content_hash(content),
        content=content,
        created_by=ctx.user_id,
        produced_by_kind="human",
        cause="adopt",
    )
    tx.record(
        "workpaper.cells_edited",
        target=Target(TARGET, paper.id),
        after=Ref(version=version_no, cells=1),
    )
    tx.emit(WorkpaperContentChanged(workpaper_id=paper.id, engagement_id=paper.engagement_id))
    tx.emit(
        WorkpaperVersionCreated(
            workpaper_id=paper.id,
            engagement_id=paper.engagement_id,
            work_item_id=paper.work_item_id,
            version_no=version_no,
        )
    )


def bound(steps: Sequence[VersionStep], paper: SourcePaper) -> list[VersionStep]:
    """The steps a draft of this paper is bound to (`procedures.bound_steps`)."""
    return bound_steps(steps, step_keys=paper.step_keys, kind=paper.kind)


async def pack_problem(
    tenant: TenantContext, version_id: UUID, paper: SourcePaper
) -> PackProblem | None:
    """The first reference the paper's bound steps can't resolve (AUD-09 d's words), or None."""
    errors = await pack_errors(tenant, version_id, step_keys=paper.step_keys, kind=paper.kind)
    if not errors:
        return None
    first = errors[0]
    return PackProblem(first.message, first.program_code, first.number, first.ref)


SOURCE = SectionSource(draft_paper, bound, pack_problem)

__all__ = [
    "SOURCE",
    "apply_cell_suggestion",
    "bound",
    "draft_paper",
    "pack_problem",
    "paper_engagement",
]
