"""Knowledge catalog v1 and methodology programs v1, the stubs (K-01-T01; K-01 §4.3, §8.2).
Contracts: `docs/contracts/knowledge-catalog.md` and `docs/contracts/methodology-programs.md`.

Each route answers 404 with its flag off and 501 `not_implemented` with it on until its task
lands: the catalog (`knowledge.catalog`) in K-01-T03; submit and approve
(`methodology.lifecycle`) in K-01-T06; program and step reads, the resolve endpoint and the
export (`methodology.programs`) in K-01-T12; drafts, discard, step edits and mandatory locks in
K-01-T14. The SPEC-008 routes (`routes.py`) stay live and are extended additively.

Rules the shapes carry:
- **Anchors are stable**: a step is `step_key@v<n>`; numbering may change, the key does not.
- **Content is immutable once published**: edits happen in a draft (vN+1); a published or
  superseded version answers 409 `version_frozen` (the database trigger lands with K-01-T05).
- **People approve**: `methodology.approve` (approve, mandatory locks) is human-only with a fresh
  second factor; the agent may only `methodology.parse` its own import (K-01-T21).
- **Facts are codes and identifiers**: change-log facts carry ids, codes and counts only.
- Classification: titles, step text, guidance and file names are internal (K-01 §4.2).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Path, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import (
    KNOWLEDGE_CATALOG,
    METHODOLOGY_LIFECYCLE,
    METHODOLOGY_PROGRAMS,
)
from abacus.kernel._statuses import (
    KnowledgeItemStatus,
    MethodologyVersionStatus,
    ParseFlagStatus,
)
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.kernel.listing import ListPage
from abacus.modules.identity.api import (
    AbacusRouter,
    AuthContext,
    Resource,
    authorise,
    current_context,
)

Ctx = Annotated[AuthContext, Depends(current_context)]
# KNW-01's categories; each is a registered catalog provider's (K-01-T03: methodology versions
# and PBC templates first; K-02, K-03, K-05, X-01, T-09 and W-03 register theirs).
Category = Literal[
    "methodology",
    "pbc_templates",
    "firm_standards",
    "engagement_templates",
    "skills",
    "notes",
    "content_packs",
    "frameworks",
    "research",
    "agent_instructions",
]
StepLevel = Literal["foundation", "planning", "testing", "completion"]
StepOrigin = Literal["workbook", "importer", "manual"]
FlagResolution = Literal["confirmed", "edited"]
ApprovalBasis = Literal["approved", "legacy_import"]
VersionEventKind = Literal[
    "legacy_backfilled",
    "imported",
    "published",
    "draft_created",
    "submitted",
    "approved",
    "superseded",
    "discarded",
    "standards_mapped",
    "exported",
]
ContentHash = Annotated[str, Field(pattern=r"^sha256:[0-9a-f]{64}$")]
StepKey = Annotated[str, Field(pattern=r"^[a-z0-9][a-z0-9_.-]{0,79}$")]


async def _stub(ctx: AuthContext, flag: Flag, action: str) -> NoReturn:
    """A client principal never reaches knowledge (INV-4): 404. Then the route's action at the
    firm (the agent, the system and anyone else refused: 403, before the flag is read), then the
    flag, then 501."""
    if ctx.client:
        raise NotFound("knowledge")
    await authorise(ctx, action, Resource.firm(ctx.tenant_id))
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    raise NotImplementedYet


# --- Knowledge catalog (KNW-01) ------------------------------------------------------------------


class MatchRangeOut(BaseModel):
    """Where the search matched in the title, for highlighting (start inclusive, end exclusive)."""

    model_config = ConfigDict(frozen=True)

    start: Annotated[int, classified("internal")]
    end: Annotated[int, classified("internal")]


class KnowledgeItemOut(BaseModel):
    """One catalog card from its provider: what it is, its state and how much it is used."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    category: Annotated[Category, classified("internal")]
    title: Annotated[str, classified("internal")]
    subtitle: Annotated[str | None, classified("internal")]
    status: Annotated[KnowledgeItemStatus, classified("internal")]
    version_label: Annotated[str | None, classified("internal")]
    effective_from: Annotated[date | None, classified("internal")]
    owner_name: Annotated[str | None, classified("internal")]
    # The registered usage counter's count over `visible()` (engagements pinned, returns using
    # a checklist); null when no counter is registered for the type.
    usage_count: Annotated[int | None, classified("internal")]
    updated_at: Annotated[datetime, classified("internal")]
    match: Annotated[list[MatchRangeOut], classified("internal")]
    route: Annotated[str, classified("internal")]


