"""The connections part of the home: the reconnect to-do (A-02-T23; TASK-1471; P-08 §2.2 to-do
kind `reconnect`; A-02 AC-11.1).

One to-do counting the firm's open reconnect requests on the live connections of the scope's
engagements' entities, for a person who holds `connection.read` there (the client Owner; INV-4:
only engagements `home.py` already authorised for this scope). It opens POR-16 and clears when
the client reconnects (the reconnect fulfils the request). Nothing is shown with none open.
"""

from __future__ import annotations

from abacus.modules.connections.api import reconnect_todo_count
from abacus.modules.identity.api import AuthContext
from abacus.modules.portal.home_sources import (
    HomePart,
    HomeScope,
    Target,
    Todo,
    register_home_source,
)


async def connections_source(ctx: AuthContext, scope: HomeScope) -> HomePart:
    part = HomePart()
    count = await reconnect_todo_count(ctx, scope.engagements)
    if count:
        part.todos.append(Todo("reconnect", count, "open", target=Target("POR-16")))
    return part


register_home_source("connections", connections_source)
