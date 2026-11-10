"""Public interface of the collaboration module; other modules import only this (ADR-008).

P-05 (SPEC-650; ADR-236 proposed, built dark behind `collaboration.v2`, DEC-3200): comments v2
(P-05-T05) and to-dos (P-05-T06) on anchors their owning modules register through
`register_anchor`.
"""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.collaboration.anchors import (
    AnchorFacts,
    AnchorProvider,
    Locator,
    register_anchor,
    registered_kinds,
)
from abacus.modules.collaboration.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.collaboration.client_threads import (
    ClientComment,
    client_comments,
    post_client_comment,
    register_client_policy,
)
from abacus.modules.collaboration.routes import threads_router, todos_router
from abacus.modules.collaboration.threads import open_thread
from abacus.modules.collaboration.todos import TODO_ANCHORS
from abacus.modules.collaboration.todos import create as create_todo
from abacus.modules.identity.api import AbacusRouter

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    threads_router,  # P-05-T05: /v1/comment-threads*, /v1/thread-comments*, candidates
    todos_router,  # P-05-T06: /v1/todos*
)

# P-05-T06: a to-do is itself an anchor (its threads, SHL-17's comment count).
register_anchor("todo", TODO_ANCHORS)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ROUTERS",
    "AnchorFacts",
    "AnchorProvider",
    "ClientComment",
    "Locator",
    "client_comments",
    "create_todo",
    "open_thread",
    "post_client_comment",
    "register_anchor",
    "register_client_policy",
    "registered_kinds",
]
