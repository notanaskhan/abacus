"""Public interface of the workbench module; other modules import only this (ADR-008).

P-10-T09: C6 v2's sessions half, a stub; P-10-T04 owns the tables; P-10-T43 the sessions core
(the snapshot, the message post, `WorkbenchSessionWorkflow` and its turn activity).
"""

from collections.abc import Awaitable, Callable, Mapping

from abacus.kernel.dispatch import register_work_classes
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import register_session_links
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.workbench.run_links import session_links
from abacus.modules.workbench.session_activities import SESSION_ACTIVITIES
from abacus.modules.workbench.session_workflow import WorkbenchSessionWorkflow
from abacus.modules.workbench.sessions import (
    SessionLocked,
    SessionSummary,
    get_session,
    open_session,
    post_message,
    sessions_for_subject,
)
from abacus.modules.workbench.sessions_contract import agent_badge_router, sessions_router

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (sessions_router, agent_badge_router)

# P-10-T14: the legacy run backfill asks which session first named each run.
register_session_links(session_links)

# The worker's parts (P-39): the session workflow and its turn activity; no subscriptions yet.
SUBSCRIPTIONS: Mapping[str, Callable[[OutboxEvent], Awaitable[None]]] = {}
WORKFLOWS: dict[type, str] = {WorkbenchSessionWorkflow: "interactive"}
ACTIVITIES: tuple[object, ...] = SESSION_ACTIVITIES
register_work_classes(WORKFLOWS)  # type: ignore[arg-type]  # registry kind literal

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "SessionLocked",
    "SessionSummary",
    "get_session",
    "open_session",
    "post_message",
    "sessions_for_subject",
]
