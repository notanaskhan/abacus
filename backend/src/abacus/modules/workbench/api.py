"""Public interface of the workbench module; other modules import only this (ADR-008).

P-10-T09: C6 v2's sessions half, a stub; P-10-T04 owns the tables; P-10-T43 the sessions core
(the snapshot, the message post, `WorkbenchSessionWorkflow` and its turn activity).
"""

from collections.abc import Awaitable, Callable, Mapping

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.kernel.dispatch import register_work_classes
from abacus.kernel.uow.relay import OutboxEvent
from abacus.modules.agents.api import register_session_links
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.workbench.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.workbench.list_contract import context_options_router, manage_router
from abacus.modules.workbench.run_links import session_links
from abacus.modules.workbench.session_activities import SESSION_ACTIVITIES
from abacus.modules.workbench.session_events import register as _register_session_topic
from abacus.modules.workbench.session_workflow import (
    SessionInput,
    TurnDone,
    WorkbenchSessionWorkflow,
    session_workflow_id,
)
from abacus.modules.workbench.sessions import (
    SessionLocked,
    SessionSummary,
    get_session,
    open_session,
    post_message,
)
from abacus.modules.workbench.sessions_contract import agent_badge_router, sessions_router
from abacus.modules.workbench.today_questions_contract import today_questions_router

# P-10-T43: the audit explorer places a session's events by its engagement (SPEC-304).
register_engagement_owners(AUDIT_KINDS, audit_owners)
_register_session_topic()  # TASK-7325: `session:<id>` and `session.items_changed`

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    sessions_router,
    agent_badge_router,
    # W-02-T02: rename, delete and the context routes (stubs).
    manage_router,
    context_options_router,
    # I-02-T03: the Today questions route shape (stub).
    today_questions_router,
)

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
    "SessionInput",
    "SessionLocked",
    "SessionSummary",
    "TurnDone",
    "WorkbenchSessionWorkflow",
    "get_session",
    "open_session",
    "post_message",
    "session_workflow_id",
]
