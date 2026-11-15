"""The component auditor room stub (A-09-T03; POR-23; SPEC-658 F7; DEC-5039). Contract:
`docs/contracts/group-audit.md` §room.

A `component_auditor` grant holds `client_contributor` on one `component` scope (DEC-67): the room
shows that component only, in client words (Due · ✓ You uploaded · Overdue · Returned), with no
agent named and "Accrued" nowhere. Any other component, the consolidation, eliminations, scoping
or group materiality is 404 (INV-4). Each route: a firm principal 404; the firm's `group_audit`
entitlement (404 off); then 501 until A-09-T33 (the room read model) and T27/T28.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header, Response
from pydantic import BaseModel, ConfigDict, Field

from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound, NotImplementedYet
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_member
from abacus.modules.platform.api import entitlement

Member = Annotated[AuthContext, Depends(current_member)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
Internal = classified("internal")
Confidential = classified("confidential")
ClientWord = Literal["due", "you_uploaded", "overdue", "returned"]


class RoomDeliverableOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    title: Annotated[str, Confidential]
    due_on: Annotated[date, Internal]
    word: Annotated[ClientWord, Internal]  # never Expected, Reviewed or Late (firm words)
    uploaded_on: Annotated[date | None, Internal]
    return_note: Annotated[str | None, Confidential]


class ComponentRoomOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    group_name: Annotated[str, Confidential]  # "Harlow & Pike Holdings, Inc. · FY2026 group audit"
    component_name: Annotated[str, Confidential]  # "Harlow & Pike Distribution, Inc."
    firm_name: Annotated[str, classified("public")]
    acknowledged_on: Annotated[date | None, Internal]
    uploaded: Annotated[int, Field(ge=0), Internal]
    expected: Annotated[int, Field(ge=0), Internal]  # "0 of 4"
    deliverables: Annotated[list[RoomDeliverableOut], Internal]


class RoomInstructionsOut(BaseModel):
    """The letter as HTML text sections (a PDF download beside it); only this component's PM and
    the clearly-trivial threshold, never group materiality (OQ-6)."""

    model_config = ConfigDict(frozen=True)

    sections: Annotated[list[RoomSectionOut], Internal]
    sent_on: Annotated[date, Internal]


class RoomSectionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    number: Annotated[int, Internal]
    title: Annotated[str, Confidential]
    body: Annotated[str, Confidential]


class RoomAcknowledgedOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    acknowledged_on: Annotated[date, Internal]


class RoomUploadOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    deliverable_id: Annotated[
        UUID | None, Internal
    ]  # None: the "Which deliverable is this for?" picker
    evidence_version_id: Annotated[UUID, Internal]


class RoomQuestionOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, Internal]
    author_name: Annotated[str, Confidential]
    body: Annotated[str, Confidential]
    at: Annotated[datetime, Internal]


class RoomQuestionsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[RoomQuestionOut], Internal]


class RoomQuestionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: Annotated[str, Field(min_length=1, max_length=4000)]


RoomInstructionsOut.model_rebuild()

router = AbacusRouter(prefix="/v1/portal/component-rooms", tags=["portal component room"])


async def _gate(ctx: AuthContext) -> None:
    """A firm principal never reads a room (404); the firm's entitlement; the room service checks
    the grant's `component` scope (A-09-T33)."""
    if not ctx.client:
        raise NotFound("component_room")
    if await entitlement(ctx.tenant, "group_audit") is None:
        raise NotFound("group_audit")


@router.get(
    "/{room_id}", action="component_room.read", response_model=ComponentRoomOut, errors=(501,)
)
async def component_room_get_room(room_id: UUID, ctx: Member) -> ComponentRoomOut:
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")


@router.get(
    "/{room_id}/instructions",
    action="component_room.read",
    response_model=RoomInstructionsOut,
    errors=(501,),
)
async def component_room_get_instructions(room_id: UUID, ctx: Member) -> RoomInstructionsOut:
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")


@router.get(
    "/{room_id}/instructions/pdf",
    action="component_room.read",
    response_model=bytes,
    errors=(501,),
)
async def component_room_get_instructions_pdf(room_id: UUID, ctx: Member) -> Response:
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")


@router.post(
    "/{room_id}/instructions/acknowledge",
    action="component_instructions.acknowledge",
    response_model=RoomAcknowledgedOut,
    errors=(409, 501),
)
async def component_room_acknowledge(
    room_id: UUID, ctx: Member, _key: IdempotencyKey
) -> RoomAcknowledgedOut:
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")


@router.post(
    "/{room_id}/deliverables/{deliverable_id}/uploads",
    action="component_deliverable.upload",
    response_model=RoomUploadOut,
    status_code=201,
    errors=(409, 413, 415, 501),
)
async def component_room_upload(
    room_id: UUID, deliverable_id: UUID, ctx: Member, _key: IdempotencyKey
) -> RoomUploadOut:
    """A new evidence version with provenance `component_auditor_upload`."""
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")


@router.post(
    "/{room_id}/drops",
    action="component_deliverable.upload",
    response_model=RoomUploadOut,
    status_code=201,
    errors=(409, 413, 415, 501),
)
async def component_room_drop(room_id: UUID, ctx: Member, _key: IdempotencyKey) -> RoomUploadOut:
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")


@router.get(
    "/{room_id}/questions",
    action="component_room.read",
    response_model=RoomQuestionsOut,
    errors=(501,),
)
async def component_room_list_questions(room_id: UUID, ctx: Member) -> RoomQuestionsOut:
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")


@router.post(
    "/{room_id}/questions",
    action="component_room.ask",
    response_model=RoomQuestionOut,
    status_code=201,
    errors=(409, 501),
)
async def component_room_ask(
    room_id: UUID, body: RoomQuestionIn, ctx: Member, _key: IdempotencyKey
) -> RoomQuestionOut:
    await _gate(ctx)
    raise NotImplementedYet("A-09-T33")
