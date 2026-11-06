"""C10 Deliverables, the portal half (R-02-T02 stub; R-02 §4.3; SPEC-646). Contract:
`docs/contracts/deliverables.md`; screens POR-09 and POR-15.

What the firm delivered to a client, the page images and downloads of it, management's approval of
the latest draft, page comments, and the governance room's letters, reports and inquiries. Every
route answers, in order: the matrix action (client people only, `scope_only`; firm roles, agents,
system and support are denied); 501 until R-02-T09, T12 and T15. Flags arrive with R-02-T14
(`portal.deliverables`, `portal.governance_room`), and only then does an off flag answer 404.

Pack rule (SPEC-646 AC-7): no field here is named or holds materiality, a threshold, a policy
name, a review note, a sign-off, the agent, a confidence or an internal status. Client strings are
hostile (ADR-052): restricted, never rendered as HTML, never stored in an audit row.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal, NoReturn
from uuid import UUID

from fastapi import Depends, Header, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member

# A portal person themself, never a break-glass support context.
Member = Annotated[AuthContext, Depends(current_member)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
Restricted = classified("restricted")
PageNumber = Annotated[int, Query(ge=1, le=5000)]

# The kinds C10 knows (R-02 §4.2); a provider publishes one per source version.
DeliverableKind = Literal[
    "fs_draft",
    "fs_final",
    "auditor_report",
    "review_report",
    "compilation_report",
    "preparation_statements",
    "close_package",
    "governance_letter",
    "signed_copy",
    "return_copy",
    "filing_letter",
    "memo",
    "soc_report",
    "assertion",
    "other",
]
# The client's words, from the status registry (DF-31, R-02-T04).
DeliverableStatus = Literal[
    "for_your_review",
    "approved_by_you",
    "waiting_for_approval",
    "in_sign",
    "signed",
    "final",
    "released",
    "not_ready_yet",
    "replaced",
]
LegendKind = Literal["ar_c_70"]
DeliverableAction = Literal["download", "approve", "comment"]
DeliverableSection = Literal["k1s"]
GovernanceStatus = Literal["new", "not_yet", "sent_acknowledged", "acknowledged"]
GovernanceAction = Literal["acknowledge", "ask", "download"]
MemberRole = Literal["chair", "member"]


def _frozen() -> ConfigDict:
    return ConfigDict(frozen=True)


def _strict() -> ConfigDict:
    return ConfigDict(frozen=True, extra="forbid")


class DeliverableRowOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    kind: Annotated[DeliverableKind, Internal]
    title: Annotated[str, Confidential]
    status: Annotated[DeliverableStatus, Internal]
    latest_version: Annotated[int | None, Internal] = None
    page_count: Annotated[int | None, Internal] = None
    released_on: Annotated[date | None, Internal] = None
    restricted_use: Annotated[bool, Internal] = False


class DeliverableBandOut(BaseModel):
    """One band of the rail: a work item, or the role union's own band."""

    model_config = _frozen()

    key: Annotated[str, Internal]
    label: Annotated[str, Confidential]
    work_item_id: Annotated[UUID | None, Internal] = None
    rows: Annotated[list[DeliverableRowOut], Confidential]


class ComingNextOut(BaseModel):
    """A C1 milestone the client may see (R-02 AC-21); nothing about how far along it is."""

    model_config = _frozen()

    label: Annotated[str, Confidential]
    expected: Annotated[str | None, Confidential] = None


class K1RowOut(BaseModel):
    """A K-1 released to this person (POR-09 d); attachments use T-02's routes (DV-09)."""

    model_config = _frozen()

    package_id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    released_on: Annotated[date, Internal]


class DeliverablesOut(BaseModel):
    model_config = _frozen()

    bands: Annotated[list[DeliverableBandOut], Confidential]
    coming_next: Annotated[list[ComingNextOut], Confidential]
    k1s: Annotated[list[K1RowOut], Confidential]


