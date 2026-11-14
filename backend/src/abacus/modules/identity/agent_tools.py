"""Identity's agent tool (W-02-T19; W-02 §4.1; C17; ADR-233, ADR-106). PROTECTED (identity, red).

`identity.list_offices` (read, `org_structure.list`): the firm's offices by name, through the
office-list slot organisations registers (`slots.firm_offices`). Offices group work for counting
("By office Chicago 34 · Denver 23 · New York 22"); they are never an access boundary (DEC-30), so
the tool reads no engagement and names no client. Declared as a `ToolDecl` and registered by
`agents` (`agents.tools.catalogue`).
"""

from __future__ import annotations

from typing import Annotated, Final
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.agent_tools import MAX_ROWS, ToolCaller, ToolDecl
from abacus.kernel.classification import classified
from abacus.modules.identity.slots import firm_offices

Int = classified("internal")
LIST: Final = "org_structure.list"


class ListOfficesIn(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OfficeRow(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Int]
    name: Annotated[str, Int]


class ListOfficesOut(BaseModel):
    offices: Annotated[list[OfficeRow], Field(max_length=MAX_ROWS), Int]
    total: Annotated[int, Field(ge=0), Int]


async def list_offices(caller: ToolCaller, args: ListOfficesIn) -> ListOfficesOut:
    """The firm's offices, by name (the slot orders them)."""
    found = await firm_offices(caller.tenant)
    rows = [OfficeRow(id=i, name=n) for i, n in found[:MAX_ROWS]]
    return ListOfficesOut(offices=rows, total=len(found))


AGENT_TOOLS: Final = (
    ToolDecl(
        "identity.list_offices", "read", LIST, "internal", ListOfficesIn, ListOfficesOut,
        list_offices, records_read="office",
    ),
)  # fmt: skip
