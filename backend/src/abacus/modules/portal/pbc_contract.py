"""C5 section `portal-pbc`, the portal read models (R-01-T01 stub; ADR P-36, ADR-139).
Contract: `docs/contracts/portal-pbc.md`; screens POR-03, POR-04 and POR-14.

The binder picker, the POR-03 binder, the POR-04 request, the POR-14 third-party room with its
code-only suggest, and the poll of a drop batch. The writes of the family live with their owners:
ignore and mark-done undo and the firm's void of a rule fulfilment in `requests/pbc_contract.py`,
the drop itself in `evidence/drops_contract.py`.

Behind `portal.documents_v2` (binders, request), `portal.third_party_room` (room, suggest) and
`portal.drop_sort` (drop batches): off, each route answers 404; on, 501 `not_implemented` until
R-01-T07 (documents) and R-01-T13 (room) land; the drop poll is served (R-01-T09).

These are a client's views. No field carries a firm status code, an amount, a confidence, a
screening verdict, an agent name or another party's data: rows carry the client words (`to_do`,
`done`, `ignored`, `returned`), receipts carry a kind and a date, and the words come from the
frontend copy registry (ADR P-36 code to words). Every list is filtered by the caller's grant
(`scope_only`; a third party's room by its delegations), so nothing outside it is even counted
(INV-4). Fixed words only: no model text reaches a client (ADR P-25 off).
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal, NoReturn, cast
from uuid import UUID

from fastapi import Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel._flags import PORTAL_DOCUMENTS_V2, PORTAL_DROP_SORT, PORTAL_THIRD_PARTY_ROOM
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.kernel.flags import Flag, flag_enabled
from abacus.kernel.text import SingleLineText
from abacus.modules.evidence.api import drop_batch
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member

# A portal person themself, never a break-glass support context.
Member = Annotated[AuthContext, Depends(current_member)]

# The client words of a request (status registry `client_label`: To do · Done · Ignored ·
# Returned). Never the firm's status code.
ClientStatus = Literal["to_do", "done", "ignored", "returned"]
# How a file reached a request, as the client may read it. `rule_linked_pending` is a code-rule
# fulfilment no person has accepted yet ("Suggested — Brightwater Hale will confirm", DEC-58 a).
ReceiptKind = Literal[
    "uploaded", "uploaded_by_other_contact", "emailed", "rule_linked_pending", "received"
]
# The portal's whole action vocabulary; a record lists the ones the caller may take now.
PortalAction = Literal[
    "upload", "ignore", "undo_ignore", "withdraw", "mark_done", "undo_mark_done", "comment"
]
# A firm-provided row ("Brightwater Hale prepares this… Nothing to upload") and a row a
# connection fulfils ("Provided from your accounting system", DEC-58 f) have no client action.
RowKind = Literal["request", "firm_provided", "provided_by_connection"]
BinderFilter = Literal["requested", "all", "uploaded_by_me", "needs_follow_up"]
# Mark as Done: tonal while requests are open, ready (olive) when none are, marked after it.
MarkDoneState = Literal["tonal", "ready", "marked"]
# The send-back reason the client reads ("Returned · wrong year"). DEC-240: P-06's return carries
# no reason yet; R-01-T07 maps the firm's return onto these codes.
ReturnReason = Literal["wrong_year", "wrong_period", "other"]
# The mechanical pre-checks a client may see, in fixed words (DEC-58 e; `ClientUploadChecks`).
PreCheckCode = Literal["wrong_period", "wrong_entity", "stale_as_of", "totals_dont_add_up"]
# POR-04's sheet variants: only `request` is served; `question` (C-01) and `decision`
# (T-06, T-09) are typed slots that their epics wire to their own routes.
SheetVariant = Literal["request", "question", "decision"]
# A drop's per-file outcome (R-01-T09).
DropOutcome = Literal["rule_linked", "waiting", "duplicate_flagged", "refused"]
DropRefusal = Literal["file_too_large", "type_not_allowed"]
# A room row's sub-line: "Uploaded Sep 2", "Due Sep 18", "You uploaded Sep 22 · Brightwater Hale
# is reviewing it", "Returned · wrong period".
RoomRowState = Literal["uploaded", "due", "in_review", "returned"]
Disc = Literal["done", "ring"]


class PortalBinderRefOut(BaseModel):
    """One binder in the picker ("2025 Binder", "2024 Binder (closed)")."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    year: Annotated[int | None, classified("internal")] = None
    closed: Annotated[bool, classified("internal")]
    read_only: Annotated[bool, classified("internal")]