class DeliverableVersionOut(BaseModel):
    model_config = _frozen()

    version_no: Annotated[int, Internal]
    is_draft: Annotated[bool, Internal]
    page_count: Annotated[int, Internal]
    page_comments: Annotated[bool, Internal]
    published_at: Annotated[datetime, Internal]
    seen_hash: Annotated[str, Internal]
    withdrawn_on: Annotated[date | None, Internal] = None
    allowed_actions: Annotated[list[DeliverableAction], Internal]


class DeliverableOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    kind: Annotated[DeliverableKind, Internal]
    title: Annotated[str, Confidential]
    status: Annotated[DeliverableStatus, Internal]
    restricted_use: Annotated[bool, Internal]
    legend_kind: Annotated[LegendKind | None, Internal] = None
    versions: Annotated[list[DeliverableVersionOut], Internal]


class DeliverableApproveIn(BaseModel):
    """What you saw is what you approved (AC-4): a stale `seen_hash` answers 409 `item_changed`."""

    model_config = _strict()

    seen_hash: Annotated[str, Field(min_length=1, max_length=128), Internal]


class DeliverableApprovedOut(BaseModel):
    model_config = _frozen()

    deliverable_id: Annotated[UUID, Internal]
    version_no: Annotated[int, Internal]
    status: Annotated[DeliverableStatus, Internal]
    approved_at: Annotated[datetime, Internal]


class PageCommentIn(BaseModel):
    """A pin on a line or a point of a page. The body is hostile client text (AC-34)."""

    model_config = _strict()

    page: Annotated[int, Field(ge=1, le=5000), Internal]
    line_ref: Annotated[str | None, Field(max_length=120), Internal] = None
    x: Annotated[float | None, Field(ge=0, le=1), Internal] = None
    y: Annotated[float | None, Field(ge=0, le=1), Internal] = None
    body: Annotated[str, Field(min_length=1, max_length=1000), Restricted]


class PageCommentOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    page: Annotated[int, Internal]
    line_ref: Annotated[str | None, Internal] = None
    x: Annotated[float | None, Internal] = None
    y: Annotated[float | None, Internal] = None
    author: Annotated[str, Confidential]
    body: Annotated[str, Restricted]
    created_at: Annotated[datetime, Internal]


class PageCommentsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[PageCommentOut], Restricted]


class GovernanceRoomOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    body_name: Annotated[str, Confidential]
    subject: Annotated[str, Confidential]
    member_role: Annotated[MemberRole, Internal]
    questions_for_you: Annotated[int, Internal]


class GovernanceRoomsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[GovernanceRoomOut], Confidential]


class CommitteeMemberOut(BaseModel):
    model_config = _frozen()

    name: Annotated[str, Confidential]
    member_role: Annotated[MemberRole, Internal]
    acknowledged_on: Annotated[date | None, Internal] = None


class RoomLetterRowOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID | None, Internal] = None
    title: Annotated[str, Confidential]
    status: Annotated[GovernanceStatus, Internal]
    sent_on: Annotated[date | None, Internal] = None
    due_on: Annotated[date | None, Internal] = None
    acknowledged_on: Annotated[date | None, Internal] = None


class GovernanceCommunicationsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[RoomLetterRowOut], Confidential]
    committee: Annotated[list[CommitteeMemberOut], Confidential]


class LetterSectionOut(BaseModel):
    """An approved letter's section as text: no citation marker reaches the room (AC-28)."""

    model_config = _frozen()

    heading: Annotated[str | None, Confidential] = None
    body: Annotated[str, Confidential]


class GovernanceLetterOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    dated_on: Annotated[date, Internal]
    signed_by: Annotated[str, Confidential]
    sections: Annotated[list[LetterSectionOut], Confidential]
    status: Annotated[GovernanceStatus, Internal]
    seen_hash: Annotated[str, Internal]
    committee: Annotated[list[CommitteeMemberOut], Confidential]
    allowed_actions: Annotated[list[GovernanceAction], Internal]


class GovernanceAcknowledgeIn(BaseModel):
    model_config = _strict()

    seen_hash: Annotated[str, Field(min_length=1, max_length=128), Internal]


