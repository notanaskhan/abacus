"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.routes import router
from abacus.modules.requests.service import FulfilmentRef, fulfil_by_rule

__all__ = ["FulfilmentRef", "RequestItemCreated", "fulfil_by_rule", "router"]
