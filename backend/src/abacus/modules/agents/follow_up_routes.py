"""Follow-ups v2 routes, the C5 SHL-20 family's follow-up half (P-06-T14; P-06 §4.3; C5 v1.2).

Behind `binders.engine` (off: 404), like the BND-01 and BND-02 screens that use them. Drafting is
`follow_up.draft`; sending, its Undo and dismissing are `follow_up.send`, which denies the agent
(DEC-74). Contract: `docs/contracts/c5-requests-binders.md` §12.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Depends, Header
from pydantic import BaseModel, ConfigDict, Field, model_validator

from abacus.kernel._flags import BINDERS_ENGINE
from abacus.kernel.classification import classified
from abacus.kernel.errors import NotFound
from abacus.kernel.flags import flag_enabled
from abacus.kernel.text import MultiLineText
from abacus.kernel.uow.idempotency import idempotent
from abacus.modules.agents import follow_up_drafts as service
from abacus.modules.identity.api import AbacusRouter, AuthContext, current_context

Ctx = Annotated[AuthContext, Depends(current_context)]
IdempotencyKey = Annotated[str, Header(alias="Idempotency-Key", min_length=1, max_length=255)]
FollowUpKind = Literal["overdue", "chase", "screening_return"]
FollowUpStatus = Literal["drafted", "sent", "dismissed"]
DraftedByKind = Literal["person", "agent"]

follow_ups_router = AbacusRouter(prefix="/v1/follow-ups", tags=["follow-ups"])


async def _engine_on(ctx: AuthContext) -> None:
    if not await flag_enabled(ctx.tenant, BINDERS_ENGINE):
        raise NotFound("binders.engine")


class FollowUpItemOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    request_item_id: Annotated[UUID, classified("internal")]
    title: Annotated[str, classified("confidential")]
    due_on: Annotated[date | None, classified("internal")]
    overdue: Annotated[bool, classified("internal")]


class FollowUpOut(BaseModel):
    """One follow-up: who it goes to, the open requests it lists (each once), and the email
    exactly as it will be sent. `body` is template-composed (DEC-79: never model text) or the
    person's edit."""

    model_config = ConfigDict(frozen=True)

    id: Annotated[UUID, classified("internal")]
    engagement_id: Annotated[UUID, classified("internal")]
    binder_id: Annotated[UUID | None, classified("internal")]
    kind: Annotated[FollowUpKind, classified("internal")]
    status: Annotated[FollowUpStatus, classified("internal")]
    recipient_user_id: Annotated[UUID, classified("internal")]
    recipient_contact_id: Annotated[UUID | None, classified("internal")]
    recipient_name: Annotated[str, classified("confidential")]
    items: Annotated[list[FollowUpItemOut], classified("confidential")]
    subject: Annotated[str, classified("confidential")]
    body: Annotated[str, classified("confidential")]
    edited: Annotated[bool, classified("internal")]
    drafted_by_kind: Annotated[DraftedByKind, classified("internal")]
    template_key: Annotated[str, classified("internal")]
    created_at: Annotated[datetime, classified("internal")]
    sent_by: Annotated[UUID | None, classified("internal")]
    sent_at: Annotated[datetime | None, classified("internal")]
    undo_until: Annotated[datetime | None, classified("internal")]
    allowed_actions: Annotated[list[str], classified("internal")]


