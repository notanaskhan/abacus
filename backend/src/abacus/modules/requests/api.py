"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.modules.engagements.api import register_roll_forward_items
from abacus.modules.requests.availability import register_available_datasets
from abacus.modules.requests.classification import classify, document_kind
from abacus.modules.requests.comments import register_comment_scope_check
from abacus.modules.requests.events import (
    DueDatesChanged,
    RequestItemClassified,
    RequestItemCreated,
    RequestItemDocumentKindChanged,
)
from abacus.modules.requests.roll_forward import copy_items, proposed_items
from abacus.modules.requests.routes import firm_router, methodology_router, router
from abacus.modules.requests.service import (
    FulfilledVersion,
    FulfilmentRef,
    ItemKind,
    ItemNotFulfillable,
    NewRequestItem,
    OverdueItem,
    RequestItemRef,
    RequestItemSummary,
    RequestItemView,
    ReviewTarget,
    add_request_item,
    apply_drafted_guidance,
    fulfil_by_rule,
    fulfil_by_upload,
    fulfilled_items,
    fulfilled_versions,
    item_ref,
    item_versions,
    items_of_version,
    latest_version_of,
    move_after_review,
    overdue_for,
    read_item,
    read_item_versions,
    request_items_for,
    review_targets,
)

# SPEC-025 (TASK-048 D1): last year's items for a roll-forward, and copying the confirmed ones.
register_roll_forward_items(proposed_items, copy_items)

__all__ = [
    "DueDatesChanged",
    "FulfilledVersion",
    "FulfilmentRef",
    "ItemKind",
    "ItemNotFulfillable",
    "NewRequestItem",
    "OverdueItem",
    "RequestItemClassified",
    "RequestItemCreated",
    "RequestItemDocumentKindChanged",
    "RequestItemRef",
    "RequestItemSummary",
    "RequestItemView",
    "ReviewTarget",
    "add_request_item",
    "apply_drafted_guidance",
    "classify",
    "document_kind",
    "firm_router",
    "fulfil_by_rule",
    "fulfil_by_upload",
    "fulfilled_items",
    "fulfilled_versions",
    "item_ref",
    "item_versions",
    "items_of_version",
    "latest_version_of",
    "methodology_router",
    "move_after_review",
    "overdue_for",
    "read_item",
    "read_item_versions",
    "register_available_datasets",
    "register_comment_scope_check",
    "request_items_for",
    "review_targets",
    "router",
]
