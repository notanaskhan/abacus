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

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.modules.agents.api import agent_tool
from abacus.modules.identity.api import AgentContext

Int = classified("internal")
Conf = classified("confidential")
MAX_CELLS: Final = 200


class SectionIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    engagement_id: Annotated[UUID | None, Int] = None
    code: Annotated[str, Field(min_length=1, max_length=20), Int]


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
    from abacus.modules.workpapers.service import workpaper_detail, workpapers_for

    engagement = args.engagement_id or agent.engagement_id
    if engagement is None:
        raise NotFound("engagement")
    papers = await workpapers_for(agent, engagement)  # type: ignore[arg-type] -- the run's context
    paper = next((p for p in papers if p.code == args.code), None)
    if paper is None:
        raise NotFound("workpaper")
    detail = await workpaper_detail(agent, engagement, paper.id)  # type: ignore[arg-type]
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
