"""Public interface of the engagements module; other modules import only this (ADR-008)."""

from abacus.modules.engagements.routes import router
from abacus.modules.engagements.service import EngagementRef, get_ref

__all__ = ["EngagementRef", "get_ref", "router"]