class FollowUpDraftsIn(BaseModel):
    """BND-01 b (binders) or BND-02 d (requests of one binder): one of the two lists."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    binder_ids: Annotated[list[UUID], Field(max_length=200), classified("internal")] = []
    request_item_ids: Annotated[list[UUID], Field(max_length=500), classified("internal")] = []

    @model_validator(mode="after")
    def _one_list(self) -> FollowUpDraftsIn:
        if bool(self.binder_ids) == bool(self.request_item_ids):
            raise ValueError("give binder_ids or request_item_ids")
        return self


class FollowUpDraftsOut(BaseModel):
    model_config = ConfigDict(frozen=True)

    items: Annotated[list[FollowUpOut], classified("confidential")]


class FollowUpEditIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    body: Annotated[
        MultiLineText, Field(min_length=1, max_length=10_000), classified("confidential")
    ]


class FollowUpSendManyIn(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ids: Annotated[list[UUID], Field(min_length=1, max_length=200), classified("internal")]


def _out(view: service.FollowUpView) -> FollowUpOut:
    return FollowUpOut(
        id=view.id,
        engagement_id=view.engagement_id,
        binder_id=view.binder_id,
        kind=view.kind,  # pyright: ignore[reportArgumentType] -- the database CHECK's codes
        status=view.status,  # pyright: ignore[reportArgumentType] -- the database CHECK's codes
        recipient_user_id=view.recipient_user_id,
        recipient_contact_id=view.recipient_contact_id,
        recipient_name=view.recipient_name,
        items=[
            FollowUpItemOut(
                request_item_id=i.request_item_id,
                title=i.title,
                due_on=i.due_on,
                overdue=i.overdue,
            )
            for i in view.items
        ],
        subject=view.subject,
        body=view.body,
        edited=view.edited,
        drafted_by_kind=view.drafted_by_kind,  # pyright: ignore[reportArgumentType] -- CHECK codes
        template_key=view.template_key,
        created_at=view.created_at,
        sent_by=view.sent_by,
        sent_at=view.sent_at,
        undo_until=view.undo_until,
        allowed_actions=view.allowed_actions,
    )


@follow_ups_router.post(
    "/drafts",
    action="follow_up.draft",
    response_model=FollowUpDraftsOut,
    status_code=201,
    errors=(409,),
)
async def draft_selection_follow_ups_route(body: FollowUpDraftsIn, ctx: Ctx) -> FollowUpDraftsOut:
    """One draft per client contact over the selection, each open client-visible request listed
    once, never one already waiting to that contact. Nothing is sent. 409
    `follow_up_template_missing` when no Reminder template is published."""
    await _engine_on(ctx)
    views = await service.draft_for(ctx, body.binder_ids, body.request_item_ids)
    return FollowUpDraftsOut(items=[_out(v) for v in views])


@follow_ups_router.get("/{follow_up_id}", action="follow_up.draft", response_model=FollowUpOut)
async def get_follow_up_route(follow_up_id: UUID, ctx: Ctx) -> FollowUpOut:
    await _engine_on(ctx)
    return _out(await service.read(ctx, follow_up_id))


@follow_ups_router.patch(
    "/{follow_up_id}", action="follow_up.draft", response_model=FollowUpOut, errors=(409,)
)
async def edit_follow_up_route(follow_up_id: UUID, body: FollowUpEditIn, ctx: Ctx) -> FollowUpOut:
    """Edit before sending: the person's wording replaces the composed body (sealed). 409
    `follow_up_already_sent` / `follow_up_not_waiting`."""
    await _engine_on(ctx)
    return _out(await service.edit(ctx, follow_up_id, body.body))


@follow_ups_router.post(
    "/{follow_up_id}/send", action="follow_up.send", response_model=FollowUpOut, errors=(409,)
)
async def send_follow_up_route(
    follow_up_id: UUID, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FollowUpOut:
    """Human only. 409 `out_of_scope` (nothing sent), `follow_up_already_sent`; the email leaves
    after the 10-s Undo window. A retry with the same key answers what the first answered."""
    await _engine_on(ctx)

    async def run() -> tuple[int, dict[str, object]]:
        return 200, _out(await service.send(ctx, follow_up_id)).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="follow_up.send",
        key=idempotency_key,
        body={"follow_up_id": str(follow_up_id)},
        run=run,
    )
    return FollowUpOut.model_validate(stored.body)


@follow_ups_router.post(
    "/send", action="follow_up.send", response_model=FollowUpDraftsOut, errors=(409,)
)
async def send_follow_ups_route(
    body: FollowUpSendManyIn, ctx: Ctx, idempotency_key: IdempotencyKey
) -> FollowUpDraftsOut:
    """BND-01 b "Send n follow-ups": all or none, in one unit of work."""
    await _engine_on(ctx)

    async def run() -> tuple[int, dict[str, object]]:
        views = await service.send_many(ctx, body.ids)
        return 200, FollowUpDraftsOut(items=[_out(v) for v in views]).model_dump(mode="json")

    stored = await idempotent(
        ctx.tenant,
        route="follow_up.send_many",
        key=idempotency_key,
        body={"ids": [str(i) for i in body.ids]},
        run=run,
    )
    return FollowUpDraftsOut.model_validate(stored.body)


@follow_ups_router.post(
    "/{follow_up_id}/undo", action="follow_up.send", response_model=FollowUpOut, errors=(409,)
)
async def undo_follow_up_route(follow_up_id: UUID, ctx: Ctx) -> FollowUpOut:
    """Within 10 s, by its sender: 409 `undo_window_closed`, `effect_started`."""
    await _engine_on(ctx)
    return _out(await service.undo(ctx, follow_up_id))


@follow_ups_router.post(
    "/{follow_up_id}/dismiss", action="follow_up.send", response_model=FollowUpOut, errors=(409,)
)
async def dismiss_follow_up_route(follow_up_id: UUID, ctx: Ctx) -> FollowUpOut:
    await _engine_on(ctx)
    return _out(await service.dismiss(ctx, follow_up_id))
