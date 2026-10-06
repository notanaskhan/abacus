"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.routes import router
from abacus.modules.requests.service import (
    FulfilmentRef,
    ItemNotFulfillable,
    RequestItemRef,
    fulfil_by_rule,
    item_ref,
)

__all__ = [
    "FulfilmentRef",
    "ItemNotFulfillable",
    "RequestItemCreated",
    "RequestItemRef",
    "fulfil_by_rule",
    "item_ref",
    "router",
]
