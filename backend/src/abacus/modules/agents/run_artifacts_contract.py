"""W-02's run-artifact and drill routes, stubs (W-02-T03; SPEC-653; W-02 §4.3). Contract:
`docs/contracts/workbench-sessions.md` (the workbench-sessions family, additive to C6 v2).

Every route answers, in order: its matrix action (the router), `workbench.enabled` (off: 404),
then 501 until W-02-T20 serves it.

- `GET /v1/run-artifacts/{id}/preview?sheet=`: one sheet of a run's **stored** artifact for the O4
  overlay (WB-03 d2). It is read from the stored bytes, never recomputed in the browser and never
  re-rendered from model output (C11). Content, so `run_content.read` (DEC-87): `agent_run.read`
  alone is the trace's metadata.
- `GET /v1/run-artifacts/{id}/download`: the stored bytes, audited `run_artifact.downloaded`
  under `run_artifact.download` (an export of client content; agent and system denied, INV-1).
- `POST /v1/workbench/sessions/{id}/drill`: appends a code-rendered table of one result group's
  records (WB-03 d "Action required 11"), filtered by `visible()`, with no model call. The session
  owner's (`session.manage`).
"""

from __future__ import annotations

from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import WORKBENCH_ENABLED
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")

CellKind = Literal["text", "number", "money", "percent", "date", "blank"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


class PreviewCellOut(BaseModel):
    """One cell as stored: `value` is the rendered text the workbook holds; numbers are never
    recomputed here (ADR-050)."""

    model_config = _frozen()

    value: Annotated[str, Confidential]
    kind: Annotated[CellKind, Internal] = "text"
    bold: Annotated[bool, Internal] = False


class ArtifactPreviewOut(BaseModel):
    """WB-03 d2: the sheet tabs, the open sheet's header and rows, from the stored artifact."""

    model_config = _frozen()

    artifact_id: Annotated[UUID, Internal]
    file_name: Annotated[str, Confidential]
    sheets: Annotated[list[str], Confidential]  # tab names in workbook order
    sheet: Annotated[str, Confidential]  # the tab shown
    columns: Annotated[list[str], Confidential]
    rows: Annotated[list[list[PreviewCellOut]], Confidential]
    footnote: Annotated[str | None, Confidential] = None  # the stage-definition row
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$"), Internal]


class DrillIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_id: Annotated[UUID, Internal]
    # A result group of the artifact, such as `status:action_required` (WB-03 d).
    group_key: Annotated[str, Field(pattern=r"^[a-z_]{1,40}:[a-z0-9_]{1,60}$"), Internal]


class DrillRowOut(BaseModel):
    """One record of the group: its link target and the words shown; names are resolved under the
    viewer's `visible()` at read time (DEC-61), never taken from model context."""

    model_config = _frozen()

    ref_type: Annotated[Literal["tax_return"], Internal]
    ref_id: Annotated[UUID, Internal]
    label: Annotated[str, Confidential]
    detail: Annotated[str | None, Confidential] = None
    href: Annotated[str, Internal]


class DrillOut(BaseModel):
    model_config = _frozen()

    item_id: Annotated[UUID, Internal]  # the `drill` session item appended
    group_key: Annotated[str, Internal]
    title: Annotated[str, Confidential]
    total: Annotated[int, Field(ge=0), Internal]
    rows: Annotated[list[DrillRowOut], Confidential]


run_artifacts_router = AbacusRouter(prefix="/v1/run-artifacts", tags=["workbench sessions"])
session_drill_router = AbacusRouter(prefix="/v1/workbench/sessions", tags=["workbench sessions"])


async def _gate(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, WORKBENCH_ENABLED):
        raise NotFound(WORKBENCH_ENABLED.name)


def _not_yet() -> NoReturn:
    raise NotImplementedYet


@run_artifacts_router.get(
    "/{artifact_id}/preview",
    action="run_content.read",
    response_model=ArtifactPreviewOut,
    errors=(501,),
)
async def artifact_preview_route(
    artifact_id: UUID,
    ctx: Ctx,
    sheet: Annotated[str | None, Query(min_length=1, max_length=31)] = None,
) -> ArtifactPreviewOut:
    """404 when the artifact's run is not readable (no existence leak, DEC-43)."""
    await _gate(ctx)
    _not_yet()


@run_artifacts_router.get(
    "/{artifact_id}/download",
    action="run_artifact.download",
    response_model=bytes,
    errors=(501,),
)
async def artifact_download_route(artifact_id: UUID, ctx: Ctx) -> Response:
    """The stored bytes with their content type; writes `run_artifact.downloaded`."""
    await _gate(ctx)
    _not_yet()


@session_drill_router.post(
    "/{session_id}/drill",
    action="session.manage",
    response_model=DrillOut,
    status_code=201,
    errors=(501,),
)
async def session_drill_route(
    session_id: UUID, body: DrillIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> DrillOut:
    """The session owner's; no model call; rows filtered by `visible()` (AC-R4, INV-3)."""
    await _gate(ctx)
    _not_yet()
