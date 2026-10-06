"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from abacus.modules.engagements.events import EngagementCreated
from abacus.modules.engagements.routes import router
from abacus.modules.engagements.service import EngagementRef, get_ref, lock_ref

__all__ = ["EngagementCreated", "EngagementRef", "get_ref", "lock_ref", "router"]
