"""The closes part of the portal home (C-01-T26; C-01 §4.8; P-08 §2.2; DEC-5412).

A close in the scope shows a work card with the client stage tracker (C2 `close` codes through
`portal.stages`), and the client's open transaction questions are one "answer" to-do that opens
POR-11. Both wait on `closes.portal_requests`; a delivered or locked close is an Earlier row, not
a card. Client codes only: no figure, no firm status, no "Accrued".
"""

from __future__ import annotations

from abacus.kernel._flags import CLOSES_PORTAL_REQUESTS
from abacus.kernel.flags import flag_enabled
from abacus.modules.closes.api import close_for
from abacus.modules.engagements.api import contact_ids_of_user
from abacus.modules.identity.api import AuthContext
from abacus.modules.portal import stages
from abacus.modules.portal.home_sources import (
    HomePart,
    HomeScope,
    Pill,
    Stage,
    Target,
    Todo,
    WorkCard,
    register_home_source,
)
from abacus.modules.requests.api import questions_for


async def closes_source(ctx: AuthContext, scope: HomeScope) -> HomePart:
    part = HomePart()
    closes = [i for i in scope.work_items if i.kind == "close"]
    if not closes or not await flag_enabled(ctx.tenant, CLOSES_PORTAL_REQUESTS):
        return part
    mine = await contact_ids_of_user(ctx.tenant, ctx.user_id)
    open_questions = 0
    first: str | None = None
    for item in closes:
        facts = await close_for(ctx.tenant, item.id)
        view = stages.client_view("close", facts.status)
        if view is not None:
            part.work_cards.append(
                WorkCard(
                    item.id,
                    item.kind,
                    item.name,
                    Pill(view.pill, view.variant),
                    [Stage(s.code, s.state) for s in view.stages],
                )
            )
        asked = [
            q
            for q in await questions_for(ctx.tenant, item.id)
            if q.status == "open" and q.assignee_contact_id in mine
        ]
        if asked and first is None:
            first = str(item.id)
        open_questions += len(asked)
    if open_questions:
        part.todos.append(
            Todo(
                "answer",
                open_questions,
                "open",
                target=Target("POR-11", {"closeId": first} if first else {}),
            )
        )
    return part


register_home_source("closes", closes_source)