class PortalBinderListOut(BaseModel):
    """The P-36 list envelope; every binder the caller's grants can see."""

    model_config = ConfigDict(frozen=True)

    items: Annotated[list[PortalBinderRefOut], classified("internal")]
    next_cursor: Annotated[str | None, classified("internal")] = None
    total: Annotated[int, classified("internal")]


class PortalCategoryOut(BaseModel):
    """A rail category. `complete` is computed by code: every request in it done or ignored."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    complete: Annotated[bool, classified("internal")]
    requested: Annotated[int, classified("internal")]


class PortalReceiptOut(BaseModel):
    """ "You uploaded Aug 7", "Jonah uploaded Aug 5", "Received by email Aug 3"."""

    model_config = ConfigDict(frozen=True)

    kind: Annotated[ReceiptKind, classified("internal")]
    on: Annotated[date, classified("internal")]
    by_first_name: Annotated[str | None, classified("confidential")] = None


class PortalFileOut(BaseModel):
    """A file on a request. A withdrawn file is never listed; `withdrawable` only for the
    caller's own unaccepted upload (never emailed, never accepted; ADR P-31)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    name: Annotated[str, classified("confidential")]
    size_bytes: Annotated[int | None, classified("internal")] = None
    receipt: Annotated[PortalReceiptOut, classified("internal")]
    withdrawable: Annotated[bool, classified("internal")]
    struck: Annotated[bool, classified("internal")] = False


class PortalReturnedOut(BaseModel):
    """The firm's client-visible send-back note, with its author's name and date."""

    model_config = ConfigDict(frozen=True)

    reason: Annotated[ReturnReason, classified("internal")]
    note: Annotated[str | None, classified("confidential")] = None
    by_name: Annotated[str, classified("confidential")]
    on: Annotated[date, classified("internal")]


class PortalRowOut(BaseModel):
    """One request as the client sees it on POR-03."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    kind: Annotated[RowKind, classified("internal")]
    client_status: Annotated[ClientStatus, classified("internal")]
    files: Annotated[list[PortalFileOut], classified("internal")] = []
    returned: Annotated[PortalReturnedOut | None, classified("internal")] = None
    ignored_on: Annotated[date | None, classified("internal")] = None
    due_on: Annotated[date | None, classified("internal")] = None
    uploading_count: Annotated[int, classified("internal")] = 0
    allowed_actions: Annotated[list[PortalAction], classified("internal")] = []


class PortalGroupOut(BaseModel):
    """A section card ("Health insurance") on the household layout."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    category_code: Annotated[str, classified("internal")]
    rows: Annotated[list[PortalRowOut], classified("internal")]


