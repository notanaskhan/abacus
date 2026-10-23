"""P-08-T13: what a client person's portal home shows of one engagement's requests (POR-02).

The upload to-do counts the same items as `your_part` (open or sent back, the person's own, or
unassigned for a client admin), so the home ties to the requests page. Overdue is the request's
derived overdue (P-06): past its own or its binder's due date while still open. The binder card is
the most recently published binder's progress over its client-visible requests, and the files the
firm matched to them ("Brightwater Hale sorted 37 of your files"); never the agent by name.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from abacus.kernel.db import tenant_session
from abacus.modules.identity.api import AuthContext, engagement_role_of
from abacus.modules.requests.binders import DONE
from abacus.modules.requests.repository import client_home_items
from abacus.modules.requests.service import OPEN_FOR_CLIENT

_CLIENT_ROLES = frozenset({"client_admin", "client_contributor"})


@dataclass(frozen=True)
class BinderProgress:
    binder_id: UUID
    done: int
    total: int
    sorted_count: int


@dataclass(frozen=True)
class ClientHome:
    upload_count: int
    overdue: bool
    due_date: date | None  # the earliest due date of the counted items
    binder: BinderProgress | None


async def client_home(ctx: AuthContext, engagement_id: UUID, today: date) -> ClientHome:
    """For a caller that authorised `portal_home.read` on the engagement; firm roles get none."""
    role = await engagement_role_of(ctx.tenant, engagement_id, ctx.user_id)
    if role not in _CLIENT_ROLES:
        return ClientHome(0, False, None, None)
    async with tenant_session(ctx.tenant) as session:
        rows = await client_home_items(session, ctx, engagement_id)
    mine = [
        (item, binder)
        for item, binder, _ in rows
        if item.status in OPEN_FOR_CLIENT
        and (
            item.client_assignee_user_id == ctx.user_id
            or (role == "client_admin" and item.client_assignee_user_id is None)
        )
    ]
    dues = sorted(d for i, b in mine if (d := i.due_on or b.default_due_on) is not None)
    binder = None
    published = [b for _, b, _ in rows if b.published_at is not None]
    if published:
        latest = max(published, key=lambda b: (b.published_at, b.id))
        own = [(i, n) for i, b, n in rows if b.id == latest.id]
        binder = BinderProgress(
            latest.id,
            sum(1 for i, _ in own if i.status in DONE),
            len(own),
            sum(n for _, n in own),
        )
    return ClientHome(len(mine), bool(dues) and dues[0] < today, dues[0] if dues else None, binder)