class GovernanceAcknowledgedOut(BaseModel):
    model_config = _frozen()

    communication_id: Annotated[UUID, Internal]
    acknowledged_on: Annotated[date, Internal]
    status: Annotated[GovernanceStatus, Internal]


class PrivateQuestionIn(BaseModel):
    """ "Ask the auditor…": readable by the author and the engagement's EP and manager (AC-33)."""

    model_config = _strict()

    body: Annotated[str, Field(min_length=1, max_length=4000), Restricted]


class PrivateQuestionOut(BaseModel):
    model_config = _frozen()

    id: Annotated[UUID, Internal]
    author: Annotated[str, Confidential]
    body: Annotated[str, Restricted]
    created_at: Annotated[datetime, Internal]


class PrivateQuestionsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[PrivateQuestionOut], Restricted]


class RoomInquiryOut(BaseModel):
    """A questionnaire addressed to the caller; answers go through T-02's addressee-only routes."""

    model_config = _frozen()

    questionnaire_id: Annotated[UUID, Internal]
    question_id: Annotated[UUID, Internal]
    prompt: Annotated[str, Confidential]


class RoomInquiriesOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[RoomInquiryOut], Confidential]


class RoomReportsOut(BaseModel):
    model_config = _frozen()

    items: Annotated[list[DeliverableRowOut], Confidential]


def _not_yet() -> NoReturn:
    raise NotImplementedYet


deliverables_router = AbacusRouter(prefix="/v1/portal/deliverables", tags=["portal deliverables"])
governance_router = AbacusRouter(prefix="/v1/portal/governance", tags=["portal governance"])

_V = "/{deliverable_id}/versions/{version_no}"


@deliverables_router.get(
    "", action="deliverable.read", response_model=DeliverablesOut, errors=(501,)
)
async def list_deliverables_route(
    ctx: Member,
    scope_id: Annotated[UUID | None, Query()] = None,
    section: Annotated[DeliverableSection | None, Query()] = None,
) -> DeliverablesOut:
    """POR-09's rail: bands by work item, Coming next, My K-1s. Only what a grant covers."""
    _not_yet()


@deliverables_router.get(
    "/{deliverable_id}", action="deliverable.read", response_model=DeliverableOut, errors=(501,)
)
async def get_deliverable_route(deliverable_id: UUID, ctx: Member) -> DeliverableOut:
    """Meta, page count and versions. Outside every audience: 404."""
    _not_yet()


@deliverables_router.get(
    _V, action="deliverable.read", response_model=DeliverableVersionOut, errors=(501,)
)
async def get_deliverable_version_route(
    deliverable_id: UUID, version_no: int, ctx: Member
) -> DeliverableVersionOut:
    """One version; a superseded one reads under Earlier versions for audience members."""
    _not_yet()


@deliverables_router.get(
    f"{_V}/pages/{{page}}", action="deliverable.read", response_model=bytes, errors=(501,)
)
async def get_deliverable_page_route(
    deliverable_id: UUID, version_no: int, page: int, ctx: Member
) -> Response:
    """A PNG served by the server, the watermark burned in on a draft (AC-22, AC-38)."""
    _not_yet()


@deliverables_router.get(
    f"{_V}/download", action="deliverable.download", response_model=bytes, errors=(501,)
)
async def download_deliverable_route(
    deliverable_id: UUID, version_no: int, request: Request, ctx: Member
) -> Response:
    """302 to a 60-second signed URL; the access event and receipt land in one unit of work."""
    _not_yet()


@deliverables_router.post(
    f"{_V}/approve",
    action="statement.client_approve",
    response_model=DeliverableApprovedOut,
    errors=(409, 501),
)
async def approve_deliverable_route(
    deliverable_id: UUID,
    version_no: int,
    body: DeliverableApproveIn,
    ctx: Member,
    idempotency_key: IdempotencyKey,
) -> DeliverableApprovedOut:
    """Management approves the latest draft: `reporting.api.apply_management_decision`.
    Not the decider: 403 `not_decider`. No fresh second factor: 401 `mfa_recent_required`."""
    _not_yet()