class ReviewQueueItemOut(BaseModel):
    """A version waiting on the viewer's approval, or a draft the viewer owns."""

    model_config = ConfigDict(frozen=True)

    category: Annotated[Category, classified("internal")]
    object_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("internal")]
    version_label: Annotated[str, classified("internal")]
    status: Annotated[MethodologyVersionStatus, classified("internal")]
    submitted_by_name: Annotated[str | None, classified("internal")]
    submitted_at: Annotated[datetime | None, classified("internal")]
    flags_open: Annotated[int, classified("internal")]
    route: Annotated[str, classified("internal")]


class ChangeActorOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["human", "agent", "system"], classified("internal")]
    user_id: Annotated[UUID | None, classified("internal")]
    name: Annotated[str | None, classified("internal")]
    # An agent's act shows "<person> via Agent" (INV-5): the person it acted for.
    on_behalf_of_user_id: Annotated[UUID | None, classified("internal")]


class ChangeLogEntryOut(BaseModel):
    """One lifecycle event across providers, oldest first within a page."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    category: Annotated[Category, classified("internal")]
    object_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("internal")]
    kind: Annotated[VersionEventKind, classified("internal")]
    actor: Annotated[ChangeActorOut, classified("internal")]
    facts: Annotated[dict[str, str | int | bool | None], classified("internal")]


knowledge_router = AbacusRouter(prefix="/v1/knowledge", tags=["knowledge"])


@knowledge_router.get(
    "/items", action="knowledge.read", response_model=ListPage[KnowledgeItemOut], errors=(501,)
)
async def knowledge_items_route(
    ctx: Ctx,
    category: Annotated[Category | None, Query()] = None,
    status: Annotated[KnowledgeItemStatus | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=200)] = None,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> ListPage[KnowledgeItemOut]:
    """KNW-01: catalog cards with category and status facets and match ranges."""
    await _stub(ctx, KNOWLEDGE_CATALOG, "knowledge.read")


@knowledge_router.get(
    "/review-queue",
    action="knowledge.read",
    response_model=ListPage[ReviewQueueItemOut],
    errors=(501,),
)
async def knowledge_review_queue_route(ctx: Ctx) -> ListPage[ReviewQueueItemOut]:
    """KNW-01: versions awaiting the viewer's approval, or the viewer's own drafts."""
    await _stub(ctx, KNOWLEDGE_CATALOG, "knowledge.read")


@knowledge_router.get(
    "/change-log",
    action="knowledge.read",
    response_model=ListPage[ChangeLogEntryOut],
    errors=(501,),
)
async def knowledge_change_log_route(
    ctx: Ctx,
    cursor: Annotated[str | None, Query(max_length=2000)] = None,
    limit: Annotated[int | None, Query(ge=1, le=200)] = None,
) -> ListPage[ChangeLogEntryOut]:
    """KNW-01: lifecycle events across providers (methodology version events first)."""
    await _stub(ctx, KNOWLEDGE_CATALOG, "knowledge.read")


# --- Methodology lifecycle (KNW-02 e, f) --------------------------------------------------------


class VersionStateOut(BaseModel):
    """A version's lifecycle row and what the viewer may do with it."""

    model_config = ConfigDict(frozen=True)

    version_id: Annotated[UUID, classified("internal")]
    template_id: Annotated[UUID, classified("internal")]
    label: Annotated[str, classified("internal")]
    status: Annotated[MethodologyVersionStatus, classified("internal")]
    effective_from: Annotated[date | None, classified("internal")]
    effective_to: Annotated[date | None, classified("internal")]
    approved_by_user_id: Annotated[UUID | None, classified("internal")]
    approved_by_name: Annotated[str | None, classified("internal")]
    approved_at: Annotated[datetime | None, classified("internal")]
    approval_basis: Annotated[ApprovalBasis | None, classified("internal")]
    standards_set_id: Annotated[UUID | None, classified("internal")]
    engagement_types: Annotated[list[str], classified("internal")]
    default_for_new_engagements: Annotated[bool, classified("internal")]
    drafted_from_version_id: Annotated[UUID | None, classified("internal")]
    row_version: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class SubmitVersionIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    row_version: Annotated[int, Field(ge=1), classified("internal")]


