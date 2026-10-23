"""The requests part of the home: the upload to-do and the binder card (P-08 §2.2: from `requests`,
with P-06's derived overdue)."""

from __future__ import annotations

from datetime import date

from abacus.modules.identity.api import AuthContext
from abacus.modules.portal.home_sources import (
    Binder,
    HomePart,
    HomeScope,
    Target,
    Todo,
    register_home_source,
)
from abacus.modules.requests.api import client_home


async def requests_source(ctx: AuthContext, scope: HomeScope) -> HomePart:
    part = HomePart()
    count, overdue = 0, False
    dues: list[date] = []
    for engagement_id in scope.engagements:
        home = await client_home(ctx, engagement_id, scope.today)
        count += home.upload_count
        overdue = overdue or home.overdue
        if home.due_date is not None:
            dues.append(home.due_date)
        if home.binder is not None:
            b = home.binder
            part.binders.append(Binder(b.binder_id, b.done, b.total, b.sorted_count))
    part.todos.append(
        Todo(
            "upload",
            count,
            "overdue" if overdue else "open" if count else "none",
            due_date=min(dues) if dues else None,
            target=Target("POR-03") if count else None,
        )
    )
    return part


register_home_source("requests", requests_source)
