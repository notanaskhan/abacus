"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.repository import client_column
from abacus.modules.engagements.routes import router
from abacus.modules.engagements.service import (
    EngagementRef,
    client_of,
    get_ref,
    lock_ref,
)
from abacus.modules.identity.api import register_engagement_client

# Identity owns ethical walls; this module owns which client an engagement belongs to (TASK-016).
register_engagement_client(client_column, client_of)

__all__ = ["EngagementCreated", "EngagementRef", "get_ref", "lock_ref", "router"]