class ApproveVersionIn(BaseModel):
    """Approve what was reviewed: a changed checklist answers 409 `checklist_changed`; open flags
    `flags_open`; unverified sources `unverified_sources`. The prior published version is
    superseded from `effective_from`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    effective_from: Annotated[date, classified("internal")]
    checklist_hash: Annotated[ContentHash, classified("internal")]
    row_version: Annotated[int, Field(ge=1), classified("internal")]


methodology_lifecycle_router = AbacusRouter(prefix="/v1/methodology", tags=["methodology"])
VersionId = Annotated[UUID, Path()]


@methodology_lifecycle_router.post(
    "/versions/{version_id}/submit",
    action="methodology.manage",
    response_model=VersionStateOut,
    errors=(409, 501),
)
async def submit_version_route(
    version_id: VersionId, body: SubmitVersionIn, ctx: Ctx
) -> VersionStateOut:
    """KNW-02: Draft to Needs review."""
    await _stub(ctx, METHODOLOGY_LIFECYCLE, "methodology.manage")


@methodology_lifecycle_router.post(
    "/versions/{version_id}/approve",
    action="methodology.approve",
    response_model=VersionStateOut,
    errors=(409, 501),
)
async def approve_version_route(
    version_id: VersionId, body: ApproveVersionIn, ctx: Ctx
) -> VersionStateOut:
    """KNW-02 e: a quality partner approves with an effective date (human-only, fresh MFA)."""
    await _stub(ctx, METHODOLOGY_LIFECYCLE, "methodology.approve")


@methodology_lifecycle_router.post(
    "/versions/{version_id}/drafts",
    action="methodology.manage",
    response_model=VersionStateOut,
    status_code=201,
    errors=(409, 501),
)
async def create_draft_route(version_id: VersionId, ctx: Ctx) -> VersionStateOut:
    """KNW-03 c: a new draft vN+1 from a published version."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.manage")


@methodology_lifecycle_router.post(
    "/versions/{version_id}/discard",
    action="methodology.manage",
    response_model=VersionStateOut,
    errors=(409, 501),
)
async def discard_draft_route(
    version_id: VersionId, body: SubmitVersionIn, ctx: Ctx
) -> VersionStateOut:
    """KNW-03: discard a draft (published versions are never discarded)."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.manage")


# --- Programs and steps (KNW-03) -----------------------------------------------------------------


class GuidanceBlockOut(BaseModel):
    """Sanitised guidance: paragraphs, ordered lists and strong text only, never HTML."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[Literal["paragraph", "ordered_list"], classified("internal")]
    text: Annotated[str | None, classified("internal")]
    items: Annotated[list[str], classified("internal")]
    strong: Annotated[list[MatchRangeOut], classified("internal")]


class StepOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    step_key: Annotated[str, classified("internal")]
    anchor: Annotated[str, classified("internal")]  # "step_key@v3"
    number: Annotated[int, classified("internal")]
    text: Annotated[str, classified("internal")]
    assertions: Annotated[list[str], classified("internal")]
    standard_refs: Annotated[list[str], classified("internal")]
    level: Annotated[StepLevel, classified("internal")]
    mandatory: Annotated[bool, classified("internal")]
    lock_note: Annotated[str | None, classified("internal")]
    guidance: Annotated[list[GuidanceBlockOut], classified("internal")]
    prepopulates: Annotated[list[str], classified("internal")]
    depends_on_step_keys: Annotated[list[str], classified("internal")]
    pbc_positions: Annotated[list[int], classified("internal")]
    origin: Annotated[StepOrigin, classified("internal")]
    parse_flag: Annotated[ParseFlagStatus | None, classified("internal")]
    flag_resolution: Annotated[FlagResolution | None, classified("internal")]
    rules_count: Annotated[int, classified("internal")]
    row_version: Annotated[int, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class ProgramOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    version: Annotated[VersionStateOut, classified("internal")]
    code: Annotated[str, classified("internal")]  # "BH-EBP-110"
    name: Annotated[str, classified("internal")]
    position: Annotated[int, classified("internal")]
    step_count: Annotated[int, classified("internal")]
    mandatory_count: Annotated[int, classified("internal")]
    flags_open: Annotated[int, classified("internal")]
    counts_by_level: Annotated[dict[str, int], classified("internal")]


class StepResolveOut(BaseModel):
    """A citation target resolved: which program and step a `step_key@version` is now."""

    model_config = ConfigDict(frozen=True)

    version_id: Annotated[UUID, classified("internal")]
    program_id: Annotated[UUID, classified("internal")]
    program_code: Annotated[str, classified("internal")]
    step_id: Annotated[UUID, classified("internal")]
    number: Annotated[int, classified("internal")]
    anchor: Annotated[str, classified("internal")]


class StepPatchIn(BaseModel):
    """A draft step's edit; absent fields stay as they are. The citation anchor is kept."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[str | None, Field(min_length=1, max_length=4000), classified("internal")] = (
        None
    )
    assertions: Annotated[list[str] | None, classified("internal")] = None
    standard_refs: Annotated[list[str] | None, classified("internal")] = None
    level: Annotated[StepLevel | None, classified("internal")] = None
    guidance: Annotated[list[GuidanceBlockOut] | None, classified("internal")] = None


class StepCreateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    text: Annotated[str, Field(min_length=1, max_length=4000), classified("internal")]
    assertions: Annotated[list[str], classified("internal")] = Field(default_factory=list)
    standard_refs: Annotated[list[str], classified("internal")] = Field(default_factory=list)
    level: Annotated[StepLevel, classified("internal")]
    after_step_id: Annotated[UUID | None, classified("internal")] = None


class MandatoryIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    mandatory: Annotated[bool, classified("internal")]
    lock_note: Annotated[str | None, Field(max_length=200), classified("internal")] = None


class StepRemovedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    step_id: Annotated[UUID, classified("internal")]


programs_router = AbacusRouter(prefix="/v1/methodology", tags=["methodology"])
IfMatch = Annotated[int, Header(alias="If-Match", ge=1)]


@programs_router.get(
    "/programs/{program_id}", action="methodology.read", response_model=ProgramOut, errors=(501,)
)
async def program_route(program_id: Annotated[UUID, Path()], ctx: Ctx) -> ProgramOut:
    """KNW-03 a: a program with its version context, counts and rail rows."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.read")


