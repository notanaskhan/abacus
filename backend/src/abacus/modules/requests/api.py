"""Public interface of the requests module; other modules import only this (ADR-008)."""

from abacus.kernel.audit_owners import register_engagement_owners
from abacus.modules.engagements.api import register_open_requests, register_roll_forward_items
from abacus.modules.identity.api import (
    AbacusRouter,
    register_contact_delegations,
    register_scope_resolver,
)
from abacus.modules.requests.audit_targets import AUDIT_KINDS, audit_owners
from abacus.modules.requests.availability import register_available_datasets
from abacus.modules.requests.binder_index import register_binder_tag
from abacus.modules.requests.binders import (
    SUBSCRIPTIONS,
    DropBinder,
    drop_binder,
    drop_binder_open,
    register_binder_close_rule,
)
from abacus.modules.requests.classification import classify, document_kind
from abacus.modules.requests.comments import register_comment_scope_check
from abacus.modules.requests.contract import (
    RequestLatestUploadOut,
    RequestOwedByOut,
    binders_router,
    items_router,
    portal_router,
)
from abacus.modules.requests.events import (
    DueDatesChanged,
    RequestItemClassified,
    RequestItemCreated,
    RequestItemDocumentKindChanged,
)
from abacus.modules.requests.follow_up_reads import FollowUpCandidate, follow_up_candidates
from abacus.modules.requests.lifecycle import (
    contact_delegations,
    end_contact_delegations,
    record_contact_delegations,
    register_live_facts,
    request_item_scope,
)
from abacus.modules.requests.pbc_contract import pbc_firm_router, pbc_portal_router
from abacus.modules.requests.portal_home import BinderProgress, ClientHome, client_home
from abacus.modules.requests.repository import open_requests_by_engagement
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
    drop_items,
    drop_target,
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
    reopen_after_undo,
    request_items_for,
    review_targets,
    upload_item_of,
    withdraw_upload,
)

# P-07-T25 (C5): CLI-04 records, ends and counts a contact's delegated requests through this.
register_contact_delegations(
    record_contact_delegations, end_contact_delegations, contact_delegations
)
# SPEC-025 (TASK-048 D1): last year's items for a roll-forward, and copying the confirmed ones.
register_roll_forward_items(proposed_items, copy_items)

# P-06-T07: binders close when C1 says their work is finished (the subscriber is in binders.py).
WORKFLOWS: dict[type, str] = {}
ACTIVITIES: tuple[object, ...] = ()

# The routers the API mounts, in order (P-39; F-03-T07).
ROUTERS: tuple[AbacusRouter, ...] = (
    router,
    firm_router,
    methodology_router,
    binders_router,  # C5 v1 stub (P-06-T01)
    items_router,
    portal_router,
    pbc_portal_router,  # C5 portal-pbc stub (R-01-T01): undo an Ignore, undo Mark as Done
    pbc_firm_router,  # C5 portal-pbc stub (R-01-T01): void a rule fulfilment
)

# P-07-T08: the clients index's open-request count.
register_open_requests(open_requests_by_engagement)
# P-06-T10: a delegate's `request_item` grant resolves to its request's engagement and client.
register_scope_resolver("request_item", request_item_scope)
# DEC-121: the audit explorer asks each owner which engagement its targets belong to.
register_engagement_owners(AUDIT_KINDS, audit_owners)

__all__ = [
    "ACTIVITIES",
    "ROUTERS",
    "SUBSCRIPTIONS",
    "WORKFLOWS",
    "BinderProgress",
    "ClientHome",
    "DropBinder",
    "DueDatesChanged",
    "FollowUpCandidate",
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
    "RequestLatestUploadOut",
    "RequestOwedByOut",
    "ReviewTarget",
    "add_request_item",
    "apply_drafted_guidance",
    "classify",
    "client_home",
    "document_kind",
    "drop_binder",
    "drop_binder_open",
    "drop_items",
    "drop_target",
    "firm_router",
    "follow_up_candidates",
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
    "register_binder_close_rule",
    "register_binder_tag",
    "register_comment_scope_check",
    "register_live_facts",
    "reopen_after_undo",
    "request_items_for",
    "review_targets",
    "router",
    "upload_item_of",
    "withdraw_upload",
]