class PortalBandOut(BaseModel):
    """A folder band ("Census & Payroll") on the audit layout (POR-03 i)."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    rows: Annotated[list[PortalRowOut], classified("internal")]


class PortalMarkDoneOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: Annotated[MarkDoneState, classified("internal")]
    marked_on: Annotated[date | None, classified("internal")] = None
    marked_by_name: Annotated[str | None, classified("confidential")] = None


class PortalBinderOut(BaseModel):
    """POR-03: one binder through the caller's grant. `open_count` is the same figure POR-02's
    "Upload 2 documents" and TAX-03's "Intake 2" read (one read model). `other_parties` names
    the organisations requests were delegated to, for admin grants only, never their titles."""

    model_config = ConfigDict(frozen=True)

    binder: Annotated[PortalBinderRefOut, classified("internal")]
    layout: Annotated[Literal["groups", "bands"], classified("internal")]
    filter: Annotated[BinderFilter, classified("internal")]
    categories: Annotated[list[PortalCategoryOut], classified("internal")]
    groups: Annotated[list[PortalGroupOut], classified("internal")] = []
    bands: Annotated[list[PortalBandOut], classified("internal")] = []
    total: Annotated[int, classified("internal")]
    done_count: Annotated[int, classified("internal")]
    open_count: Annotated[int, classified("internal")]
    sorted_count: Annotated[int, classified("internal")]
    mark_done: Annotated[PortalMarkDoneOut, classified("internal")]
    other_parties: Annotated[list[str], classified("confidential")] = []
    allowed_actions: Annotated[list[PortalAction], classified("internal")] = []


class PortalCategoryRefOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]


class PortalPriorYearOut(BaseModel):
    """ "Last year you sent … on Mar 3, 2025." (the prior year's fulfilment, roll-forward)."""

    model_config = ConfigDict(frozen=True)

    file_name: Annotated[str, classified("confidential")]
    sent_on: Annotated[date, classified("internal")]


class PortalRequestOut(BaseModel):
    """POR-04: one request in the sheet. `guidance` is firm-written only (SPEC-031 fields or an
    approved draft; never unapproved model text, ADR-111)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID, classified("internal")]
    variant: Annotated[SheetVariant, classified("internal")] = "request"
    category: Annotated[PortalCategoryRefOut, classified("internal")]
    title: Annotated[str, classified("confidential")]
    client_status: Annotated[ClientStatus, classified("internal")]
    requested_on: Annotated[date, classified("internal")]
    due_on: Annotated[date | None, classified("internal")] = None
    guidance: Annotated[str | None, classified("confidential")] = None
    prior_year: Annotated[PortalPriorYearOut | None, classified("internal")] = None
    files: Annotated[list[PortalFileOut], classified("internal")] = []
    returned: Annotated[PortalReturnedOut | None, classified("internal")] = None
    pre_checks: Annotated[list[PreCheckCode], classified("internal")] = []
    comment_count: Annotated[int, classified("internal")] = 0
    uploading_count: Annotated[int, classified("internal")] = 0
    allowed_actions: Annotated[list[PortalAction], classified("internal")] = []


class PortalRoomRowOut(BaseModel):
    """One delegated request in the third-party room (POR-14)."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    state: Annotated[RoomRowState, classified("internal")]
    state_on: Annotated[date | None, classified("internal")] = None
    disc: Annotated[Disc, classified("internal")]
    guidance: Annotated[str | None, classified("confidential")] = None
    files: Annotated[list[PortalFileOut], classified("internal")] = []
    returned: Annotated[PortalReturnedOut | None, classified("internal")] = None
    comment_count: Annotated[int, classified("internal")] = 0
    allowed_actions: Annotated[list[PortalAction], classified("internal")] = []


class PortalRoomBandOut(BaseModel):
    """ "Recordkeeper reports · 3 of 5"."""

    model_config = ConfigDict(frozen=True)

    code: Annotated[str, classified("internal")]
    label: Annotated[str, classified("confidential")]
    uploaded: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    rows: Annotated[list[PortalRoomRowOut], classified("internal")]


class PortalRoomOut(BaseModel):
    """POR-14: exactly the caller's delegated items, "n of N". `intro` is firm-written request
    guidance (the custodian's ERISA §103(a)(3)(C) line is database content, not a constant)."""

    model_config = ConfigDict(frozen=True)

    engagement_label: Annotated[str, classified("confidential")]
    firm_name: Annotated[str, classified("public")]
    organisation_name: Annotated[str, classified("confidential")]
    intro: Annotated[str | None, classified("confidential")] = None
    uploaded_count: Annotated[int, classified("internal")]
    total: Annotated[int, classified("internal")]
    complete: Annotated[bool, classified("internal")]
    bands: Annotated[list[PortalRoomBandOut], classified("internal")]


class RoomSuggestIn(BaseModel):
    """File names only: the suggest never sees content (code-only scoring, ADR-050)."""

    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)

    file_names: Annotated[
        list[Annotated[SingleLineText, Field(min_length=1, max_length=255)]],
        Field(min_length=1, max_length=20),
        classified("confidential"),
    ]


class RoomSuggestionOut(BaseModel):
    """`request_item_id` is null when no delegated item wins; the person chooses."""

    model_config = ConfigDict(frozen=True)

    file_name: Annotated[str, classified("confidential")]
    request_item_id: Annotated[UUID | None, classified("internal")] = None


class RoomSuggestOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    suggestions: Annotated[list[RoomSuggestionOut], classified("internal")]


