"""Platform staff: the Pub 4557 control definitions (G-02-T20; DEC-626). Platform content, never a
commit (AGENTS.md 16): one staff member imports a numbered draft set, a second publishes it (409
`control_set_same_person` for the importer); the published set is what every firm's safeguards
record counts over."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import Depends
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.text import SingleLineText
from abacus.modules.identity.api import STAFF, AbacusRouter, Staff, current_staff
from abacus.modules.platform.safeguards import import_controls, publish_controls

controls_platform_router = AbacusRouter(
    prefix="/v1/platform/safeguards-controls", tags=["security center"]
)


class SafeguardsControlRowIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    control_key: Annotated[
        str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,63}$"), classified("internal")
    ]
    title: Annotated[SingleLineText, Field(min_length=1, max_length=200), classified("internal")]
    position: Annotated[int, Field(ge=1, le=500), classified("internal")]


class SafeguardsControlSetIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    set_version: Annotated[int, Field(ge=1), classified("internal")]
    rows: Annotated[
        list[SafeguardsControlRowIn], Field(min_length=1, max_length=200), classified("internal")
    ]


class SafeguardsControlSetOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    set_version: Annotated[int, classified("internal")]
    rows: Annotated[int, classified("internal")]
    status: Annotated[Literal["draft", "published"], classified("internal")]


@controls_platform_router.post(
    "", action=STAFF, response_model=SafeguardsControlSetOut, status_code=201, errors=(409,)
)
async def import_safeguards_controls_route(
    body: SafeguardsControlSetIn, staff: Annotated[Staff, Depends(current_staff)]
) -> SafeguardsControlSetOut:
    """A draft set of control definitions; a second staff member publishes it. 409
    `control_set_exists`; 422 `control_set_invalid`."""
    rows = [r.model_dump(mode="json") for r in body.rows]
    n = await import_controls(body.set_version, rows, str(staff.id))
    return SafeguardsControlSetOut(set_version=body.set_version, rows=n, status="draft")


@controls_platform_router.post(
    "/{set_version}/publish", action=STAFF, response_model=SafeguardsControlSetOut, errors=(409,)
)
async def publish_safeguards_controls_route(
    set_version: int, staff: Annotated[Staff, Depends(current_staff)]
) -> SafeguardsControlSetOut:
    """Publish a draft set as a second staff member; the previous set is superseded."""
    n = await publish_controls(set_version, str(staff.id))
    return SafeguardsControlSetOut(set_version=set_version, rows=n, status="published")