@programs_router.get(
    "/programs/{program_id}/steps",
    action="methodology.read",
    response_model=list[StepOut],
    errors=(501,),
)
async def program_steps_route(program_id: Annotated[UUID, Path()], ctx: Ctx) -> list[StepOut]:
    """KNW-03 a, b: the program's steps in order."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.read")


@programs_router.get(
    "/steps/resolve", action="methodology.read", response_model=StepResolveOut, errors=(501,)
)
async def resolve_step_route(
    ctx: Ctx,
    key: Annotated[str, Query(pattern=r"^[a-z0-9][a-z0-9_.-]{0,79}$")],
    version: Annotated[UUID, Query()],
) -> StepResolveOut:
    """C4: a `methodology_step` citation target to its program and step number."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.read")


@programs_router.patch(
    "/versions/{version_id}/steps/{step_id}",
    action="methodology.manage",
    response_model=StepOut,
    errors=(409, 501),
)
async def edit_step_route(
    version_id: VersionId,
    step_id: Annotated[UUID, Path()],
    body: StepPatchIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> StepOut:
    """KNW-03 c: edit a draft step (409 `version_frozen` on a published version)."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.manage")


@programs_router.post(
    "/versions/{version_id}/programs/{program_id}/steps",
    action="methodology.manage",
    response_model=StepOut,
    status_code=201,
    errors=(409, 501),
)
async def add_step_route(
    version_id: VersionId,
    program_id: Annotated[UUID, Path()],
    body: StepCreateIn,
    ctx: Ctx,
) -> StepOut:
    """KNW-03 c: + Step in a draft."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.manage")


@programs_router.delete(
    "/versions/{version_id}/steps/{step_id}",
    action="methodology.manage",
    response_model=StepRemovedOut,
    errors=(409, 501),
)
async def remove_step_route(
    version_id: VersionId, step_id: Annotated[UUID, Path()], ctx: Ctx, if_match: IfMatch
) -> StepRemovedOut:
    """KNW-03 c: remove a non-mandatory draft step (409 `mandatory_locked`)."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.manage")


@programs_router.post(
    "/versions/{version_id}/steps/{step_id}/mandatory",
    action="methodology.approve",
    response_model=StepOut,
    errors=(409, 501),
)
async def mandatory_step_route(
    version_id: VersionId,
    step_id: Annotated[UUID, Path()],
    body: MandatoryIn,
    ctx: Ctx,
    if_match: IfMatch,
) -> StepOut:
    """KNW-03 d: a quality partner locks or unlocks a step (human-only, fresh MFA)."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.approve")


@programs_router.get(
    "/versions/{version_id}/export.xlsx",
    action="methodology.read",
    response_model=bytes,
    errors=(501,),
)
async def export_version_route(version_id: VersionId, ctx: Ctx) -> bytes:
    """KNW-03: the deterministic program workbook (an audit event per export)."""
    await _stub(ctx, METHODOLOGY_PROGRAMS, "methodology.read")
