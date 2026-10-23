"""C5 v1, the binders and requests half: the BND-01, BND-02 and SHL-14 family (P-06-T01 stub;
ADR-139, P-36). Contract: `docs/contracts/c5-requests-binders.md`; spec: SPEC-319.

Behind `binders.engine`: off, every route here answers 404; on, 501 `not_implemented` until the
task that implements it (P-06-T10 request lifecycle, P-06-T11 the index read model). P-06-T07
implements the binder lifecycle (`binders.py`): create, read, rows, publish and its Undo,
unpublish, duplicate, recipients, the client preview, activity and the client's mark-done. The
Brightwater Hale binder slice (`stub_from_seed`) arrives with P-06-T08, so the stubs return no
fixtures yet. Routes that already exist stay where they are: the request-item create
(extended additively by P-06-T10), client visibility, the client view, the SPEC-042 client
responses and the evidence decisions.

Binders are `request_lists` (DEC-31, F-03-T14); request statuses are C2's (DEC-09, F-03-T15). The
human-only actions (publish, send, return, delegate) are separate operations whose matrix rows
deny the agent (INV-1, ADR-005).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import BINDERS_ENGINE
from abacus.kernel._statuses import BinderStatus, EvidenceScreeningStatus, RequestStatus
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import flag_enabled
from abacus.kernel.listing import ListPage
from abacus.kernel.text import MultiLineText, SingleLineText
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context
from abacus.modules.requests import binders
from abacus.modules.requests.binders import engine_on

Ctx = Annotated[AuthContext, Depends(current_context)]
# ADR-139: every request with a client-visible effect carries one; the replay store is P-06-T06's.
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]

# Codes from the database CHECKs (F-03-T14, F-03-T15) and P-06 §4.2 (P-06-T05).
BinderKind = Literal["organizer", "pbc", "close_intake", "intake", "third_party"]
CreatedFrom = Literal["blank", "template", "prior_year_binder", "engine_import"]
ItemKind = Literal["client_upload", "firm_provided"]
Wave = Literal["planning", "year_end", "sample"]
NaReason = Literal["not_applicable_this_year", "already_sent", "dont_have", "firm_waived"]
# The client's reasons, as SPEC-042's "This doesn't apply" records them.
IgnoreReason = Literal["not_this_year", "sent_another_way", "dont_have"]
IncorporationState = Literal["none", "matched", "pending_incorporation", "incorporated"]
WordingSource = Literal["template", "model"]
LinkedKind = Literal["workpaper", "procedure_step", "k1_package"]
ActorKind = Literal["human", "agent", "system"]
ActivityFilter = Literal["any", "none_30_days"]


# --- Binders ------------------------------------------------------------------------------------


class FollowUpOverride(BaseModel):
    """The per-binder follow-up cadence R-01's scheduler reads (DEC-74; POR-20 at most 4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    every_days: Annotated[int, Field(ge=1, le=30), classified("internal")]
    max: Annotated[int, Field(ge=1, le=4), classified("internal")]


class BinderRecipientOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]


class BinderCategoryOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    position: Annotated[int, classified("internal")]
    done_count: Annotated[int, classified("internal")]
    total_count: Annotated[int, classified("internal")]


