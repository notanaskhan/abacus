"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.routes import router
from abacus.modules.requests.service import (
    FulfilledVersion,
    FulfilmentRef,
    ItemNotFulfillable,
    RequestItemRef,
    RequestItemSummary,
    ReviewTarget,
    fulfil_by_rule,
    fulfilled_items,
    fulfilled_versions,
    item_ref,
    move_after_review,
    review_targets,
)

__all__ = [
    "FulfilledVersion",
    "FulfilmentRef",
    "ItemNotFulfillable",
    "RequestItemCreated",
    "RequestItemRef",
    "RequestItemSummary",
    "ReviewTarget",
    "fulfil_by_rule",
    "fulfilled_items",
    "fulfilled_versions",
    "item_ref",
    "move_after_review",
    "review_targets",
    "router",
]