class DropFileOut(BaseModel):
    """One dropped file's outcome. `rule_linked` names the request it landed on, pending a
    person's accept; `waiting` is "Brightwater Hale will sort this"."""

    model_config = ConfigDict(frozen=True)

    file_id: Annotated[UUID, classified("internal")]
    file_name: Annotated[str, classified("confidential")]
    outcome: Annotated[DropOutcome | None, classified("internal")] = None
    request_item_id: Annotated[UUID | None, classified("internal")] = None
    refusal: Annotated[DropRefusal | None, classified("internal")] = None


class DropBatchOut(BaseModel):
    """`GET /v1/portal/drops/{batch_id}`: polled until `settled` (every file has an outcome)."""

    model_config = ConfigDict(frozen=True)

    batch_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID, classified("internal")]
    files: Annotated[list[DropFileOut], classified("internal")]
    settled: Annotated[bool, classified("internal")]


async def _stub(ctx: AuthContext, flag: Flag) -> NoReturn:
    if not await flag_enabled(ctx.tenant, flag):
        raise NotFound(flag.name)
    raise NotImplementedYet


pbc_router = AbacusRouter(prefix="/v1/portal", tags=["portal"])


@pbc_router.get(
    "/binders",
    action="portal_documents.read",
    response_model=PortalBinderListOut,
    errors=(501,),
)
async def list_portal_binders_route(
    ctx: Member, scope_id: Annotated[UUID | None, Query()] = None
) -> PortalBinderListOut:
    """The binder picker: every binder the caller can see; closed ones read-only."""
    await _stub(ctx, PORTAL_DOCUMENTS_V2)


@pbc_router.get(
    "/binders/{binder_id}",
    action="portal_documents.read",
    response_model=PortalBinderOut,
    errors=(501,),
)
async def get_portal_binder_route(
    binder_id: UUID,
    ctx: Member,
    filter: Annotated[BinderFilter, Query()] = "requested",
    category: Annotated[str | None, Query(max_length=64)] = None,
) -> PortalBinderOut:
    """POR-03. A binder outside the caller's grant, a draft or a forged id answers 404."""
    await _stub(ctx, PORTAL_DOCUMENTS_V2)


@pbc_router.get(
    "/request-items/{item_id}",
    action="portal_documents.read",
    response_model=PortalRequestOut,
    errors=(501,),
)
async def get_portal_request_route(item_id: UUID, ctx: Member) -> PortalRequestOut:
    """POR-04. Out of scope, internal-only, delegated to a third party or forged: 404."""
    await _stub(ctx, PORTAL_DOCUMENTS_V2)


@pbc_router.get(
    "/room",
    action="portal_documents.read",
    response_model=PortalRoomOut,
    errors=(501,),
)
async def get_portal_room_route(ctx: Member) -> PortalRoomOut:
    """POR-14: the caller's delegated request items, by band."""
    await _stub(ctx, PORTAL_THIRD_PARTY_ROOM)


@pbc_router.post(
    "/room/suggest",
    action="portal_documents.read",
    response_model=RoomSuggestOut,
    errors=(501,),
)
async def suggest_room_request_route(body: RoomSuggestIn, ctx: Member) -> RoomSuggestOut:
    """ "Which request is this for?": code-only file-name scoring among the caller's delegated
    items. Writes nothing."""
    await _stub(ctx, PORTAL_THIRD_PARTY_ROOM)


@pbc_router.get(
    "/drops/{batch_id}",
    action="portal_documents.read",
    response_model=DropBatchOut,
    errors=(501,),
)
async def get_drop_batch_route(batch_id: UUID, ctx: Member) -> DropBatchOut:
    """The dropper's poll of one drop batch; anyone else's batch answers 404 (R-01-T09)."""
    if not await flag_enabled(ctx.tenant, PORTAL_DROP_SORT):
        raise NotFound(PORTAL_DROP_SORT.name)
    found = await drop_batch(ctx, batch_id)
    return DropBatchOut(
        batch_id=found.batch_id,
        binder_id=found.binder_id,
        files=[
            DropFileOut(
                file_id=f.file_id,
                file_name=f.file_name,
                outcome=cast(DropOutcome | None, f.outcome),
                request_item_id=f.request_item_id,
            )
            for f in found.files
        ],
        settled=found.settled,
    )
