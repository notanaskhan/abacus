"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.requests.events import RequestItemCreated
from abacus.modules.requests.routes import methodology_router, router
from abacus.modules.requests.service import (
    FulfilledVersion,
    FulfilmentRef,
    ItemNotFulfillable,
    RequestItemRef,
    RequestItemSummary,
    RequestItemView,
    ReviewTarget,
    fulfil_by_rule,
    fulfilled_items,
    fulfilled_versions,
    item_ref,
    move_after_review,
    request_items_for,
    review_targets,
)

__all__ = [
    "FulfilledVersion",
    "FulfilmentRef",
    "ItemNotFulfillable",
    "RequestItemCreated",
    "RequestItemRef",
    "RequestItemSummary",
    "RequestItemView",
    "ReviewTarget",
    "fulfil_by_rule",
    "fulfilled_items",
    "fulfilled_versions",
    "item_ref",
    "methodology_router",
    "move_after_review",
    "request_items_for",
    "review_targets",
    "router",
]