class BinderRowOut(BaseModel):
    """A BND-01 row. Counted and listed after `visible()`: a walled binder is absent (INV-3)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID | None, classified("internal")]
    client_name: Annotated[str, classified("confidential")]
    work_item_label: Annotated[str | None, classified("confidential")]
    name: Annotated[str, classified("confidential")]
    kind: Annotated[BinderKind, classified("internal")]
    part: Annotated[int, classified("internal")]
    status: Annotated[BinderStatus, classified("internal")]  # C2
    preparer_user_id: Annotated[UUID | None, classified("internal")]
    done_count: Annotated[int, classified("internal")]
    total_count: Annotated[int, classified("internal")]
    last_client_activity_at: Annotated[datetime | None, classified("internal")]
    unpublished_at: Annotated[datetime | None, classified("internal")] = None
    unpublished_by: Annotated[UUID | None, classified("internal")] = None
    unpublish_reason: Annotated[str | None, classified("confidential")] = None
    # Registered tag codes (the §7216 consents tag is P-07's / T-01's): codes, never prose.
    tags: Annotated[list[str], classified("internal")] = []
    allowed_actions: Annotated[list[str], classified("internal")] = []


class BinderOut(BaseModel):
    """The BND-02 record projection: rail, categories with counts, publish-bar facts."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    work_item_id: Annotated[UUID | None, classified("internal")]
    name: Annotated[str, classified("confidential")]
    kind: Annotated[BinderKind, classified("internal")]
    part: Annotated[int, classified("internal")]
    status: Annotated[BinderStatus, classified("internal")]  # C2
    created_from: Annotated[CreatedFrom, classified("internal")]
    prior_year_source_ref: Annotated[UUID | None, classified("internal")] = None
    template_ref: Annotated[str | None, classified("internal")] = None
    default_due_on: Annotated[date | None, classified("internal")] = None
    recipients: Annotated[list[BinderRecipientOut], classified("internal")] = []
    categories: Annotated[list[BinderCategoryOut], classified("internal")] = []
    done_count: Annotated[int, classified("internal")] = 0
    total_count: Annotated[int, classified("internal")] = 0
    published_at: Annotated[datetime | None, classified("internal")] = None
    published_by: Annotated[UUID | None, classified("internal")] = None
    unpublished_at: Annotated[datetime | None, classified("internal")] = None
    unpublished_by: Annotated[UUID | None, classified("internal")] = None
    unpublish_reason: Annotated[str | None, classified("confidential")] = None
    marked_done_at: Annotated[datetime | None, classified("internal")] = None
    marked_done_by: Annotated[UUID | None, classified("internal")] = None
    marked_done_open_count: Annotated[int | None, classified("internal")] = None
    closed_at: Annotated[datetime | None, classified("internal")] = None
    closed_reason: Annotated[str | None, classified("internal")] = None  # a registered rule code
    follow_up_override: Annotated[FollowUpOverride | None, classified("internal")] = None
    # The 10-s Undo window of the last publish, while it is open (DEC-24, ADR-161).
    undo_until: Annotated[datetime | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class BinderIn(BaseModel):
    """Create a Draft: blank, from a firm template, or from the prior-year binder."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    work_item_id: Annotated[UUID, classified("internal")]
    kind: Annotated[BinderKind, classified("internal")]
    name: Annotated[
        SingleLineText | None,
        Field(default=None, min_length=1, max_length=200),
        classified("confidential"),
    ]
    from_binder_id: Annotated[UUID | None, classified("internal")] = None
    template_ref: Annotated[
        str | None, Field(default=None, min_length=1, max_length=200), classified("internal")
    ]


class UnpublishIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[
        SingleLineText, Field(min_length=1, max_length=300), classified("confidential")
    ]


class RecipientsIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contact_ids: Annotated[list[UUID], Field(max_length=50), classified("internal")]


class FollowUpOverrideIn(BaseModel):
    """`null` clears the override; the firm's cadence applies again."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    override: Annotated[FollowUpOverride | None, classified("internal")]


class LinkedRefOut(BaseModel):
    """An opaque reference to what a request supports (a workpaper, a step, a K-1 package)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[LinkedKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class BinderRequestRowOut(BaseModel):
    """A BND-02 row. Client principals never receive a Draft or an internal-only row (INV-4)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    category_id: Annotated[UUID | None, classified("internal")]
    title: Annotated[str, classified("confidential")]
    status: Annotated[RequestStatus, classified("internal")]  # C2 (DEC-09)
    overdue: Annotated[bool, classified("internal")]  # derived, never stored
    client_visible: Annotated[bool, classified("internal")]
    kind: Annotated[ItemKind, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None
    requested_at: Annotated[datetime | None, classified("internal")] = None
    client_ignored_at: Annotated[datetime | None, classified("internal")] = None
    client_ignore_reason: Annotated[IgnoreReason | None, classified("internal")] = None
    source_tag: Annotated[Literal["prior_year"] | None, classified("internal")] = None
    incorporation_state: Annotated[IncorporationState, classified("internal")] = "none"
    # The 12 px glyph only; the card's text is SHL-20's (P-06-T15) and never `client_service`'s.
    screening: Annotated[EvidenceScreeningStatus | None, classified("internal")] = None
    linked_count: Annotated[int | None, classified("internal")] = None  # "Linked (n)"; K-04
    upload_count: Annotated[int, classified("internal")] = 0
    allowed_actions: Annotated[list[str], classified("internal")] = []


class LiveItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    uploading_files: Annotated[int, classified("internal")]  # "Uploading 2 files…"
    inbox_waiting: Annotated[int, classified("internal")]  # "Waiting 2"
    screening_running: Annotated[bool, classified("internal")]


class BinderLiveOut(BaseModel):
    """What BND-02 polls every 5 s while visible (DEC-23, DV-3)."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[LiveItemOut], classified("internal")]
    as_of: Annotated[datetime, classified("internal")]


class ClientPreviewItemOut(BaseModel):
    """A request as the client sees it: the portal projection, never internal fields."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    category_name: Annotated[str | None, classified("confidential")]
    title: Annotated[str, classified("confidential")]
    description: Annotated[str, classified("confidential")]  # the client wording
    status: Annotated[RequestStatus, classified("internal")]  # client words from C2's client_label
    client_ignored: Annotated[bool, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None


class BinderClientPreviewOut(BaseModel):
    """POR-03 as a recipient will see it, for BND-02's "Preview as client" sheet."""

    model_config = ConfigDict(frozen=True)

    binder_id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    status: Annotated[BinderStatus, classified("internal")]
    items: Annotated[list[ClientPreviewItemOut], classified("internal")]


class ActivityEventOut(BaseModel):
    """One audit event, identifiers only, through `audit_trail.api` (§4.7). The UI words it;
    a withdrawn upload never carries its file name (ADR-162)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    event_type: Annotated[str, classified("internal")]
    at: Annotated[datetime, classified("internal")]
    actor_kind: Annotated[ActorKind, classified("internal")]
    actor_user_id: Annotated[UUID | None, classified("internal")] = None
    # "<person> via Agent": the person who adopted an agent's draft (INV-5).
    via_agent: Annotated[bool, classified("internal")] = False
    target_type: Annotated[str, classified("internal")]
    target_id: Annotated[UUID, classified("internal")]


class BinderMarkedDoneOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    binder_id: Annotated[UUID, classified("internal")]
    status: Annotated[BinderStatus, classified("internal")]
    marked_done_at: Annotated[datetime, classified("internal")]
    open_count: Annotated[int, classified("internal")]


# --- Request items, lifecycle v2 ----------------------------------------------------------------


class RequestItemV2Out(BaseModel):
    """The SHL-14 record: the extended request (P-06 §4.2) with its `allowed_actions`."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID | None, classified("internal")]
    category_id: Annotated[UUID | None, classified("internal")] = None
    title: Annotated[str | None, classified("confidential")] = None
    description: Annotated[str, classified("confidential")]  # the client wording
    status: Annotated[RequestStatus, classified("internal")]  # C2 (DEC-09)
    overdue: Annotated[bool, classified("internal")] = False
    client_visible: Annotated[bool, classified("internal")]
    kind: Annotated[ItemKind, classified("internal")] = "client_upload"
    wave: Annotated[Wave | None, classified("internal")] = None
    period_start: Annotated[date | None, classified("internal")] = None
    period_end: Annotated[date | None, classified("internal")] = None
    due_on: Annotated[date | None, classified("internal")] = None
    client_assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    firm_owner_user_id: Annotated[UUID | None, classified("internal")] = None
    supports_ref: Annotated[str | None, classified("confidential")] = None
    linked_ref: Annotated[LinkedRefOut | None, classified("internal")] = None
    source_tag: Annotated[Literal["prior_year"] | None, classified("internal")] = None
    requested_at: Annotated[datetime | None, classified("internal")] = None
    sent_at: Annotated[datetime | None, classified("internal")] = None
    sent_by: Annotated[UUID | None, classified("internal")] = None  # always a person (INV-5)
    drafted_by_run_id: Annotated[UUID | None, classified("internal")] = None
    drafted_wording_source: Annotated[WordingSource | None, classified("internal")] = None
    na_reason: Annotated[NaReason | None, classified("internal")] = None
    na_by: Annotated[UUID | None, classified("internal")] = None
    na_at: Annotated[datetime | None, classified("internal")] = None
    client_ignored_at: Annotated[datetime | None, classified("internal")] = None
    incorporation_state: Annotated[IncorporationState, classified("internal")] = "none"
    incorporated_by: Annotated[UUID | None, classified("internal")] = None
    incorporated_at: Annotated[datetime | None, classified("internal")] = None
    undo_until: Annotated[datetime | None, classified("internal")] = None
    allowed_actions: Annotated[list[str], classified("internal")] = []


class LinkedRefIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: Annotated[LinkedKind, classified("internal")]
    id: Annotated[UUID, classified("internal")]


class RequestItemPatchIn(BaseModel):
    """Edit any non-terminal request (SHL-14 b). Absent fields are unchanged."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    title: Annotated[
        SingleLineText | None,
        Field(default=None, min_length=1, max_length=200),
        classified("confidential"),
    ]
    description: Annotated[
        MultiLineText | None,
        Field(default=None, min_length=1, max_length=2000),
        classified("confidential"),
    ]
    category_id: Annotated[UUID | None, classified("internal")] = None
    period_start: Annotated[date | None, classified("internal")] = None
    period_end: Annotated[date | None, classified("internal")] = None
    due_on: Annotated[date | None, classified("internal")] = None
    wave: Annotated[Wave | None, classified("internal")] = None
    client_assignee_user_id: Annotated[UUID | None, classified("internal")] = None
    firm_owner_user_id: Annotated[UUID | None, classified("internal")] = None
    supports_ref: Annotated[
        SingleLineText | None,
        Field(default=None, min_length=1, max_length=200),
        classified("confidential"),
    ]
    linked_ref: Annotated[LinkedRefIn | None, classified("internal")] = None


class WaiveIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    na_reason: Annotated[NaReason, classified("internal")]
    note: Annotated[
        MultiLineText, Field(min_length=1, max_length=1000), classified("confidential")
    ]


class ReturnToClientIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    note: Annotated[
        MultiLineText | None,
        Field(default=None, min_length=1, max_length=1000),
        classified("confidential"),
    ]


class DelegateIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contact_id: Annotated[UUID, classified("internal")]


class DelegationOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    contact_id: Annotated[UUID, classified("internal")]
    grant_id: Annotated[UUID, classified("internal")]  # identity's `request_item` grant (P-09)
    granted_by: Annotated[UUID, classified("internal")]
    granted_at: Annotated[datetime, classified("internal")]


class RequestItemDeletedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    deleted_at: Annotated[datetime, classified("internal")]


# --- Portal (the client's side; P-08's portal principal replaces the firm context) --------------


class IgnoreIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    reason: Annotated[IgnoreReason, classified("internal")]
    note: Annotated[
        MultiLineText | None,
        Field(default=None, min_length=1, max_length=500),
        classified("confidential"),
    ]


class IgnoredOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    status: Annotated[RequestStatus, classified("internal")]  # stays `requested` (OQ-3)
    client_ignored_at: Annotated[datetime, classified("internal")]


class UploadIntentIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    files_expected: Annotated[int, Field(ge=1, le=50), classified("internal")]


class UploadIntentOut(BaseModel):
    """Lives 90 s; R-01 posts it again while the upload runs (UNLOGGED, swept)."""

    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    files_expected: Annotated[int, classified("internal")]
    expires_at: Annotated[datetime, classified("internal")]


def _binder(view: binders.BinderView) -> BinderOut:
    return BinderOut.model_validate(view, from_attributes=True)


async def _stub(ctx: AuthContext) -> NoReturn:
    if not await flag_enabled(ctx.tenant, BINDERS_ENGINE):
        raise NotFound("binders.engine")
    raise NotImplementedYet


binders_router = AbacusRouter(prefix="/v1/binders", tags=["binders"])
items_router = AbacusRouter(
    prefix="/v1/engagements/{engagement_id}/request-items", tags=["requests"]
)
portal_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


# --- /v1/binders (P-06-T07, T11) ----------------------------------------------------------------


@binders_router.get("", action="binder.read", response_model=ListPage[BinderRowOut], errors=(501,))
async def list_binders_route(
    ctx: Ctx,
    service: Annotated[str | None, Query(max_length=40)] = None,
    season: Annotated[str | None, Query(max_length=20)] = None,
    office: Annotated[UUID | None, Query()] = None,
    preparer: Annotated[UUID | None, Query()] = None,
    client_activity: Annotated[ActivityFilter, Query()] = "any",
    status: Annotated[BinderStatus | None, Query()] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> ListPage[BinderRowOut]:
    """BND-01 rows, tiles (`counts` per status) and facets, after `visible()` (INV-3)."""
    await _stub(ctx)


@binders_router.post(
    "", action="binder.create", response_model=BinderOut, status_code=201, errors=(409,)
)
async def create_binder_route(body: BinderIn, ctx: Ctx) -> BinderOut:
    """A Draft binder on a work item (DEC-31: many per work item): blank, from a firm template,
    or from the prior-year binder (P-06-T07)."""
    await engine_on(ctx)
    view = await binders.create_binder(
        ctx,
        work_item_id=body.work_item_id,
        kind=body.kind,
        name=body.name,
        from_binder_id=body.from_binder_id,
        template_ref=body.template_ref,
    )
    return _binder(view)


@binders_router.get("/{binder_id}", action="binder.read", response_model=BinderOut)
async def get_binder_route(binder_id: UUID, ctx: Ctx) -> BinderOut:
    await engine_on(ctx)
    return _binder(await binders.read_binder(ctx, binder_id))


@binders_router.get(
    "/{binder_id}/requests",
    action="request_item.read",
    response_model=ListPage[BinderRequestRowOut],
)
async def binder_requests_route(
    binder_id: UUID,
    ctx: Ctx,
    category: Annotated[UUID | None, Query()] = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> ListPage[BinderRequestRowOut]:
    """BND-02 rows by category; `counts` per request status."""
    await engine_on(ctx)
    page = await binders.binder_requests(ctx, binder_id, category, cursor)
    return ListPage[BinderRequestRowOut](
        items=[BinderRequestRowOut.model_validate(r, from_attributes=True) for r in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
        total_capped=page.total_capped,
        counts=page.counts,
    )


@binders_router.get(
    "/{binder_id}/live", action="request_item.read", response_model=BinderLiveOut, errors=(501,)
)
async def binder_live_route(binder_id: UUID, ctx: Ctx) -> BinderLiveOut:
    await _stub(ctx)


@binders_router.post(
    "/{binder_id}/publish", action="binder.publish", response_model=BinderOut, errors=(409,)
)
async def publish_binder_route(
    binder_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> BinderOut:
    """Human-only. Draft or Unpublished to Published; G3 first except `intake` (409
    `binder_gate_unmet`); 422 `due_date_required`; email after the 10-s Undo window. A retry
    with the same key answers what the first answered and sends nothing again."""
    await engine_on(ctx)
    await binders.check_action(ctx, binder_id, "binder.publish")

    async def run() -> tuple[int, dict[str, object]]:
        view = await binders.publish_binder(ctx, binder_id)
        return 200, _binder(view).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="binder.publish",
        key=idempotency_key,
        body={"binder_id": str(binder_id)},
        run=run,
    )
    return BinderOut.model_validate(stored.body)


@binders_router.post(
    "/{binder_id}/publish/undo",
    action="binder.publish",
    response_model=BinderOut,
    errors=(409,),
)
async def undo_publish_binder_route(binder_id: UUID, ctx: Ctx) -> BinderOut:
    """Within 10 s: `binder.publish_undone`, nothing sent (409 `undo_window_closed`; 409
    `effect_started` once the delivery has begun)."""
    await engine_on(ctx)
    return _binder(await binders.undo_publish(ctx, binder_id))


@binders_router.post(
    "/{binder_id}/unpublish", action="binder.publish", response_model=BinderOut, errors=(409,)
)
async def unpublish_binder_route(binder_id: UUID, body: UnpublishIn, ctx: Ctx) -> BinderOut:
    """Published to Unpublished with a reason: client principals get 404 at once (INV-4)."""
    await engine_on(ctx)
    return _binder(await binders.unpublish_binder(ctx, binder_id, body.reason))


@binders_router.post(
    "/{binder_id}/duplicate",
    action="binder.create",
    response_model=BinderOut,
    status_code=201,
    errors=(409,),
)
async def duplicate_binder_route(binder_id: UUID, ctx: Ctx) -> BinderOut:
    """ "Duplicate as pt 2": an empty Draft, same recipients and categories (OQ-7)."""
    await engine_on(ctx)
    return _binder(await binders.duplicate_binder(ctx, binder_id))


@binders_router.put(
    "/{binder_id}/recipients", action="binder.update", response_model=BinderOut, errors=(409,)
)
async def set_binder_recipients_route(binder_id: UUID, body: RecipientsIn, ctx: Ctx) -> BinderOut:
    """The engagement's client's contacts the binder is for (insert-only history)."""
    await engine_on(ctx)
    return _binder(await binders.set_recipients(ctx, binder_id, body.contact_ids))


@binders_router.put(
    "/{binder_id}/follow-up-override",
    action="binder.update",
    response_model=BinderOut,
    errors=(501,),
)
async def set_binder_follow_up_override_route(
    binder_id: UUID, body: FollowUpOverrideIn, ctx: Ctx
) -> BinderOut:
    await _stub(ctx)


@binders_router.get(
    "/{binder_id}/client-preview",
    action="binder.read",
    response_model=BinderClientPreviewOut,
)
async def binder_client_preview_route(binder_id: UUID, ctx: Ctx) -> BinderClientPreviewOut:
    await engine_on(ctx)
    view = await binders.client_preview(ctx, binder_id)
    return BinderClientPreviewOut.model_validate(view, from_attributes=True)


@binders_router.get(
    "/{binder_id}/activity",
    action="activity.read",
    response_model=ListPage[ActivityEventOut],
)
async def binder_activity_route(
    binder_id: UUID, ctx: Ctx, cursor: Annotated[str | None, Query(max_length=512)] = None
) -> ListPage[ActivityEventOut]:
    """The binder's and its requests' audit events, newest first, identifiers only."""
    await engine_on(ctx)
    page = await binders.binder_activity(ctx, binder_id, cursor)
    return ListPage[ActivityEventOut](
        items=[ActivityEventOut.model_validate(e, from_attributes=True) for e in page.items],
        next_cursor=page.next_cursor,
        total=page.total,
        total_capped=page.total_capped,
    )


# --- /v1/engagements/{engagement_id}/request-items: lifecycle v2 (P-06-T10) ---------------------


@items_router.patch(
    "/{item_id}", action="request_item.update", response_model=RequestItemV2Out, errors=(409, 501)
)
async def update_request_item_route(
    engagement_id: UUID, item_id: UUID, body: RequestItemPatchIn, ctx: Ctx
) -> RequestItemV2Out:
    await _stub(ctx)


@items_router.delete(
    "/{item_id}",
    action="request_item.update",
    response_model=RequestItemDeletedOut,
    errors=(409, 501),
)
async def delete_request_item_route(
    engagement_id: UUID, item_id: UUID, ctx: Ctx
) -> RequestItemDeletedOut:
    """Never-sent Drafts only (soft); a sent one answers 409 `request_already_sent`."""
    await _stub(ctx)


@items_router.post(
    "/{item_id}/send",
    action="request_item.send",
    response_model=RequestItemV2Out,
    errors=(409, 501),
)
async def send_request_item_route(
    engagement_id: UUID, item_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> RequestItemV2Out:
    """Human-only. Draft to Requested: 422 `due_date_required`, 409 `out_of_scope`, 409
    `model_text_not_permitted` (DV-11); email after the 10-s Undo window."""
    await _stub(ctx)


@items_router.post(
    "/{item_id}/send/undo",
    action="request_item.send",
    response_model=RequestItemV2Out,
    errors=(409, 501),
)
async def undo_send_request_item_route(
    engagement_id: UUID, item_id: UUID, ctx: Ctx
) -> RequestItemV2Out:
    await _stub(ctx)


@items_router.post(
    "/{item_id}/waive",
    action="request_item.waive",
    response_model=RequestItemV2Out,
    errors=(409, 501),
)
async def waive_request_item_route(
    engagement_id: UUID, item_id: UUID, body: WaiveIn, ctx: Ctx
) -> RequestItemV2Out:
    """To `not_applicable` with a reason (Story 4.1)."""
    await _stub(ctx)


@items_router.post(
    "/{item_id}/return-to-client",
    action="request_item.return",
    response_model=RequestItemV2Out,
    errors=(409, 501),
)
async def return_request_item_to_client_route(
    engagement_id: UUID,
    item_id: UUID,
    body: ReturnToClientIn,
    ctx: Ctx,
    idempotency_key: IdempotencyKey,
) -> RequestItemV2Out:
    """Human-only. Clears a client Ignore; the client is told after the Undo window."""
    await _stub(ctx)


@items_router.post(
    "/{item_id}/delegate",
    action="request_item.delegate",
    response_model=DelegationOut,
    status_code=201,
    errors=(409, 501),
)
async def delegate_request_item_route(
    engagement_id: UUID, item_id: UUID, body: DelegateIn, ctx: Ctx
) -> DelegationOut:
    """A third party gets this one request (P-09 `scope_kind=request_item`)."""
    await _stub(ctx)


@items_router.post(
    "/{item_id}/incorporate",
    action="request_item.update",
    response_model=RequestItemV2Out,
    errors=(409, 501),
)
async def incorporate_request_item_route(
    engagement_id: UUID, item_id: UUID, ctx: Ctx
) -> RequestItemV2Out:
    """Close variant: `pending_incorporation` to `incorporated` (SHL-14 d)."""
    await _stub(ctx)


@items_router.get(
    "/{item_id}/activity",
    action="activity.read",
    response_model=ListPage[ActivityEventOut],
    errors=(501,),
)
async def request_item_activity_route(
    engagement_id: UUID,
    item_id: UUID,
    ctx: Ctx,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
) -> ListPage[ActivityEventOut]:
    await _stub(ctx)


# --- /v1/portal (the client; P-06-T07, T10) ----------------------------------------------------


@portal_router.post(
    "/binders/{binder_id}/mark-done",
    action="binder.mark_done",
    response_model=BinderMarkedDoneOut,
    errors=(409,),
)
async def mark_binder_done_route(binder_id: UUID, ctx: Ctx) -> BinderMarkedDoneOut:
    """The client: Published to Complete, with the open count at that moment (OQ-8)."""
    await engine_on(ctx)
    view = await binders.mark_done(ctx, binder_id)
    return BinderMarkedDoneOut.model_validate(view, from_attributes=True)


@portal_router.post(
    "/request-items/{item_id}/ignore",
    action="request_item.ignore",
    response_model=IgnoredOut,
    errors=(409, 501),
)
async def ignore_request_item_route(item_id: UUID, body: IgnoreIn, ctx: Ctx) -> IgnoredOut:
    """The client's Ignore, with a reason; the firm returns or waives (OQ-3)."""
    await _stub(ctx)


@portal_router.post(
    "/request-items/{item_id}/upload-intents",
    action="evidence.upload",
    response_model=UploadIntentOut,
    status_code=201,
    errors=(501,),
)
async def announce_upload_intent_route(
    item_id: UUID, body: UploadIntentIn, ctx: Ctx
) -> UploadIntentOut:
    """R-01 announces an upload in progress, for BND-02's "Uploading n files…"."""
    await _stub(ctx)
