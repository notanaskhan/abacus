"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.requests.availability import register_available_datasets
from abacus.modules.requests.classification import classify
from abacus.modules.requests.events import RequestItemClassified, RequestItemCreated
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
    fulfil_by_upload,
    fulfilled_items,
    fulfilled_versions,
    item_ref,
    item_versions,
    move_after_review,
    read_item,
    read_item_versions,
    request_items_for,
    review_targets,
)

__all__ = [
    "FulfilledVersion",
    "FulfilmentRef",
    "ItemNotFulfillable",
    "RequestItemClassified",
    "RequestItemCreated",
    "RequestItemRef",
    "RequestItemSummary",
    "RequestItemView",
    "ReviewTarget",
    "classify",
    "fulfil_by_rule",
    "fulfil_by_upload",
    "fulfilled_items",
    "fulfilled_versions",
    "item_ref",
    "item_versions",
    "methodology_router",
    "move_after_review",
    "read_item",
    "read_item_versions",
    "register_available_datasets",
    "request_items_for",
    "review_targets",
    "router",
]