@deliverables_router.get(
    f"{_V}/comments", action="deliverable.comment", response_model=PageCommentsOut, errors=(501,)
)
async def list_page_comments_route(
    deliverable_id: UUID, version_no: int, ctx: Member
) -> PageCommentsOut:
    _not_yet()


@deliverables_router.post(
    f"{_V}/comments",
    action="deliverable.comment",
    response_model=PageCommentOut,
    status_code=201,
    errors=(409, 501),
)
async def add_page_comment_route(
    deliverable_id: UUID,
    version_no: int,
    body: PageCommentIn,
    ctx: Member,
    idempotency_key: IdempotencyKey,
) -> PageCommentOut:
    """A version with `page_comments = false` refuses a pin: 409."""
    _not_yet()


@governance_router.get(
    "/rooms", action="tcwg.read", response_model=GovernanceRoomsOut, errors=(501,)
)
async def list_rooms_route(ctx: Member) -> GovernanceRoomsOut:
    """The rooms the caller's `tcwg` grants open; a management grant reaches none (DEC-93)."""
    _not_yet()


@governance_router.get(
    "/rooms/{room_id}/communications",
    action="tcwg.read",
    response_model=GovernanceCommunicationsOut,
    errors=(501,),
)
async def list_room_communications_route(
    room_id: UUID, ctx: Member
) -> GovernanceCommunicationsOut:
    _not_yet()


@governance_router.get(
    "/rooms/{room_id}/inquiries",
    action="tcwg.read",
    response_model=RoomInquiriesOut,
    errors=(501,),
)
async def list_room_inquiries_route(room_id: UUID, ctx: Member) -> RoomInquiriesOut:
    """Questionnaires addressed to the caller only (AC-29)."""
    _not_yet()


@governance_router.get(
    "/rooms/{room_id}/reports", action="tcwg.read", response_model=RoomReportsOut, errors=(501,)
)
async def list_room_reports_route(room_id: UUID, ctx: Member) -> RoomReportsOut:
    """Deliverables whose audiences include this room; nothing from management's list (AC-30)."""
    _not_yet()


@governance_router.get(
    "/communications/{communication_id}",
    action="tcwg.read",
    response_model=GovernanceLetterOut,
    errors=(501,),
)
async def get_communication_route(communication_id: UUID, ctx: Member) -> GovernanceLetterOut:
    """The paper model. A version without an EP send row is refused (AC-28)."""
    _not_yet()


@governance_router.get(
    "/communications/{communication_id}/pdf",
    action="tcwg.read",
    response_model=bytes,
    errors=(501,),
)
async def get_communication_pdf_route(communication_id: UUID, ctx: Member) -> Response:
    """302 to the C10 download."""
    _not_yet()


@governance_router.post(
    "/communications/{communication_id}/acknowledge",
    action="tcwg.acknowledge",
    response_model=GovernanceAcknowledgedOut,
    errors=(409, 501),
)
async def acknowledge_communication_route(
    communication_id: UUID,
    body: GovernanceAcknowledgeIn,
    ctx: Member,
    idempotency_key: IdempotencyKey,
) -> GovernanceAcknowledgedOut:
    """`assurance.api.record_acknowledgement`: one row per member and version."""
    _not_yet()


@governance_router.get(
    "/communications/{communication_id}/questions",
    action="tcwg.ask",
    response_model=PrivateQuestionsOut,
    errors=(501,),
)
async def list_private_questions_route(communication_id: UUID, ctx: Member) -> PrivateQuestionsOut:
    """The author's own thread; other members and management get 404 (AC-33)."""
    _not_yet()


@governance_router.post(
    "/communications/{communication_id}/questions",
    action="tcwg.ask",
    response_model=PrivateQuestionOut,
    status_code=201,
    errors=(501,),
)
async def ask_auditor_route(
    communication_id: UUID,
    body: PrivateQuestionIn,
    ctx: Member,
    idempotency_key: IdempotencyKey,
) -> PrivateQuestionOut:
    _not_yet()
