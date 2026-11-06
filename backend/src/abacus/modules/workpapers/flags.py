"""A-04-T19: converting a PBC GAP attention flag (A-04 §3.2 AC2.3; DEC-2055).

A person turns an open flag into a request item **draft** (nothing is sent: SHL-14 opens it
prefilled, and the request goes to the client only when a person sends it through C5) or into an
open review note on the workpaper (C3). The flag reads Converted with what it became, and its
insert-only history records the act (`attention_flag_events`, actor kind from the session).

Remind (DEC-2388) drafts a follow-up to the client contacts over the engagement's open requests
through C5's own follow-up drafts: nothing is sent (`follow_up.send` is a person's). A reminder
doesn't close the gap, so the flag stays open and its history records `reminded`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal
from uuid import UUID

from sqlalchemy import select

from abacus.kernel.db import tenant_session
from abacus.kernel.errors import DomainConflict, NotFound
from abacus.kernel.uow import Ref, Scope, Target, uow
from abacus.modules.agents.api import draft_follow_ups
from abacus.modules.identity.api import AuthContext, Forbidden
from abacus.modules.requests.api import NewRequestItem, add_request_item, request_items_for
from abacus.modules.review.api import raise_review_note
from abacus.modules.workpapers.models import AttentionFlag, AttentionFlagEvent
from abacus.modules.workpapers.service import TARGET as PAPER_TARGET

TARGET = "attention_flag"
ConvertTo = Literal["request_draft", "review_note"]
_CHASED: Final = frozenset({"requested", "returned"})  # what C5's follow-up drafts chase


class FlagNotOpen(DomainConflict):
    """The flag was converted or resolved already."""

    code = "flag_not_open"


class NothingToRemind(DomainConflict):
    """No open client request is left to chase, or a follow-up already waits for each one."""

    code = "nothing_to_remind"


@dataclass(frozen=True)
class Converted:
    flag: AttentionFlag
    draft_id: UUID


async def _open_flag(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID, flag_id: UUID
) -> AttentionFlag:
    async with tenant_session(ctx.tenant) as session:
        flag = (
            await session.execute(
                select(AttentionFlag).where(
                    AttentionFlag.id == flag_id,
                    AttentionFlag.workpaper_id == workpaper_id,
                    AttentionFlag.engagement_id == engagement_id,
                )
            )
        ).scalar_one_or_none()
    if flag is None:
        raise NotFound(TARGET)
    if flag.state != "open":
        raise FlagNotOpen(facts={"state": flag.state})
    return flag


async def convert(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID, flag_id: UUID, to: ConvertTo
) -> Converted:
    """`POST …/flags/{flag_id}/convert` (the route authorised `attention_flag.convert`)."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("attention_flag.convert", "role")
    flag = await _open_flag(ctx, engagement_id, workpaper_id, flag_id)
    kind: Literal["request_item", "review_note"]
    if to == "request_draft":
        item = await add_request_item(
            ctx, engagement_id, NewRequestItem(description=flag.text, audit_area=flag.section_key)
        )
        kind, draft_id = "request_item", item.id
    else:
        note = await raise_review_note(
            ctx,
            "workpaper",
            workpaper_id,
            anchor_kind=None,
            anchor_ref=None,
            body=flag.text,
            assignee=None,
        )
        kind, draft_id = "review_note", note.note.id
    async with uow(ctx.tenant) as tx:
        locked = (
            await tx.session.execute(
                select(AttentionFlag).where(AttentionFlag.id == flag_id).with_for_update()
            )
        ).scalar_one()
        if locked.state != "open":
            raise FlagNotOpen(facts={"state": locked.state})
        locked.state = "converted"
        locked.converted_to_kind = kind
        locked.converted_to_id = draft_id
        tx.session.add(
            AttentionFlagEvent(
                tenant_id=ctx.tenant_id,
                workpaper_id=workpaper_id,
                flag_id=flag_id,
                event="converted",
                actor_user_id=ctx.user_id,
                agent_run_id=None,
                ref={"to": kind, "id": str(draft_id)},
            )
        )
        tx.record(
            "attention_flag.converted",
            target=Target(PAPER_TARGET, workpaper_id),
            after=Ref(flag=flag_id),
            scope=Scope(engagement_id=engagement_id, work_item_id=locked.work_item_id),
        )
    async with tenant_session(ctx.tenant) as session:
        fresh = await session.get(AttentionFlag, flag_id)
    if fresh is None:
        raise NotFound(TARGET)
    return Converted(fresh, draft_id)


async def remind(
    ctx: AuthContext, engagement_id: UUID, workpaper_id: UUID, flag_id: UUID
) -> Converted:
    """`POST …/flags/{flag_id}/remind` (the route authorised `follow_up.draft`): a follow-up draft
    per client contact over the engagement's open requests. A flag names no request, so the draft
    lists them all and a person reads it before sending. `draft_id` is the first draft; the history
    keeps every one. 409 `nothing_to_remind` leaves the flag as it was (Escalate… drafts one)."""
    if ctx.tenant.actor_kind != "human" or ctx.client:
        raise Forbidden("follow_up.draft", "role")
    flag = await _open_flag(ctx, engagement_id, workpaper_id, flag_id)
    items = await request_items_for(ctx, engagement_id)
    drafts = await draft_follow_ups(ctx, [], [i.id for i in items if i.status in _CHASED])
    if not drafts:
        raise NothingToRemind
    async with uow(ctx.tenant) as tx:
        tx.session.add(
            AttentionFlagEvent(
                tenant_id=ctx.tenant_id,
                workpaper_id=workpaper_id,
                flag_id=flag_id,
                event="reminded",
                actor_user_id=ctx.user_id,
                agent_run_id=None,
                ref={"to": "follow_up", "ids": [str(d.id) for d in drafts]},
            )
        )
        tx.record(
            "attention_flag.reminded",
            target=Target(PAPER_TARGET, workpaper_id),
            after=Ref(flag=flag_id, drafts=len(drafts)),
            scope=Scope(engagement_id=engagement_id, work_item_id=flag.work_item_id),
        )
    return Converted(flag, drafts[0].id)
