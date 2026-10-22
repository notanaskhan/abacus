"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.engagements.api import register_roll_forward_items
from abacus.modules.identity.api import AbacusRouter
from abacus.modules.requests.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.requests.availability import register_available_datasets
from abacus.modules.requests.classification import classify, document_kind
from abacus.modules.requests.comments import register_comment_scope_check
from abacus.modules.requests.contract import binders_router, items_router, portal_router
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

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    firm_router,
    methodology_router,
    binders_router,  # C5 v1 stub (P-06-T01)
    items_router,
    portal_router,
)

# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ROUTERS",
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
