"""The signatures part of the home: the Sign to-do (N-02-T24; P-08 §2.2 to-do kind `sign`;
POR-02 → POR-06).

One to-do counting the envelopes on the scope's engagements that wait for the person's own
signature (they are a named signer and have not signed or declined), with the earliest due date;
overdue once that date has passed. Only engagements `home.py` already authorised for this scope
(INV-4); a spouse's or another signer's envelope never counts. Nothing is shown with none.
"""

from __future__ import annotations

from abacus.modules.identity.api import AuthContext
from abacus.modules.portal.home_sources import (
    HomePart,
    HomeScope,
    Target,
    Todo,
    register_home_source,
)
from abacus.modules.signatures.api import sign_todo


async def signatures_source(ctx: AuthContext, scope: HomeScope) -> HomePart:
    part = HomePart()
    todo = await sign_todo(ctx, scope.engagements)
    if todo.count:
        overdue = todo.due_on is not None and todo.due_on < scope.today
        part.todos.append(
            Todo(
                "sign",
                todo.count,
                "overdue" if overdue else "open",
                due_date=todo.due_on,
                target=Target("POR-06"),
            )
        )
    return part


register_home_source("signatures", signatures_source)
