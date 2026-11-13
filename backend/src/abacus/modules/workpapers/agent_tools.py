"""`workpapers.read_section` on C17 (W-02-T11; W-02 §6; ADR-233, ADR-049, ADR-052; DEC-4716).

One workpaper of the run's engagement, by its code: its title, area, status, sign-off levels and
filled cells (address with text or computed value), and its citation count. Read only; a cell's
text may come from client data, so the model reads `cells` as untrusted. The runtime authorised
`workpaper.read` on the engagement; `workpaper_detail` checks it again.
"""

from __future__ import annotations

from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import agent_tool
from abacus.modules.identity.api import AgentContext

Int = classified("internal")
Conf = classified("confidential")
MAX_CELLS: Final = 200


class SectionIn(BaseModel):
    """The frozen workbench suite's arguments (S41 end pass, DEC-4733): the workpaper, and the
    section it should be (its kind, `internal_control`, or its AUD-17 section, `planning`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    workpaper_id: Annotated[UUID, Int]
    section: Annotated[str | None, Field(min_length=1, max_length=40), Int] = None


class CellRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[str, Int]  # "<workpaper id>:<cell>" (ADR-049: rows carry an id)
    address: Annotated[str, Int]
    text: Annotated[str | None, Conf] = None
    value: Annotated[str | None, Conf] = None


class SectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, Int]
    title: Annotated[str, Conf]
    audit_area: Annotated[str | None, Conf] = None
    status: Annotated[str, Int]
    signed_levels: Annotated[list[int], Int]
    cells: Annotated[list[CellRow], Conf]
    citations: Annotated[int, Int]
    total_cells: Annotated[int, Int]


@agent_tool(
    name="workpapers.read_section", kind="read", action="workpaper.read",
    data_class="confidential", input_model=SectionIn, output_model=SectionOut,
    untrusted=("cells",), records_read="workpaper",
)  # fmt: skip
async def read_section(agent: AgentContext, args: SectionIn) -> SectionOut:
    from abacus.kernel.db import tenant_session
    from abacus.modules.workpapers.models import Workpaper
    from abacus.modules.workpapers.service import section_of, workpaper_detail, workpapers_for

    async with tenant_session(agent.tenant) as session:
        row = (
            await session.execute(
                select(Workpaper.engagement_id, Workpaper.kind).where(
                    Workpaper.id == args.workpaper_id
                )
            )
        ).first()
    if row is None:
        raise NotFound("workpaper")
    engagement = row.engagement_id
    # `workpapers_for` applies the reader's visibility: a paper they may not read is not found.
    papers = await workpapers_for(agent, engagement)  # type: ignore[arg-type] -- the run's context
    paper = next((p for p in papers if p.id == args.workpaper_id), None)
    if paper is None:
        raise NotFound("workpaper")
    if args.section is not None and args.section not in {
        row.kind,
        section_of(row.kind, paper.audit_area),
    }:
        raise NotFound("workpaper_section")
    detail = await workpaper_detail(agent, engagement, paper.id)  # type: ignore[arg-type] -- the run's context reads as its initiator
    cells = [
        CellRow(
            id=f"{paper.id}:{c.cell_key}",
            address=c.cell_key,
            text=c.text,
            value=None if c.value is None else format(c.value, "f"),
        )
        for c in detail.cells
    ]
    return SectionOut(
        code=paper.code,
        title=paper.title,
        audit_area=paper.audit_area,
        status=str(paper.status),
        signed_levels=sorted({lv.level for lv in paper.levels if getattr(lv, "signed_by", None)}),
        cells=cells[:MAX_CELLS],
        citations=len(detail.citations),
        total_cells=len(cells),
    )


__all__ = ["read_section"]
