"""What a follow-up may chase (P-06-T14; BND-01 b, BND-02 d; DEC-220).

The agents module drafts follow-ups; it reads the requests through this. A request is chased
while it is open for the client: Requested or Returned, client-visible, not deleted, in a
Published binder. Reads go through `visible()` for the caller, so a walled engagement's requests
are absent.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.modules.identity.api import AuthContext
from abacus.modules.requests.binders import BinderNotPublished, current_recipients
from abacus.modules.requests.repository import (
    binder_statuses,
    binders_recipient_rows,
    follow_up_items,
)


@dataclass(frozen=True)
class FollowUpCandidate:
    id: UUID
    engagement_id: UUID
    binder_id: UUID
    title: str  # the title the client reads, else the client wording
    due_on: date | None
    client_assignee_user_id: UUID | None
    binder_recipient_contact_ids: tuple[UUID, ...]  # the binder's current recipients


async def follow_up_candidates(
    ctx: AuthContext, binder_ids: Sequence[UUID], item_ids: Sequence[UUID]
) -> list[FollowUpCandidate]:
    """The open client-visible requests of these binders or ids the caller may read, each once,
    in engagement, due-date and creation order. Only a Published binder is chased: a binder the
    caller may read that is not Published answers 409 `binder_not_published` (nothing is
    drafted); requests asked for by id keep only those in Published binders."""
    async with tenant_session(ctx.tenant) as session:
        statuses = await binder_statuses(session, ctx, binder_ids)
        for binder in binder_ids:
            if statuses.get(binder, "published") != "published":
                raise BinderNotPublished(facts={"binder_id": str(binder)})
        rows = await follow_up_items(session, ctx, binder_ids, item_ids)
        binders = sorted({item.request_list_id for item, _ in rows}, key=str)
        history = await binders_recipient_rows(session, binders)
    recipients = {
        binder: tuple(current_recipients([r for r in history if r.binder_id == binder]))
        for binder in binders
    }
    return [
        FollowUpCandidate(
            id=item.id,
            engagement_id=item.engagement_id,
            binder_id=item.request_list_id,
            title=(item.title or item.description).strip(),
            due_on=due,
            client_assignee_user_id=item.client_assignee_user_id,
            binder_recipient_contact_ids=recipients.get(item.request_list_id, ()),
        )
        for item, due in rows
    ]
