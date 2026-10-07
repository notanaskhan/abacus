"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.routes import router
from abacus.modules.requests.service import (
    FulfilledVersion,
    FulfilmentRef,
    ItemNotFulfillable,
    RequestItemRef,
    RequestItemSummary,
    fulfil_by_rule,
    fulfilled_items,
    fulfilled_versions,
    item_ref,
    move_after_review,
)

__all__ = [
    "FulfilledVersion",
    "FulfilmentRef",
    "ItemNotFulfillable",
    "RequestItemCreated",
    "RequestItemRef",
    "RequestItemSummary",
    "fulfil_by_rule",
    "fulfilled_items",
    "fulfilled_versions",
    "item_ref",
    "move_after_review",
    "router",
]
